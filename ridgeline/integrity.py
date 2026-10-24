"""Clock repair precedes duplicate detection and chronological comparisons."""
from collections import defaultdict
from datetime import timedelta
import math
from .model import Analysis, CHANNELS, distance, med, network_bounds, runs, stamp


def repair_clocks(result: Analysis) -> None:
    for station in result.stations.values():
        if not station.records:
            continue
        fixes = sorted((f for f in station.gps if f.utc), key=lambda f: f.utc)
        segments = []
        for fix in fixes:
            offset = round((fix.logger - fix.utc).total_seconds() / 60) * 60
            if not segments or segments[-1][0] != offset:
                segments.append((offset, [fix]))
            else:
                segments[-1][1].append(fix)
        # A transient fix must never move a whole weather record segment.
        stable = [(off, ff) for off, ff in segments if len(ff) >= 3 and
                  (ff[-1].utc - ff[0].utc).total_seconds() >= 7200 and
                  max(abs((f.logger-f.utc).total_seconds()-off) for f in ff) <= 3]
        if not stable:
            continue
        correction = 0
        cursor = 0
        for number, (offset, ff) in enumerate(stable):
            new_correction = -offset
            if new_correction == correction:
                continue
            prior = stable[number - 1][1][-1].utc if number else None
            candidates = []
            for i in range(max(1, cursor + 1), len(station.records)):
                a, b = station.records[i - 1], station.records[i]
                before = a.raw + timedelta(seconds=correction)
                after = b.raw + timedelta(seconds=new_correction)
                if after - before == station.step and (not prior or before >= prior - station.step) and after <= ff[0].utc + station.step:
                    candidates.append(i)
            if number == 0 and not prior:
                close_to_start = abs((ff[0].logger-station.records[0].raw).total_seconds()) <= 7200
                candidates = [0] if close_to_start else []
            if len(candidates) != 1 or abs(offset) > 86400:
                result.warnings.append(f"{station.id}: GPS clock change could not be mapped uniquely to weather rows; affected times withheld")
                # An ambiguous backward step can overlap earlier logger times;
                # withholding everything is safer than selecting rows by raw date.
                affected = station.records
                if affected:
                    result.add(station, "all", min(r.time for r in affected), max(r.time for r in affected),
                               "unresolved clock change", "exclude", "GPS and logger disagree but the transition cannot be uniquely mapped to source rows; withhold the station until row-level timing is resolved.")
                    for record in affected:
                        record.clock_unsafe = True
                break
            boundary = candidates[0]
            for record in station.records[boundary:]:
                record.time = record.raw + timedelta(seconds=new_correction)
            correction, cursor = new_correction, boundary
            if new_correction:
                start, end = station.records[boundary].time, station.records[-1].time
                result.add(station, "all", start, end, "logger clock offset", "correct",
                           f"Add {new_correction:+d} seconds to source timestamps from CSV line {station.records[boundary].row}; {len(ff)} valid RMC fixes agree within 3 seconds and the row transition restores cadence.",
                           offset_seconds=new_correction, source_line=station.records[boundary].row,
                           gps_fixes=len(ff), transition_backed=boundary>0,
                           raw_start=stamp(station.records[boundary].raw), raw_end=stamp(station.records[-1].raw),
                           gps_last_before=stamp(prior) if prior else None, gps_first_after=stamp(ff[0].utc))
        # Refine each corrected incident end at the next correction, when present.
        clock_flags = [f for f in result.flags if f.station_id == station.id and f.issue == "logger clock offset"]
        for flag in clock_flags:
            source = flag.evidence['source_line']
            segment = []
            for record in station.records:
                if record.row < source:
                    continue
                if (record.time - record.raw).total_seconds() != flag.evidence['offset_seconds']:
                    break
                segment.append(record)
            if segment:
                flag.start, flag.end = segment[0].time, segment[-1].time
                flag.evidence['source_end_line'] = segment[-1].row
                flag.evidence['raw_end'] = stamp(segment[-1].raw)
                support = "the row transition restores cadence" if flag.evidence['transition_backed'] else "initial GPS coverage supports this constant offset"
                flag.note = (f"Add {flag.evidence['offset_seconds']:+d} seconds to source timestamps on CSV lines "
                             f"{source}-{segment[-1].row}; {flag.evidence['gps_fixes']} valid RMC fixes agree within 3 seconds and {support}.")


