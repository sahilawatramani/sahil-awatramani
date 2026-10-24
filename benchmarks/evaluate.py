"""Seeded, labeled weather simulations; not an estimate of field accuracy.

Development seeds and evaluation seeds are disjoint. Scenario definitions and
metrics are fixed in source. Evaluate once after development; publish failures
alongside successes rather than tuning against the evaluation results.
"""
import argparse
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ridgeline.model import Analysis, CHANNELS, Record, Station, stamp
from ridgeline.basic import basic_checks, solar_elevation
from ridgeline.advanced import pressure_steps, wind_steps, daylight_temperature_drift
from ridgeline.peers import Peers

START = datetime(2024, 5, 1)
SEEDS = {'development': [1709, 2712, 3907], 'evaluation': [4903, 5904, 6917]}


def weather(seed, days=24):
    rng = random.Random(seed)
    interval = 10 if seed % 2 else 20
    stations = {}
    for j in range(6):
        sid = f'N{j}'
        stations[sid] = Station(sid, f'Synthetic {j}', 39.8+j*.06, -105+j*.035,
                                1500+j*85, interval, START-timedelta(days=90))
    common = 0
    local = [0.]*6
    for i in range(int(days*1440/interval)):
        t = START+timedelta(minutes=i*interval)
        d = i*interval/1440
        common = .95*common+rng.gauss(0, .12)
        front = 4*math.tanh((d-9)*3)-3*math.tanh((d-12)*3)
        for j, s in enumerate(stations.values()):
            local[j] = .94*local[j]+rng.gauss(0, .07)
            sun = max(0, math.sin(math.radians(solar_elevation(t-s.step/2, s.lat, s.lon))))
            values = dict(zip(CHANNELS, (
                12+9*sun+front-j*.45+common+local[j]+rng.gauss(0,.12),
                62-30*sun+3*common+rng.gauss(0,.7),
                840-j*8+7*math.sin(d*.55)+front+common+local[j]*.15+rng.gauss(0,.06),
                max(.2, (12+6*math.sin(d*2)+4*math.sin(d*8)+common)*(1+j*.07)+local[j]+rng.gauss(0,.2)),
                (220+70*math.sin(d)+rng.gauss(0,4))%360,
                .2 if 9 < d < 9.5 and i%3==0 else 0,
                max(0, 950*sun*(.8+.15*math.sin(d*2))+rng.gauss(0,2)) if sun else 0)))
            s.records.append(Record(i+2,t,t,values))
    return Analysis(stations)


def intervals(times, step):
    groups = []
    for t in sorted(times):
        if not groups or t-groups[-1][-1] != step:
            groups.append([])
        groups[-1].append(t)
    return [(g[0],g[-1]) for g in groups]


def score(result, truth, channel):
    tp=fp=fn=tn=collateral=0
    events=[]
    for sid,s in result.stations.items():
        predicted = {r.time for r in s.records if channel in r.excluded}
        actual = {r.time for r in s.records if (sid,r.time) in truth}
        tp+=len(predicted & actual); fp+=len(predicted-actual)
        fn+=len(actual-predicted); tn+=len(s.records)-len(predicted|actual)
        collateral+=sum(len(r.excluded-{channel}) for r in s.records)
        predicted_intervals=intervals(predicted,s.step)
        for a,b in intervals(actual,s.step):
            matches=[(x,y) for x,y in predicted_intervals if x<=b and y>=a]
            if matches:
                x,y=max(matches,key=lambda z:(min(b,z[1])-max(a,z[0])).total_seconds())
                overlap=(min(b,y)-max(a,x)+s.step).total_seconds()
                union=(max(b,y)-min(a,x)+s.step).total_seconds()
                events.append({'detected':True,'iou':round(overlap/union,4),
                               'onset_error_minutes':(x-a).total_seconds()/60,
                               'end_error_minutes':(y-b).total_seconds()/60})
            else:
                events.append({'detected':False,'iou':0})
    return dict(tp=tp,fp=fp,fn=fn,tn=tn,
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,
                false_exclusions_per_1000_healthy=1000*fp/(fp+tn) if fp+tn else 0,
                collateral_channel_exclusions=collateral,events=events,
                unresolved_checks=len(result.unresolved) if hasattr(result,'unresolved') else 0)


