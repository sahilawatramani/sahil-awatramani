"""Conservative peer-supported incident detection; all thresholds documented."""
from __future__ import annotations
from collections import defaultdict
from bisect import bisect_left
from datetime import datetime, timedelta
import math
from .model import Analysis, correlation, mad, med, runs, stamp


def pressure_steps(result: Analysis, peers) -> None:
    """Detect abrupt sustained pressure offsets, including a supported recovery."""
    from .config import DEFAULTS as cfg
    from .incidents import abrupt_transitions, build_incidents
    with result.stage():
        for station in result.stations.values():
            records=sorted(station.index().values(),key=lambda r:r.time)
            times=[r.time for r in records]
            values=[peers.pressure_residual(station,r) for r in records]
            transitions=abrupt_transitions(station,peers,'pressure_hpa',times,values,
                                          cfg.pressure_window_hours,cfg.pressure_shift_hpa,
                                          cfg.pressure_jump_hpa,.15,result=result)
            for incident in build_incidents(transitions,station,1.5):
                evidence=incident.evidence(station)
                evidence.update(peer_change_hpa=round(incident.level_change,3),
                                peers=incident.transitions[0].support,
                                onset_method='adjacent discontinuity, 12-hour residual windows and pairwise reference groups')
                recovery='ends at a corroborated return to the prior residual' if incident.recovered else 'continues to pack end without observed recovery'
                result.add(station,'pressure_hpa',incident.start,incident.end,'pressure calibration step','exclude',
                           f"Target-minus-peer pressure shifts {incident.level_change:+.1f} hPa against a larger coherent reference group and {recovery}; exclude without assuming an exact calibration offset.",
                           **evidence)


def long_wind_profile(station, peers, omit=None):
    """Fit without mutating masks, so reference omissions share one baseline."""
    records = sorted(station.index().values(), key=lambda r: r.time)
    hourly = defaultdict(list)
    for r in records:
        reference = med(peers.values(station, r, 'wind_kmh', omit=omit))
        value = r.value('wind_kmh')
        if math.isfinite(value) and reference >= 5 and value >= 0:
            hourly[r.time.replace(minute=0)].append(math.log((value + .5) / (reference + .5)))
    points = sorted((t, med(v)) for t,v in hourly.items() if len(v) >= max(1, 20/station.interval))
    if len(points) < 24 * 14:
        return None
    daily = defaultdict(list)
    for t,v in points:
        daily[t.date()].append(v)
    days = sorted((d, med(v)) for d,v in daily.items() if len(v) >= 6)
    if len(days) < 21:
        return None
    middle = med(v for _,v in days)
    baseline_loss = sum(abs(v-middle) for _,v in days)
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
        return None
    coarse = datetime.combine(days[k][0], datetime.min.time())
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
    return {'onset':min(splits)[1] if splits else coarse,'ratio_factor':round(factor,3),
            'loss_reduction':round(1-loss/baseline_loss,3)}