def inspect_locations(result: Analysis) -> None:
    for station in result.stations.values():
        if not station.records:
            continue
        rmc = [f for f in station.gps if f.utc]
        gga = [f for f in station.gps if f.kind == "GGA"]
        if len(rmc) < 12 or (max(f.utc for f in rmc) - min(f.utc for f in rmc)).total_seconds() < 86400:
            continue
        lat, lon = med(f.lat for f in rmc), med(f.lon for f in rmc)
        spread = med(distance(lat, lon, f.lat, f.lon) for f in rmc)
        separation = distance(station.lat, station.lon, lat, lon)
        corroborated = len(gga) >= 3 and distance(lat, lon, med(f.lat for f in gga), med(f.lon for f in gga)) < .1
        if separation > max(1.0, 10 * spread):
            result.add(station, "metadata", *station.bounds, "location mismatch", "exclude",
                       f"Valid GPS median ({lat:.5f}, {lon:.5f}) is {separation:.1f} km from inventory; withhold coordinate-dependent use until the install location is verified.",
                       "high" if corroborated else "medium", distance_km=round(separation, 3),
                       gps_lat=lat, gps_lon=lon, rmc_fixes=len(rmc), gga_agreement=corroborated)


def inspect_duplicates(result: Analysis) -> None:
    for station in result.stations.values():
        groups = defaultdict(list)
        for record in station.records:
            if not record.clock_unsafe:
                groups[record.time].append(record)
        exact, conflict = [], []
        for time, records in groups.items():
            if len(records) < 2:
                continue
            keys = [tuple(None if math.isnan(r.values[c]) else r.values[c] for c in CHANNELS) for r in records]
            if len(set(keys)) == 1:
                for record in records[1:]:
                    record.removed = True
                exact.append(records[0])
            else:
                conflict.append(records[0])
        for label, records in (("exact retransmission", exact), ("conflicting duplicate", conflict)):
            records.sort(key=lambda r: r.time)
            for group in runs(records, [True] * len(records), station.step):
                if label == "exact retransmission":
                    count = sum(len(groups[r.time]) - 1 for r in group)
                    result.add(station, "all", group[0].time, group[-1].time, label, "correct",
                               f"Drop {count} extra rows with identical timestamps and all seven identical weather values, retaining the first copy.", extra_rows=count)
                else:
                    result.add(station, "all", group[0].time, group[-1].time, label, "exclude",
                               f"{len(group)} timestamps contain conflicting observations after supported clock repairs; no unique value can be selected.")


def inspect_cadence(result: Analysis) -> None:
    # Pack-wide bounds are an explicit assumption for leading/trailing outages.
    start, end = network_bounds(result)
    for station in result.stations.values():
        times = sorted(station.index())
        first, last, count = station.grid(start, end)
        if not station.records:
            if count:
                issue = 'missing weather file' if station.source_status == 'missing' else 'empty weather file'
                result.add(station, 'all', first, last, issue, 'exclude',
                           f"{count} nominal slots unavailable because the weather file is {station.source_status}; period and phase are inferred from the network and inventory.",
                           missing_slots=count, inferred_grid=True)
            continue
        if not times:  # Unsupported clock transitions already withhold the station.
            continue
        before_install = [t for t in times if t < station.installed]
        if before_install:
            result.add(station, 'metadata', min(before_install), max(before_install),
                       'installation date conflict', 'exclude',
                       'Observations predate the inventory installation date; verify station history before assigning climate coverage.')
        positions = sorted({int((t-first)/station.step) for t in times
                            if first <= t <= last and (t-first) % station.step == timedelta(0)})
        previous = -1
        for position in positions + [count]:
            if position - previous > 1:
                a, b = first + (previous+1)*station.step, first + (position-1)*station.step
                missing = position - previous - 1
                result.add(station, 'all', a, b, 'missing observations', 'exclude',
                           f"{missing} expected {station.interval}-minute records are absent; leave missing and do not treat as zero.", missing_slots=missing)
            previous = position
        irregular = []
        for a, b in zip(times, times[1:]):
            if (b-a) % station.step != timedelta(0):
                if irregular and a <= irregular[-1][1] + station.step:
                    irregular[-1] = (irregular[-1][0], b)
                else:
                    irregular.append((a,b))
        for a,b in irregular:
            result.add(station, 'metadata', a, b, 'irregular cadence', 'keep',
                       'Timestamps depart from the inventory grid; retain observations for review but do not aggregate off-grid rows as expected samples.', 'medium')
        for a, b in zip(station.records, station.records[1:]):
            if b.time < a.time and not b.removed and not a.removed and not b.clock_unsafe and not a.clock_unsafe:
                # A reverse delivery order with unique corrected times is sortable.
                result.add(station, "metadata", min(a.time, b.time), max(a.time, b.time),
                           "out-of-order delivery", "correct", "Sort unique observations by corrected UTC while retaining original source row numbers.")
