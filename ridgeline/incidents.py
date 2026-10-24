"""Bounded abrupt incidents and reference-group adjudication.

The majority is evidence under an explicit minority-fault assumption, not a
calibration truth. Equal groups are unresolved and do not become CSV 'keep'.
"""
from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import timedelta
from itertools import combinations
import math
from .config import DEFAULTS as CFG
from .model import mad, med, stamp


@dataclass
class Transition:
    time: object
    left: float
    right: float
    noise: float
    support: list[str] = field(default_factory=list)

    @property
    def delta(self):
        return self.right-self.left


@dataclass
class Incident:
    start: object
    end: object
    level_change: float
    recovered: bool
    transitions: list[Transition]

    def evidence(self, station):
        records=[r for r in station.records if self.start<=r.time<=self.end and not r.removed]
        return dict(status='recovered' if self.recovered else 'open at pack end',
                    recovery_utc=stamp(self.end+station.step) if self.recovered else None,
                    source_row_start=min(r.row for r in records),
                    source_row_end=max(r.row for r in records),
                    transitions=[dict(time_utc=stamp(t.time),change=round(t.delta,4),
                                      robust_noise=round(t.noise,4),peers=t.support) for t in self.transitions],
                    identification_assumption='faulty group smaller than stable reference group; common faults can escape detection')


def windows(times, values, boundary, hours, interval):
    """Physical-time windows; a gap cannot contribute stale observations."""
    a=bisect_left(times,boundary-timedelta(hours=hours))
    k=bisect_left(times,boundary)
    b=bisect_left(times,boundary+timedelta(hours=hours))
    left=[v for v in values[a:k] if math.isfinite(v)]
    right=[v for v in values[k:b] if math.isfinite(v)]
    minimum=max(3,hours*60/interval*CFG.required_window_coverage)
    return (left,right) if min(len(left),len(right))>=minimum else ([],[])


def reference_group(station, peers, channel, boundary, hours, logarithmic=False, omit=None):
    """Compare all pairs, not just each target against a contaminated median."""
    members=[station]+[s for s in peers.select(station) if s.id!=omit]
    indices=peers.indices
    adjacency={s.id:set() for s in members}
    def value(record):
        v=record.value(channel)
        return math.log(v+.5) if logarithmic and v>=0 else (v if not logarithmic else math.nan)
    tolerance=(.35 if hours>=72 else CFG.wind_group_tolerance_log) if logarithmic else CFG.pressure_group_tolerance_hpa
    for i,a in enumerate(members):
        for b in members[i+1:]:
            before=[]; after=[]
            for t,r in indices[a.id].items():
                if not boundary-timedelta(hours=hours)<=t<boundary+timedelta(hours=hours):continue
                other=indices[b.id].get(t)
                if not other:continue
                if logarithmic and max(r.value(channel),other.value(channel))<1:continue
                difference=value(r)-value(other)
                if math.isfinite(difference):(before if t<boundary else after).append(difference)
            required=max(3,hours*60/max(a.interval,b.interval)*CFG.required_window_coverage)
            if min(len(before),len(after))>=required and abs(med(after)-med(before))<tolerance:
                adjacency[a.id].add(b.id);adjacency[b.id].add(a.id)
    # Enumerate cliques in the tiny local graph (at most target + four peers).
    # A chain is not a quorum; overlapping equally large cliques are retained.
    ids=sorted(adjacency);groups=[]
    for size in range(len(ids),0,-1):
        groups=[list(group) for group in combinations(ids,size)
                if all(set(group)-{sid}<=adjacency[sid] for sid in group)]
        if groups:break
    if size==len(ids):return [],'no independently distinct changed group',groups
    if size<2:return [],'fewer than two coherent references',groups
    if any(station.id in group for group in groups):
        if all(station.id in group for group in groups):return [],'target belongs to stable majority',groups
        return [],'equally supported reference groups; trusted anchor required',groups
    # If all largest groups exclude the target, its minority status is stable.
    return groups[0],None,groups


def build_incidents(transitions, station, tolerance):
    """A confirmed return to the pre-fault level closes, rather than reopens."""
    incidents=[]; active=[];baseline=None;change=0
    for transition in sorted(transitions,key=lambda t:t.time):
        if not active:
            baseline=transition.left;active=[transition];change=transition.delta
        else:
            active.append(transition)
            if abs(transition.right-baseline)<=max(tolerance,abs(change)*.25):
                incidents.append(Incident(active[0].time,transition.time-station.step,change,True,active))
                active=[];baseline=None
            else:
                change=transition.right-baseline
    if active:incidents.append(Incident(active[0].time,station.bounds[1],change,False,active))
    return incidents


def abrupt_transitions(station, peers, channel, times, values, hours, minimum,
                       jump, noise_floor, logarithmic=False, omit=None, result=None):
    candidates=[]
    interval=(times[1]-times[0]).total_seconds()/60 if len(times)>1 else station.interval
    # Caller supplies regular hourly summaries for wind, actual rows for pressure.
    for i in range(1,len(times)):
        if times[i]-times[i-1]>timedelta(minutes=interval*1.5):continue
        if not math.isfinite(values[i]-values[i-1]) or abs(values[i]-values[i-1])<jump:continue
        left,right=windows(times,values,times[i],hours,interval)
        if not left:continue
        a,b=med(left),med(right)
        noise=max(noise_floor,1.4826*med([mad(left),mad(right)]))
        if abs(b-a)<max(minimum,CFG.robust_noise_multiplier*noise):continue
        if (b-a)*(values[i]-values[i-1])<=0:continue
        candidates.append(Transition(times[i],a,b,noise))
    # One transition per local discontinuity; robust windows reject most noise.
    accepted=[]
    for t in sorted(candidates,key=lambda t:(-abs(t.delta)/t.noise,t.time)):
        if any(abs(t.time-other.time)<timedelta(hours=hours) for other in accepted):continue
        support,reason,groups=reference_group(station,peers,channel,t.time,hours,logarithmic,omit)
        if support:
            t.support=support;accepted.append(t)
        elif result is not None and 'equally supported' in reason:
            result.abstain(station,channel,t.time,reason,groups=groups,
                           climate_policy='Do not assign a failed group or treat this as validated data; seek an independent reference before using cross-boundary changes.')
    return sorted(accepted,key=lambda t:t.time)