def wind_profile(station, peers, omit=None):
    """Multiple sustained scale changes; short middle episodes need no 7-day split."""
    from .config import DEFAULTS as cfg
    from .incidents import abrupt_transitions, build_incidents, reference_group, Transition
    records=sorted(station.index().values(),key=lambda r:r.time)
    hourly=defaultdict(list); raw=[]
    for r in records:
        reference=med(peers.values(station,r,'wind_kmh',omit=omit))
        value=r.value('wind_kmh')
        ratio=math.log((value+.5)/(reference+.5)) if math.isfinite(value) and value>=0 and reference>=1 else math.nan
        raw.append((r.time,ratio))
        if math.isfinite(ratio):hourly[r.time.replace(minute=0,second=0,microsecond=0)].append(ratio)
    points=sorted((t,med(v)) for t,v in hourly.items() if len(v)>=max(1,30/station.interval))
    if len(points)<48:return None
    times=[t for t,v in points]; values=[v for t,v in points]
    transitions=abrupt_transitions(station,peers,'wind_kmh',times,values,
                                  cfg.wind_window_hours,cfg.wind_log_shift,.25,.055,True,omit)
    # Short-event claims need a stable proportional relationship before entry.
    # Highly variable terrain/exposure ratios need the longer-regime evidence.
    transitions=[t for t in transitions if mad([v for tt,v in points
                    if t.time-timedelta(days=3)<=tt<t.time])<=.15]
    # A second time scale retains sensitivity when hourly local wind is noisy.
    # It is corroborated against pairwise 72-hour reference changes before use.
    long_fit=long_wind_profile(station,peers,omit)
    if long_fit and not any(abs(t.time-long_fit['onset'])<=timedelta(days=3) for t in transitions):
        support,reason,groups=reference_group(station,peers,'wind_kmh',long_fit['onset'],72,True,omit)
        if support:
            before=[v for t,v in points if long_fit['onset']-timedelta(days=3)<=t<long_fit['onset']]
            after=[v for t,v in points if long_fit['onset']<=t<long_fit['onset']+timedelta(days=3)]
            transitions.append(Transition(long_fit['onset'],med(before),med(after),max(.055,mad(before)),support))
    # Hourly screening, then raw-cadence boundary refinement using clean levels.
    for transition in transitions:
        nearby=[(t,v) for t,v in raw if abs(t-transition.time)<=timedelta(hours=3) and math.isfinite(v)]
        candidates=[t for t,v in nearby if abs(t-transition.time)<=timedelta(hours=1)]
        if candidates:
            transition.time=min(candidates,key=lambda boundary:(
                sum(abs(v-(transition.left if t<boundary else transition.right)) for t,v in nearby),boundary))
    incidents=build_incidents(transitions,station,.22)
    if not incidents:return None
    dominant=max(incidents,key=lambda i:abs(i.level_change))
    return dict(onset=dominant.start,ratio_factor=round(math.exp(dominant.level_change),3),
                incidents=incidents,points=[dict(time_utc=stamp(t),log_ratio=round(v,4)) for t,v in points])


def omission_check(station, peers, profile, initial):
    """Empirical sensitivity, not a statistical confidence interval."""
    checks=[]
    references=peers.select(station)
    if len(references) >= 3:
        for reference in references:
            fit=profile(station,peers,omit=reference.id)
            checks.append({'omitted_peer':reference.id,'detected':fit is not None,
                           'onset':stamp(fit['onset']) if fit else None})
    onsets=[initial['onset']]+[datetime.fromisoformat(c['onset']) for c in checks if c['detected']]
    return {'peer_omissions':checks,'omission_detections':sum(c['detected'] for c in checks),
            'omission_tests':len(checks),'tested_onset_start':stamp(min(onsets)),
            'tested_onset_end':stamp(max(onsets)),
            'uncertainty_kind':'reference sensitivity only, not a statistical confidence interval'}


def wind_steps(result: Analysis, peers) -> None:
    with result.stage():
        for station in result.stations.values():
            fit=wind_profile(station,peers)
            if not fit:continue
            sensitivity=omission_check(station,peers,wind_profile,fit)
            for incident in fit['incidents']:
                evidence=incident.evidence(station)
                evidence.update(sensitivity)
                evidence.update(ratio_factor=round(math.exp(incident.level_change),3),
                                nominal_onset=stamp(incident.start),peers=incident.transitions[0].support,
                                hourly_points=fit['points'])
                # Match nearby opening boundaries only; a different incident's
                # dominant split must not extend this bounded event.
                evidence['tested_onset_start']=stamp(min([incident.start]+[
                    datetime.fromisoformat(c['onset']) for c in sensitivity['peer_omissions'] if c['detected']
                    and abs(datetime.fromisoformat(c['onset'])-incident.start)<=timedelta(hours=12)]))
                status='a supported return closes the interval' if incident.recovered else 'no recovery is observed before pack end'
                sensitivity_note='' if sensitivity['omission_tests'] else ', with reference sensitivity untested because fewer than three peers are available'
                onset=datetime.fromisoformat(evidence['tested_onset_start'])
                evidence['nominal_source_row_start']=evidence['source_row_start']
                evidence['source_row_start']=min(r.row for r in station.records if onset<=r.time<=incident.end and not r.removed)
                evidence['boundary_policy']='hold from earliest nearby reference-tested onset; nominal cadence refinement is not a known physical onset'
                result.add(station,'wind_kmh',onset,incident.end,'wind scale discontinuity','exclude',
                           f"Wind ratio changes by factor {evidence['ratio_factor']:.2f} against a larger coherent reference group and {status}{sensitivity_note}; exclude pending instrument/configuration verification.",
                           'medium',**evidence)


