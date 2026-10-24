from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import median
from typing import Iterable
import math

CHANNELS = ("temp_c", "rh_pct", "pressure_hpa", "wind_kmh", "wind_dir_deg", "rain_mm", "ghi_wm2")
FIELDS = ("station_id", "channel", "start_utc", "end_utc", "issue", "action", "note")


def stamp(t: datetime) -> str:
    return t.strftime("%Y-%m-%d %H:%M")


def med(values: Iterable[float], default: float = math.nan) -> float:
    values = [x for x in values if math.isfinite(x)]
    return median(values) if values else default


def mad(values: list[float]) -> float:
    middle = med(values)
    return med(abs(v - middle) for v in values)


def distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a, b = math.radians(lat1), math.radians(lat2)
    dlat, dlon = b - a, math.radians(lon2 - lon1)
    q = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(min(1, math.sqrt(q)))


def correlation(a: list[float], b: list[float]) -> float:
    if len(a) < 3:
        return 0.0
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((x - mb) ** 2 for x in b))
    return cov / den if den else 0.0


@dataclass
class Record:
    row: int
    raw: datetime
    time: datetime
    values: dict[str, float]
    excluded: set[str] = field(default_factory=set)
    removed: bool = False
    clock_unsafe: bool = False

    def value(self, channel: str) -> float:
        if self.removed or self.clock_unsafe or channel in self.excluded:
            return math.nan
        return self.values.get(channel, math.nan)


@dataclass
class Station:
    id: str
    name: str
    lat: float
    lon: float
    elevation: float
    interval: int
    installed: datetime
    records: list[Record] = field(default_factory=list)
    gps: list = field(default_factory=list)
    gps_stats: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    source_status: str = "available"

    @property
    def step(self) -> timedelta:
        return timedelta(minutes=self.interval)

    @property
    def bounds(self) -> tuple[datetime, datetime]:
        times = [r.time for r in self.records if not r.removed]
        return min(times), max(times)

    def index(self) -> dict[datetime, Record]:
        return {r.time: r for r in self.records if not r.removed and not r.clock_unsafe}

    def grid(self, begin: datetime, end: datetime) -> tuple[datetime, datetime, int]:
        """Nominal slots, preserving observed phase and respecting installation."""
        times = self.index()
        anchor = min(times) if times else begin
        first = anchor + math.ceil((max(begin, self.installed) - anchor) / self.step) * self.step
        last = anchor + math.floor((end - anchor) / self.step) * self.step
        return first, last, max(0, int((last - first) / self.step) + 1)


@dataclass
class Flag:
    station_id: str
    channel: str
    start: datetime
    end: datetime
    issue: str
    action: str
    note: str
    confidence: str = "high"
    evidence: dict = field(default_factory=dict)

    def as_row(self) -> dict[str, str]:
        return dict(zip(FIELDS, (self.station_id, self.channel, stamp(self.start), stamp(self.end),
                                self.issue, self.action, self.note)))


@dataclass
class Analysis:
    stations: dict[str, Station]
    flags: list[Flag] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add(self, station: Station, channel: str, start: datetime, end: datetime,
            issue: str, action: str, note: str, confidence: str = "high", **evidence) -> Flag:
        flag = Flag(station.id, channel, start, end, issue, action, note, confidence, evidence)
        self.flags.append(flag)
        if action == "exclude" and channel != "metadata":
            channels = CHANNELS if channel == "all" else (channel,)
            for record in station.records:
                if start <= record.time <= end:
                    record.excluded.update(channels)
        return flag


def network_bounds(result: Analysis) -> tuple[datetime, datetime]:
    times = [r.time for s in result.stations.values() for r in s.records
             if not r.removed and not r.clock_unsafe]
    if not times:
        # Still allow a withheld pack to be reported, without claiming valid UTC.
        times = [r.time for s in result.stations.values() for r in s.records if not r.removed]
    if not times:
        raise ValueError("No weather observations in the pack")
    return min(times), max(times)


def runs(records: list[Record], selected: Iterable[bool], step: timedelta) -> list[list[Record]]:
    """Contiguous selected observations; gaps break incidents."""
    result, current = [], []
    for record, choose in zip(records, selected):
        if not choose or (current and record.time - current[-1].time != step):
            if current:
                result.append(current)
            current = []
        if choose:
            current.append(record)
    if current:
        result.append(current)
    return result
