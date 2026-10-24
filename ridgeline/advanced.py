"""Conservative peer-supported incident detection; all thresholds documented."""
from __future__ import annotations
from collections import defaultdict
from bisect import bisect_left
from datetime import datetime, timedelta
import math
from .model import Analysis, correlation, mad, med, runs, stamp


def pressure_steps(result: Analysis, peers) -> None:
    candidates = []
    for station in result.stations.values():
        records = sorted(station.index().values(), key=lambda r: r.time)
        times = [r.time for r in records]
        residuals = [peers.pressure_residual(station, r) for r in records]
        for i in range(1, len(records)):
            if records[i].time - records[i-1].time != station.step:
                continue
            jump = residuals[i] - residuals[i-1]
            if not math.isfinite(jump) or abs(jump) < 2.5:
                continue
            lower = bisect_left(times, records[i].time-timedelta(hours=48))
            upper = bisect_left(times, records[i].time+timedelta(hours=48))
            before = [v for v in residuals[lower:i] if math.isfinite(v)]
            after = [v for v in residuals[i:upper] if math.isfinite(v)]
            if min(len(before), len(after)) < 1440 / station.interval:
                continue
            delta = med(after) - med(before)
            noise = max(.2, 1.4826 * med([mad(before), mad(after)]))
            if abs(delta) < max(4, 6 * noise) or jump * delta <= 0:
                continue
            # Real regional pressure changes should appear in peers too.
            corroboration = []
            for peer in peers.select(station):
                index = peers.indices[peer.id]
                a = [r.value('pressure_hpa') - index[r.time].value('pressure_hpa') for r in records[lower:i] if r.time in index]
                b = [r.value('pressure_hpa') - index[r.time].value('pressure_hpa') for r in records[i:upper] if r.time in index]
                change = med(b) - med(a)
                if math.isfinite(change) and change * delta > 0 and abs(change) > 3:
                    corroboration.append(peer.id)
            if len(corroboration) >= 2:
                candidates.append((abs(delta), station, records[i], delta, corroboration))
    accepted = defaultdict(list)
    for _, station, record, delta, support in sorted(candidates, key=lambda x: (-x[0], x[1].id, x[2].time)):
        if any(abs(record.time - t) < timedelta(days=3) for t in accepted[station.id]):
            continue
        accepted[station.id].append(record.time)
        result.add(station, 'pressure_hpa', record.time, station.bounds[1], 'pressure calibration step', 'exclude',
                   f"Target-minus-peer pressure shifts {delta:+.1f} hPa across this boundary with {len(support)} agreeing peers; exclude pending calibration rather than assume an exact offset.",
                   peer_change_hpa=round(delta,3), peers=support, onset_method='adjacent jump plus 48-hour residual windows')


def wind_steps(result: Analysis, peers) -> None:
    for station in result.stations.values():
        records = sorted(station.index().values(), key=lambda r: r.time)
        hourly = defaultdict(list)
        for r in records:
            vals = peers.values(station, r, 'wind_kmh')
            reference = med(vals)
            value = r.value('wind_kmh')
            if math.isfinite(value) and reference >= 5 and value >= 0:
                hourly[r.time.replace(minute=0)].append(math.log((value + .5) / (reference + .5)))
        points = sorted((t, med(v)) for t,v in hourly.items() if len(v) >= max(1, 20/station.interval))
        if len(points) < 24 * 14:
            continue
        daily = defaultdict(list)
        for t,v in points:
            daily[t.date()].append(v)
        days = sorted((d, med(v)) for d,v in daily.items() if len(v) >= 6)
        if len(days) < 21:
            continue
        baseline_loss = sum(abs(v-med(vv for _,vv in days)) for _,v in days)
        best = None
        for k in range(7, len(days)-6):
            a, b = [v for _,v in days[:k]], [v for _,v in days[k:]]
            left, right = med(a), med(b)
            loss = sum(abs(v-left) for v in a) + sum(abs(v-right) for v in b)
            if best is None or loss < best[0]:
                best = loss,k,left,right
        loss,k,left,right = best
        factor = math.exp(right-left)
        if .5 < factor < 2 or baseline_loss <= 0 or loss / baseline_loss > .6:
            continue
        coarse = datetime.combine(days[k][0], datetime.min.time())
        # Refine to an hour; the flag honestly states the onset is estimated.
        nearby = [(t,v) for t,v in points if abs(t-coarse) <= timedelta(days=4)]
        splits = []
        for t,_ in nearby:
            if abs(t-coarse) > timedelta(days=1):
                continue
            a = [v for tt,v in nearby if tt < t]
            b = [v for tt,v in nearby if tt >= t]
            if min(len(a),len(b)) >= 24:
                score = sum(abs(v-left) for v in a) + sum(abs(v-right) for v in b)
                splits.append((score,t))
        onset = min(splits)[1] if splits else coarse
        result.add(station, 'wind_kmh', onset, station.bounds[1], 'wind scale discontinuity', 'exclude',
                   f"Weather-matched wind ratio changes by a factor of {factor:.2f} with a persistent post-change regime; onset is estimated to the hour and no factory calibration factor is known.",
                   'medium', ratio_factor=round(factor,3), loss_reduction=round(1-loss/baseline_loss,3),
                   onset_uncertainty='approximately one hour; inspect raw transition', peers=[s.id for s in peers.select(station)])


