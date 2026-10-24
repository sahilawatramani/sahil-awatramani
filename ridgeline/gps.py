"""Checksum-qualified RMC/GGA parsing; no GGA date guessed from logger time."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter
import math


@dataclass
class Fix:
    logger: datetime
    utc: datetime | None
    lat: float
    lon: float
    kind: str
    quality: int = 0
    satellites: int = 0
    hdop: float = math.nan
    altitude_msl: float = math.nan


def coordinate(value: str, hemisphere: str) -> float:
    width = 2 if hemisphere in ("N", "S") else 3
    if hemisphere not in ("N", "S", "E", "W") or len(value) <= width:
        raise ValueError("invalid coordinate")
    degrees, minutes = int(value[:width]), float(value[width:])
    limit = 90 if width == 2 else 180
    if not math.isfinite(minutes) or not 0 <= minutes < 60 or not 0 <= degrees <= limit:
        raise ValueError("coordinate out of range")
    result = degrees + minutes / 60
    if result > limit:
        raise ValueError("coordinate out of range")
    return -result if hemisphere in ("S", "W") else result


def parse_line(line: str) -> tuple[Fix | None, str]:
    try:
        logger_text, sentence = line.strip().split(",", 1)
        logger = datetime.fromisoformat(logger_text)
        if logger.tzinfo is not None or not sentence.startswith("$"):
            return None, "malformed"
        payload, checksum = sentence[1:].rsplit("*", 1)
        check = 0
        for char in payload:
            check ^= ord(char)
        if len(checksum) != 2 or check != int(checksum, 16):
            return None, "checksum_failed"
        f = payload.split(",")
        kind = f[0][-3:]
        if kind == "RMC":
            if f[2] != "A" or (len(f) > 12 and f[12] in ("N", "E", "M", "S")):
                return None, "invalid_fix"
            tod = f[1]
            base = datetime.strptime(f[9] + tod[:6], "%d%m%y%H%M%S")
            if "." in tod:
                base += timedelta(seconds=float("0." + tod.split(".")[1]))
            return Fix(logger, base, coordinate(f[3], f[4]), coordinate(f[5], f[6]), kind), "accepted_rmc"
        if kind == "GGA":
            quality, satellites, hdop = int(f[6]), int(f[7]), float(f[8])
            if quality not in (1, 2, 4, 5) or satellites < 4 or not math.isfinite(hdop) or not 0 < hdop <= 5:
                return None, "poor_gga_fix"
            if f[10] != "M":
                return None, "malformed"
            altitude = float(f[9])
            if not math.isfinite(altitude):
                return None, "malformed"
            return Fix(logger, None, coordinate(f[2], f[3]), coordinate(f[4], f[5]), kind,
                       quality, satellites, hdop, altitude), "accepted_gga"
        return None, "unsupported"
    except (ValueError, IndexError, OverflowError):
        return None, "malformed"


def read_gps(path: Path) -> tuple[list[Fix], dict]:
    fixes, counts = [], Counter()
    if not path.exists():
        return [], {"missing_file": 1}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        fix, reason = parse_line(line)
        counts[reason] += 1
        if fix:
            fixes.append(fix)
    return fixes, dict(counts)