def run(split):
    output=[]
    # The small/marginal faults deliberately expose sensitivity limits.
    cases=[('pressure_short','pressure_hpa',pressure_steps,4.5,1),
           ('pressure_recovery','pressure_hpa',pressure_steps,7,4),
           ('pressure_persistent','pressure_hpa',pressure_steps,-6,24),
           ('wind_short','wind_kmh',wind_steps,.3,1),
           ('wind_recovery','wind_kmh',wind_steps,.35,3),
           ('wind_persistent','wind_kmh',wind_steps,2.5,24),
           ('burst_short','temp_c',basic_checks,18,1/24),
           ('burst_long','temp_c',basic_checks,-20,6/24),
           ('frozen','temp_c',basic_checks,6.125,2),
           ('healthy_front','temp_c',basic_checks,0,0),
           ('healthy_pressure','pressure_hpa',pressure_steps,0,0),
           ('healthy_wind','wind_kmh',wind_steps,0,0),
           ('heterogeneous_wind','wind_kmh',wind_steps,0,0),
           ('healthy_saturated','rh_pct',basic_checks,0,0),
           ('local_warm_weather','temp_c',basic_checks,8,2/24),
           ('small_pressure','pressure_hpa',pressure_steps,2,3),
           ('shared_pressure','pressure_hpa',pressure_steps,7,12),
           ('ambiguous_pressure','pressure_hpa',pressure_steps,7,12),
           ('sunny_drift','temp_c',daylight_temperature_drift,.24,28)]
    for seed in SEEDS[split]:
        for name,channel,detector,size,duration in cases:
            result=weather(seed,42 if name=='sunny_drift' else 24)
            target=f'N{seed%6}'
            targets={target}
            if name=='shared_pressure':targets={'N1','N4'}
            if name=='ambiguous_pressure':
                # An unanchored 2:2 network cannot identify the bad half.
                result.stations={k:v for k,v in result.stations.items() if k in ('N0','N1','N2','N3')}
                targets={'N1','N2'}
            begin=START+timedelta(days=7,hours=seed%17)
            end=begin+timedelta(days=duration)
            truth=set()
            for sid,s in result.stations.items():
                for r in s.records:
                    if name=='heterogeneous_wind':
                        day=(r.time-START).total_seconds()/86400
                        phase=int(sid[1:])*1.3
                        r.values['wind_kmh']*=1+.35*math.sin(day*1.7+phase)
                    if name=='healthy_saturated' and 8<=(r.time-START).total_seconds()/86400<10:
                        r.values['rh_pct']=99.2;r.values['ghi_wm2']=0
                    faulty=sid in targets and begin<=r.time<end and size!=0
                    if name=='sunny_drift':
                        faulty=sid in targets and r.time>=START+timedelta(days=14) and r.values['ghi_wm2']>100
                    if faulty:
                        truth.add((sid,r.time))
                        if name.startswith('wind'):r.values[channel]*=size
                        elif name=='frozen':r.values[channel]=size
                        elif name=='sunny_drift':r.values[channel]+=max(0,(r.time-START).total_seconds()/86400-14)*size
                        else:r.values[channel]+=size
            if name=='local_warm_weather':truth=set()  # genuine, bounded local +8 C anomaly
            detector(result,Peers(result))
            metrics=score(result,truth,channel)
            output.append(dict(case=name,seed=seed,channel=channel,targets=sorted(targets),
                               ambiguous=name=='ambiguous_pressure',**metrics))
            print(f"{split} {seed} {name}: precision={metrics['precision']} recall={metrics['recall']} fp={metrics['fp']}",flush=True)
    aggregate={}
    for name,_,_,_,_ in cases:
        rows=[c for c in output if c['case']==name]
        tp,fp,fn,tn=[sum(c[k] for c in rows) for k in ('tp','fp','fn','tn')]
        events=[e for c in rows for e in c['events']]
        aggregate[name]=dict(tp=tp,fp=fp,fn=fn,tn=tn,
                             precision=tp/(tp+fp) if tp+fp else None,
                             recall=tp/(tp+fn) if tp+fn else None,
                             event_recall=sum(e['detected'] for e in events)/len(events) if events else None,
                             mean_event_iou=sum(e['iou'] for e in events)/len(events) if events else None,
                             false_exclusions_per_1000_healthy=1000*fp/(fp+tn),
                             unresolved_checks=sum(c['unresolved_checks'] for c in rows))
    detector_names=('model','config','peers','basic','advanced','incidents','temperature_validation')
    detector_hash=hashlib.sha256('\n'.join((ROOT/'ridgeline'/f'{name}.py').read_text() for name in detector_names).encode()).hexdigest()
    return {'split':split,'seeds':SEEDS[split],'detector_sha256':detector_hash,
            'benchmark_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'Synthetic stress tests only; unknown field precision/recall; no hidden organizer labels.',
            'scenarios':len(output),'aggregate':aggregate,'cases':output}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split',choices=SEEDS,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run(args.split)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
