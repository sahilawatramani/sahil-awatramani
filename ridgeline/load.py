from __future__ import annotations
import csv
import math
import re
from datetime import datetime
from pathlib import Path
from .gps import read_gps
from .model import CHANNELS, Analysis, Record, Station


def load_pack(root: Path) -> Analysis:
    root = root.resolve()
    inventory = root / "stations.csv"
    if not inventory.is_file():
        raise ValueError(f"Missing station inventory: {inventory}")
    result = Analysis({})
    with inventory.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"station_id", "name", "lat", "lon", "elevation_m", "installed", "logger_interval_min"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("stations.csv is missing required columns")
        for row in reader:
            sid = row['station_id']
            if not sid or Path(sid).name != sid or sid in result.stations:
                raise ValueError(f"Invalid or duplicate station ID: {sid!r}")
            try:
                station = Station(sid, row['name'], float(row['lat']), float(row['lon']),
                                  float(row['elevation_m']), int(row['logger_interval_min']),
                                  datetime.fromisoformat(row['installed']))
            except ValueError as error:
                raise ValueError(f"Invalid inventory for {sid}: {error}") from error
            if not (-90 <= station.lat <= 90 and -180 <= station.lon <= 180 and
                    math.isfinite(station.elevation) and 0 < station.interval <= 1440):
                raise ValueError(f"Invalid location or cadence for {sid}")
            result.stations[sid] = station
    if not result.stations:
        raise ValueError("No stations in inventory")
    notebook = root / "maintenance_log.md"
    lines = notebook.read_text(encoding="utf-8-sig").splitlines() if notebook.exists() else []
    for sid, station in result.stations.items():
        station.notes = [line for line in lines if re.search(r'(?<!\w)' + re.escape(sid) + r'(?!\w)', line)]
        path = root / "data" / f"{sid}.csv"
        if not path.exists():
            result.warnings.append(f"{sid}: missing weather file; availability cannot be established")
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not {"timestamp_utc", *CHANNELS}.issubset(reader.fieldnames or []):
                raise ValueError(f"{sid}: weather file is missing required columns")
            for number, row in enumerate(reader, start=2):
                try:
                    time = datetime.fromisoformat(row['timestamp_utc'])
                    if time.tzinfo is not None or time.second or time.microsecond:
                        raise ValueError("expected naive UTC minute timestamp")
                except (ValueError, TypeError) as error:
                    raise ValueError(f"{sid}: invalid timestamp on CSV line {number}; not silently discarded") from error
                values = {}
                for channel in CHANNELS:
                    try:
                        values[channel] = float(row[channel])
                    except (TypeError, ValueError):
                        values[channel] = math.nan
                station.records.append(Record(number, time, time, values))
        station.gps, station.gps_stats = read_gps(root / "gps" / f"{sid}.nmea")
        if not station.records:
            result.warnings.append(f"{sid}: empty weather file")
        if not station.gps:
            result.warnings.append(f"{sid}: no trustworthy GPS fixes; no automatic time or location correction")
    return result
