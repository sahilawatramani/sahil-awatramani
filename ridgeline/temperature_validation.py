"""Independent time-block checks for the gradual temperature hypothesis.

The first week is an assumed reference period, never a calibrated truth. The
second week is held out. Matching UTC hour and observed sunlight controls part
of the diurnal/exposure mix; it does not control every weather or terrain effect.
"""
from collections import defaultdict
from datetime import timedelta
import math
from .model import mad, med, stamp


def matched_validation(station, peers, omit=None):
    observations=[]
    for r in sorted(station.index().values(),key=lambda r:r.time):
        value=peers.residual(station,r,'temp_c',omit=omit)
        if math.isfinite(value) and math.isfinite(r.value('ghi_wm2')):
            observations.append((r,value))
    if not observations:return {}
    start=observations[0][0].time
    train_end=start+timedelta(days=7)
    holdout_end=start+timedelta(days=14)
    last_week=observations[-1][0].time-timedelta(days=7)
    cells=defaultdict(list);hours=defaultdict(list)
    for r,v in observations:
        if r.time<train_end:
            hour=r.time.hour//2;sun=int(max(0,r.values['ghi_wm2'])//200)
            cells[hour,sun].append(v);hours[hour].append(v)
    adjusted=[]
    for r,v in observations:
        hour=r.time.hour//2;sun=int(max(0,r.values['ghi_wm2'])//200)
        matches=cells[hour,sun]
        if len(matches)<max(3,60/station.interval):matches=hours[hour]
        if len(matches)>=3:adjusted.append((r,v-med(matches)))
    heldout=[v for r,v in adjusted if train_end<=r.time<holdout_end and r.values['ghi_wm2']>300]
    late=[v for r,v in adjusted if r.time>=last_week and r.values['ghi_wm2']>300]
    nights=[v for r,v in adjusted if r.time>=last_week and r.values['ghi_wm2']<5]
    daily=defaultdict(list)
    for r,v in adjusted:
        if r.values['ghi_wm2']>300:daily[r.time.date()].append(v)
    if not heldout or not late:return {}
    baseline=med(heldout)
    threshold=max(1.5,3*1.4826*mad(heldout))
    days=sorted((d,med(v)) for d,v in daily.items() if len(v)*station.interval>=120)
    departures=[]
    for i in range(len(days)-2):
        group=days[i:i+3]
        if (group[-1][0]-group[0][0]).days==2 and all(v-baseline>threshold for _,v in group):
            departures.append(str(group[0][0]))
    return dict(training_start=stamp(start),training_end_exclusive=stamp(train_end),
                heldout_end_exclusive=stamp(holdout_end),
                method='first-week median residual cells by 2-hour UTC bin and 200 W/m2 GHI bin; sparse cells fall back to hour',
                heldout_sunny_bias_c=round(baseline,3),heldout_sunny_mae_c=round(med(abs(v) for v in heldout),3),
                late_sunny_change_c=round(med(late)-baseline,3),late_night_bias_c=round(med(nights),3) if nights else None,
                departure_threshold_c=round(threshold,3),
                first_three_day_departure=departures[0] if departures else None,
                limits='assumes the first week is serviceable; weather matching is incomplete; departure date is not a physical fault onset')