def daylight_temperature_drift(result: Analysis, peers) -> None:
    for station in result.stations.values():
        if station.id in peers.disputed:
            continue
        days = defaultdict(list)
        for r in station.index().values():
            residual = peers.residual(station, r, 'temp_c')
            if math.isfinite(residual):
                days[r.time.date()].append((r, residual))
        points, nights = [], []
        for day, values in sorted(days.items()):
            daylight = [v for r,v in values if r.values['ghi_wm2'] > 300]
            dark = [v for r,v in values if r.values['ghi_wm2'] < 5]
            if len(daylight) * station.interval >= 120 and len(dark) * station.interval >= 120:
                points.append((day, med(daylight))); nights.append(med(dark))
        if len(points) < 28:
            continue
        x = [(d-points[0][0]).days for d,_ in points]
        y = [v for _,v in points]
        early, late = med(y[:7]), med(y[-7:])
        night_change = med(nights[-7:])-med(nights[:7])
        if late-early < 2.5 or abs(night_change) > 1.5 or correlation(x,y) < .65:
            continue
        flat_loss = sum(abs(v-med(y)) for v in y)
        options = []
        for k in range(7, len(points)-9):
            slopes = [(y[j]-y[i])/(x[j]-x[i]) for i in range(k,len(x)) for j in range(i+1,len(x)) if x[j]-x[i] >= 7]
            slope = med(slopes)
            intercept = med(v-slope*max(0,xx-x[k]) for xx,v in zip(x,y))
            loss = sum(abs(v-intercept-slope*max(0,xx-x[k])) for xx,v in zip(x,y))
            options.append((loss,k,slope,intercept))
        loss,k,slope,intercept = min(options)
        if slope < .06 or flat_loss <= 0 or loss / flat_loss > .7:
            continue
        onset = datetime.combine(points[k][0], datetime.min.time())
        records = sorted(station.index().values(),key=lambda r:r.time)
        selected = [r.time >= onset and r.values['ghi_wm2'] > 100 and 'temp_c' not in r.excluded for r in records]
        evidence = dict(onset_estimate=stamp(onset), drift_c_per_day=round(slope,3),
                        early_sunny_residual=round(early,2), late_sunny_residual=round(late,2),
                        night_change=round(night_change,2), loss_reduction=round(1-loss/flat_loss,3),
                        daily_points=[{'day':str(d),'sunny_residual':round(v,3),'night_residual':round(n,3)} for (d,v),n in zip(points,nights)])
        for group in runs(records, selected, station.step):
            result.add(station, 'temp_c', group[0].time, group[-1].time, 'sunlight-dependent temperature drift', 'exclude',
                       f"Sunny peer residual rises from {early:+.1f} to {late:+.1f} C while night residual changes {night_change:+.1f} C; quarantine sunlit values after estimated drift onset, with no defensible correction.",
                       'medium', **evidence)


def rain_blockage(result: Analysis, peers) -> None:
    for station in result.stations.values():
        records = sorted(station.index().values(),key=lambda r:r.time)
        zeros = runs(records, (r.value('rain_mm') == 0 for r in records), station.step)
        index = {r.time:i for i,r in enumerate(records)}
        for group in zeros:
            if len(group)*station.interval < 48*60:
                continue
            end_i = index[group[-1].time]
            following = records[end_i+1:end_i+1+max(1,int(60/station.interval))]
            following = [r for r in following if r.time-group[-1].time <= timedelta(hours=1)]
            pulse = sum(r.values['rain_mm'] for r in following)
            if pulse < 5:
                continue
            peer_pulse = []
            for peer in peers.select(station):
                vals = [peers.indices[peer.id][r.time].value('rain_mm') for r in following if r.time in peers.indices[peer.id]]
                if vals and all(math.isfinite(v) for v in vals):
                    peer_pulse.append(sum(vals))
            if len(peer_pulse) < 2 or pulse < max(5,5*med(peer_pulse)):
                continue
            missed = []
            for r in group:
                wet = peers.values(station,r,'rain_mm')
                if len(wet) >= 2 and sum(v>0 for v in wet)>=2 and r.values['temp_c'] > 2:
                    missed.append(r)
            if len(missed)*station.interval < 60:
                continue
            # Require substantial corroborated rainfall, not isolated stray tips.
            totals = []
            for peer in peers.select(station):
                vals = [peers.indices[peer.id][r.time].value('rain_mm') for r in group if r.time in peers.indices[peer.id]]
                totals.append(sum(v for v in vals if math.isfinite(v)))
            if sum(t >= 5 for t in totals)<2:
                continue
            nonzero = [r for r in following if r.values['rain_mm']>0]
            result.add(station, 'rain_mm', missed[0].time, nonzero[-1].time, 'rain blockage and delayed release', 'exclude',
                       f"Zeros span multiple warm peer-wet intervals then {pulse:.1f} mm arrives within an hour versus peer median {med(peer_pulse):.1f} mm; exclude uncertain accumulation and timing, without redistributing rainfall.",
                       'medium', release_mm=round(pulse,2), peer_release_mm=round(med(peer_pulse),2),
                       zero_run_start=stamp(group[0].time), first_corroborated_missed_rain=stamp(missed[0].time),
                       onset_uncertainty='blockage may have started earlier during dry weather')
