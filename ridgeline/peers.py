from __future__ import annotations
import math
from .model import Analysis, Record, Station, distance, med


class Peers:
    """Nearby, roughly comparable elevations; per-pair baseline offsets for pressure."""
    def __init__(self, result: Analysis):
        self.result = result
        self.indices = {sid: s.index() for sid, s in result.stations.items()}
        self.disputed = {f.station_id for f in result.flags if f.issue == "location mismatch"}
        self.offsets = {}
        self.selections = {}

    def select(self, station: Station, elevation_limit: float = 700, count: int = 4) -> list[Station]:
        key = station.id, elevation_limit, count
        if key in self.selections:
            return self.selections[key]
        choices = []
        for other in self.result.stations.values():
            if other.id == station.id or other.id in self.disputed or not other.records:
                continue
            km = distance(station.lat, station.lon, other.lat, other.lon)
            elevation = abs(station.elevation - other.elevation)
            if km <= 180 and elevation <= elevation_limit:
                choices.append((km + elevation / 50, other.id, other))
        self.selections[key] = [item[2] for item in sorted(choices)[:count]]
        return self.selections[key]

    def values(self, station: Station, record: Record, channel: str, minimum: int = 2, omit: str | None = None) -> list[float]:
        vals = []
        for peer in self.select(station):
            if peer.id == omit:
                continue
            other = self.indices[peer.id].get(record.time)
            if other:
                value = other.value(channel)
                if math.isfinite(value):
                    vals.append(value)
        return vals if len(vals) >= minimum else []

    def residual(self, station: Station, record: Record, channel: str, omit: str | None = None) -> float:
        vals = self.values(station, record, channel, omit=omit)
        value = record.value(channel)
        return value - med(vals) if vals and math.isfinite(value) else math.nan

    def pressure_residual(self, station: Station, record: Record) -> float:
        vals = []
        for peer in self.select(station):
            key = station.id, peer.id
            if key not in self.offsets:
                differences = []
                for r in station.records:
                    other = self.indices[peer.id].get(r.time)
                    if other and math.isfinite(r.value('pressure_hpa')) and math.isfinite(other.value('pressure_hpa')):
                        differences.append(r.value('pressure_hpa') - other.value('pressure_hpa'))
                self.offsets[key] = med(differences) if len(differences) >= 144 else math.nan
            other = self.indices[peer.id].get(record.time)
            if other:
                value = record.value('pressure_hpa') - other.value('pressure_hpa') - self.offsets[key]
                if math.isfinite(value):
                    vals.append(value)
        return med(vals) if len(vals) >= 2 else math.nan