def temperature_profile(station, peers, omit=None):
    if station.id in peers.disputed:
        return None
    days = defaultdict(list)
    for r in station.index().values():
        residual = peers.residual(station, r, 'temp_c', omit=omit)
        if math.isfinite(residual):
            days[r.time.date()].append((r, residual))
    points, nights = [], []
    for day, values in sorted(days.items()):
        daylight = [v for r,v in values if r.values['ghi_wm2'] > 300]
        dark = [v for r,v in values if r.values['ghi_wm2'] < 5]
        if len(daylight) * station.interval >= 120 and len(dark) * station.interval >= 120:
            points.append((day, med(daylight))); nights.append(med(dark))
    if len(points) < 28:
        return None
    x = [(d-points[0][0]).days for d,_ in points]
    y = [v for _,v in points]
    early, late = med(y[:7]), med(y[-7:])
    night_change = med(nights[-7:])-med(nights[:7])
    if late-early < 2.5 or abs(night_change) > 1.5 or correlation(x,y) < .65:
        return None
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
        return None
    onset = datetime.combine(points[k][0], datetime.min.time())
    return dict(onset=onset,onset_estimate=stamp(onset), drift_c_per_day=round(slope,3),
                early_sunny_residual=round(early,2), late_sunny_residual=round(late,2),
                night_change=round(night_change,2), loss_reduction=round(1-loss/flat_loss,3),
                daily_points=[{'day':str(d),'sunny_residual':round(v,3),'night_residual':round(n,3)} for (d,v),n in zip(points,nights)])


def daylight_temperature_drift(result: Analysis, peers) -> None:
    from .temperature_validation import matched_validation
    pending=[]
    for station in result.stations.values():
        fit=temperature_profile(station,peers)
        if fit:
            sensitivity=omission_check(station,peers,temperature_profile,fit)
            fit['matched_time_block_validation']=matched_validation(station,peers)
            fit['climate_policy']='Hold GHI>100 windows from the full-model onset as a precaution; early held samples may be valid; retained nights do not support complete daily means.'
            pending.append((station,fit,sensitivity))
    # Commit masks after every station is fitted, avoiding inventory-order effects.
    for station,fit,sensitivity in pending:
        records = sorted(station.index().values(),key=lambda r:r.time)
        selected = [r.time >= fit['onset'] and r.values['ghi_wm2'] > 100 and 'temp_c' not in r.excluded for r in records]
        evidence={k:v for k,v in fit.items() if k!='onset'}
        evidence.update(sensitivity)
        evidence['peers']=[s.id for s in peers.select(station)]
        for group in runs(records, selected, station.step):
            result.add(station, 'temp_c', group[0].time, group[-1].time, 'sunlight-dependent temperature drift', 'exclude',
                       f"Sunny residual rises from {fit['early_sunny_residual']:+.1f} to {fit['late_sunny_residual']:+.1f} C; cautiously hold sunlit values after the reference-sensitive model onset, retaining nights and applying no numerical correction.",
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
