"""A second, deliberately different weather generator and difficult cases.

No evaluate.weather()/network() fixture is reused. Storm arrival delays, altitude
dependent pressure response, nocturnal cold pools, direction-dependent wind
exposure and quantized rain are simulated. This is still synthetic, not field
truth. Diagnostics and reserved seeds share this new generator.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
def load_engine(root):
    global Analysis,Record,Station,CHANNELS,basic_checks,pressure_steps,wind_steps,daylight_temperature_drift,Peers
    sys.path.insert(0,str(root))
    from ridgeline.model import Analysis,Record,Station,CHANNELS
    from ridgeline.basic import basic_checks
    from ridgeline.advanced import pressure_steps,wind_steps,daylight_temperature_drift
    from ridgeline.peers import Peers


if __name__!='__main__':load_engine(ROOT)

START=datetime(2024,9,1)
SEEDS={'diagnostic':(8273,9282),'reserved':(10301,11412)}


def weather(seed,days=18,terrain=False):
    rng=random.Random(seed)
    interval=10 if seed%3 else 20
    result=Analysis({})
    for j in range(6):
        sid=f'Q{j}'
        result.stations[sid]=Station(sid,'Storm model '+sid,40+j*.055,-105+j*.04,
                                     1400+j*95,interval,START-timedelta(days=90))
    # Independent hourly state process, interpolated at logger cadence.
    state=[];p=0;w=2;cloud=.5;direction=230
    for hour in range(days*24+2):
        p=.985*p+rng.gauss(0,.45)
        w=.86*w+rng.gauss(0,.6)
        cloud=max(.05,min(.95,.92*cloud+.08*rng.random()+rng.gauss(0,.04)))
        direction=(direction+rng.gauss(0,9))%360
        state.append((p,w,cloud,direction))
    local=[0.]*6
    for i in range(int(days*1440/interval)):
        time=START+timedelta(minutes=i*interval)
        hour=i*interval/60;k=int(hour);fraction=hour-k
        latent=[a+(b-a)*fraction for a,b in zip(state[k][:3],state[k+1][:3])]
        direction=state[k][3]
        for j,s in enumerate(result.stations.values()):
            day=hour/24-j*.012
            solar_hour=(time.hour+time.minute/60+s.lon/15)%24
            sun=max(0,math.sin(math.pi*(solar_hour-7)/10)) if 7<solar_hour<17 else 0
            front=5*math.tanh((day-4)*6)-7*math.tanh((day-10)*5)+4*math.tanh((day-15)*4)
            storm=math.exp(-((day-4)/.3)**2)+math.exp(-((day-10)/.4)**2)
            local[j]=.9*local[j]+rng.gauss(0,.08)
            coldpool=(-3.5*(1-j/6)*max(0,1-sun*5) if 6<day<8 else 0)
            temp=17-.006*(s.elevation-1400)+8*sun-.4*front+local[j]+coldpool+rng.gauss(0,.12)
            pressure=1008*math.exp(-s.elevation/8200)+(latent[0]+front)*math.exp(-s.elevation/18000)+rng.gauss(0,.09)
            exposure=1+.08*math.cos(math.radians(direction+j*30))
            if terrain:exposure=1+.45*math.cos(math.radians(direction+j*57))
            wind=max(.1,(10+latent[1]+12*storm)*exposure*math.exp(rng.gauss(0,.08)))
            rain=.2 if storm>.2 and rng.random()<storm*.45 else 0
            humidity=min(99.5,max(15,72-27*sun+18*storm+rng.gauss(0,.8)))
            ghi=900*sun*(1-latent[2]*.65)
            if 12<day<14:humidity=99.2;ghi=0  # a legitimate shared fog episode
            values=dict(zip(CHANNELS,(temp,humidity,pressure,wind,direction,rain,ghi)))
            s.records.append(Record(i+2,time,time,values))
    return result


def spans(times,step):
    groups=[]
    for t in sorted(times):
        if not groups or t-groups[-1][-1]!=step:groups.append([])
        groups[-1].append(t)
    return [(g[0],g[-1]) for g in groups]


def score(result,truth,channel):
    counts=dict(tp=0,fp=0,fn=0,tn=0,collateral=0)
    events=[]
    for sid,s in result.stations.items():
        predicted={r.time for r in s.records if channel in r.excluded}
        actual={r.time for r in s.records if (sid,r.time) in truth}
        counts['tp']+=len(predicted&actual);counts['fp']+=len(predicted-actual)
        counts['fn']+=len(actual-predicted);counts['tn']+=len(s.records)-len(predicted|actual)
        counts['collateral']+=sum(len(r.excluded-{channel}) for r in s.records)
        for a,b in spans(actual,s.step):
            matches=[(x,y) for x,y in spans(predicted,s.step) if x<=b and y>=a]
            if matches:
                x,y=max(matches,key=lambda z:(min(b,z[1])-max(a,z[0])).total_seconds())
                events.append(dict(station=sid,detected=True,
                    iou=round((min(b,y)-max(a,x)+s.step)/(max(b,y)-min(a,x)+s.step),4),
                    onset_error_minutes=(x-a).total_seconds()/60,end_error_minutes=(y-b).total_seconds()/60))
            else:events.append(dict(station=sid,detected=False,iou=0))
    tp,fp,fn,tn=[counts[k] for k in ('tp','fp','fn','tn')]
    return dict(**counts,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,
                false_exclusions_per_1000_healthy=1000*fp/(fp+tn),events=events,
                unresolved=result.unresolved,
                flags=[f.as_row() for f in result.flags if f.action=='exclude'])


# Definitions are frozen before diagnostics; reserved seeds are not used to tune.
CASES=(
    ('healthy_pressure_storms','pressure_hpa',0,0,0),
    ('healthy_wind_exposure','wind_kmh',0,0,0),
    ('healthy_temperature_coldpool','temp_c',0,0,0),
    ('pressure_12h','pressure_hpa',7,7, .5),
    ('pressure_gap_open','pressure_hpa',7,7,3),
    ('pressure_gap_recovery','pressure_hpa',7,7,3),
    ('pressure_at_start','pressure_hpa',7,0,1.5),
    ('pressure_at_end','pressure_hpa',7,17.75,.25),
    ('pressure_faulty_majority','pressure_hpa',7,7,3),
    ('pressure_all_common','pressure_hpa',7,7,3),
    ('wind_12h','wind_kmh',.28,7,.5),
    ('wind_gap_recovery','wind_kmh',.28,7,3),
    ('wind_at_start','wind_kmh',.28,0,1.5),
    ('wind_at_end','wind_kmh',.28,17.75,.25),
    ('wind_faulty_majority','wind_kmh',.28,7,3),
    ('burst_in_storm','temp_c',22,4,2/24),
    ('drift_with_weather','temp_c',.25,14,28),
)


def run(split,engine_root=ROOT):
    rows=[]
    for seed in SEEDS[split]:
        for name,channel,size,onset,duration in CASES:
            result=weather(seed,42 if name=='drift_with_weather' else 18,terrain=name=='healthy_wind_exposure')
            begin=START+timedelta(days=onset)
            end=begin+timedelta(days=duration)
            targets={'Q2'}
            if 'faulty_majority' in name:targets={'Q0','Q1','Q2','Q3'}
            if name=='pressure_all_common':targets=set(result.stations)
            truth=set()
            for sid,s in result.stations.items():
                for r in s.records:
                    faulty=size!=0 and sid in targets and begin<=r.time<end
                    if name=='drift_with_weather':faulty=faulty and r.values['ghi_wm2']>100
                    if faulty:
                        truth.add((sid,r.time))
                        if channel=='wind_kmh':r.values[channel]*=size
                        elif name=='drift_with_weather':r.values[channel]+=size*(r.time-begin).total_seconds()/86400
                        else:r.values[channel]+=size
            # Remove only target records, with real source-row identities kept.
            if 'gap' in name:
                boundary=begin if name.endswith('open') else end
                station=result.stations['Q2']
                station.records=[r for r in station.records if not boundary-timedelta(hours=1)<=r.time<boundary+timedelta(hours=1)]
            peers=Peers(result)
            basic_checks(result,peers)
            if channel=='pressure_hpa':pressure_steps(result,peers)
            elif channel=='wind_kmh':wind_steps(result,peers)
            elif name=='drift_with_weather':daylight_temperature_drift(result,peers)
            row=dict(case=name,seed=seed,channel=channel,
                     identifiable=not any(x in name for x in ('at_start','at_end','majority','all_common')),
                     **score(result,truth,channel))
            rows.append(row)
            print(f"{split} {seed} {name}: tp={row['tp']} fp={row['fp']} fn={row['fn']} unresolved={len(row['unresolved'])}",flush=True)
    aggregate={}
    for name,_,_,_,_ in CASES:
        group=[r for r in rows if r['case']==name]
        totals={k:sum(r[k] for r in group) for k in ('tp','fp','fn','tn','collateral')}
        tp,fp,fn,tn=[totals[k] for k in ('tp','fp','fn','tn')]
        aggregate[name]=dict(**totals,precision=tp/(tp+fp) if tp+fp else None,
                             recall=tp/(tp+fn) if tp+fn else None,
                             unresolved_cases=sum(bool(r['unresolved']) for r in group))
    return dict(split=split,seeds=SEEDS[split],scenarios=len(rows),aggregate=aggregate,cases=rows,
                scope='Different synthetic weather model; still no independent field calibration truth.',
                benchmark_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                source_hashes={p.name:hashlib.sha256(p.read_text(encoding='utf-8').encode()).hexdigest() for p in sorted((engine_root/'ridgeline').glob('*.py'))})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split',choices=SEEDS,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--engine-root',type=Path,default=ROOT,help='Optional separate checkout, for reproducible before/after comparison')
    args=parser.parse_args()
    load_engine(args.engine_root)
    data=run(args.split,args.engine_root)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
