"""Cross-check submitted decisions using separate raw CSV/NMEA calculations.

No detector, model fixture or production loader is imported. Uses submitted
clock provenance to construct UTC, then independently verifies accounting,
duplicates, bounds, direct faults, peer changes and drift-policy sensitivity.
This is a consistency review, not independently labeled calibration truth.
"""
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timedelta
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median

CHANNELS=('temp_c','rh_pct','pressure_hpa','wind_kmh','wind_dir_deg','rain_mm','ghi_wm2')
DIRECT={'invalid value','sensor frozen','isolated temperature spike','temperature error burst','humidity saturation failure'}


def mid(values):
    values=[v for v in values if math.isfinite(v)]
    return median(values) if values else None


def km(a,b):
    x,y=math.radians(a['lat']),math.radians(b['lat'])
    q=math.sin((x-y)/2)**2+math.cos(x)*math.cos(y)*math.sin(math.radians(a['lon']-b['lon'])/2)**2
    return 12742*math.asin(min(1,math.sqrt(q)))


def gps_review(path):
    counts=Counter();offsets=Counter();positions=[];gga_positions=[];jitter=[]
    for line in path.read_text(encoding='utf-8-sig').splitlines() if path.exists() else []:
        try:
            logger,payload=line.split(',',1);body,checksum=payload[1:].split('*')
            xor=0
            for char in body:xor^=ord(char)
            if xor!=int(checksum[:2],16):counts['checksum_rejected']+=1;continue
            parts=body.split(',')
            def coordinate(value,hemisphere):
                n=float(value);result=int(n/100)+(n%100)/60
                return -result if hemisphere in ('S','W') else result
            if parts[0].endswith('GGA'):
                if int(parts[6]) in (1,2,4,5) and int(parts[7])>=4 and 0<float(parts[8])<=5 and parts[10]=='M':
                    gga_positions.append((coordinate(parts[2],parts[3]),coordinate(parts[4],parts[5]),float(parts[9])))
                    counts['quality_admitted_gga']+=1
                else:counts['quality_rejected_gga']+=1
                continue
            if not parts[0].endswith('RMC'):continue
            if parts[2]!='A' or (len(parts)>12 and parts[12] in ('N','E','M','S')):
                counts['inactive_or_untrusted_rmc']+=1;continue
            day=datetime.strptime(parts[9],'%d%m%y')
            clock=parts[1];hour=int(clock[:2]);minute=int(clock[2:4]);second=float(clock[4:])
            utc=day+timedelta(hours=hour,minutes=minute,seconds=second)
            offset=(datetime.fromisoformat(logger)-utc).total_seconds()
            offsets[str(round(offset/60)*60)]+=1
            jitter.append(abs(offset-round(offset/60)*60))
            positions.append((coordinate(parts[3],parts[4]),coordinate(parts[5],parts[6])))
            counts['active_checksum_valid_rmc']+=1
        except (ValueError,IndexError):counts['malformed_rejected']+=1
    return dict(counts=counts,logger_minus_rmc_seconds=offsets,
                median_lat=mid(p[0] for p in positions),median_lon=mid(p[1] for p in positions),
                maximum_receipt_jitter_seconds=max(jitter,default=None),
                gga_median_lat=mid(p[0] for p in gga_positions),gga_median_lon=mid(p[1] for p in gga_positions),
                gga_median_altitude_msl=mid(p[2] for p in gga_positions))


def review(pack,submission):
    audit=json.loads((submission/'audit.json').read_text(encoding='utf-8'))
    flags=list(csv.DictReader((submission/'flags.csv').open(encoding='utf-8',newline='')))
    for flag in flags:
        flag['a']=datetime.fromisoformat(flag['start_utc']);flag['b']=datetime.fromisoformat(flag['end_utc'])
    stored=audit['flags']
    def evidence(flag):
        e=next(f['evidence'] for f in stored if all(f[k]==flag[k] for k in ('station_id','channel','start_utc','end_utc','issue')))
        return audit['diagnostics'][e['diagnostic_ref']] if 'diagnostic_ref' in e else e
    sites={r['station_id']:r for r in csv.DictReader((pack/'stations.csv').open(encoding='utf-8-sig',newline=''))}
    for site in sites.values():
        for key in ('lat','lon','elevation_m'):site[key]=float(site[key])
        site['step']=timedelta(minutes=int(site['logger_interval_min']))
    records={};raw_counts={};removed={};conflicts={}
    for sid in sites:
        index={};raw=list(csv.DictReader((pack/'data'/f'{sid}.csv').open(encoding='utf-8-sig',newline='')))
        raw_counts[sid]=len(raw);removed[sid]=0;conflicts[sid]=0
        for row,source in enumerate(raw,2):
            t=datetime.fromisoformat(source['timestamp_utc']);corrected=t
            for flag in flags:
                if flag['station_id']==sid and flag['issue']=='logger clock offset':
                    e=evidence(flag)
                    if e['source_line']<=row<=e['source_end_line']:corrected=t+timedelta(seconds=e['offset_seconds'])
            values={c:float(source[c]) for c in CHANNELS}
            if corrected in index:
                if values==index[corrected]['values']:removed[sid]+=1
                else:conflicts[sid]+=1
            else:index[corrected]=dict(time=corrected,raw=t,row=row,values=values)
        records[sid]=index
    disputed={f['station_id'] for f in flags if f['issue']=='location mismatch'}
    def peers(sid):
        if sid in disputed:return []
        site=sites[sid];choices=[]
        for other,s in sites.items():
            d=km(site,s);z=abs(site['elevation_m']-s['elevation_m'])
            if other!=sid and other not in disputed and d<=180 and z<=700:choices.append((d+z/50,other))
        return [other for _,other in sorted(choices)[:4]]
    def usable(sid,time,channel):
        return not any(f['station_id']==sid and f['channel'] in (channel,'all') and f['action']=='exclude'
                       and f['issue'] in DIRECT and f['a']<=time<=f['b'] for f in flags)
    def pair(sid,other,channel,a,b,condition=lambda r:True):
        vals=[]
        for t,r in records[sid].items():
            peer=records[other].get(t)
            if a<=t<b and peer and condition(r) and usable(other,t,channel) and usable(sid,t,channel):
                v=r['values'][channel];w=peer['values'][channel]
                if channel=='wind_kmh':v=math.log((v+.5)/(w+.5))
                else:v-=w
                if math.isfinite(v):vals.append(v)
        return vals
    ledger=[]
    for flag in flags:
        sid=flag['station_id'];channel=flag['channel']
        selected=[r for t,r in records[sid].items() if flag['a']<=t<=flag['b']]
        row={k:flag[k] for k in ('station_id','channel','start_utc','end_utc','issue','action')}
        row.update(observed_unique_samples=len(selected),expected_slots=int((flag['b']-flag['a'])/sites[sid]['step'])+1)
        if channel in CHANNELS and selected:
            values=[r['values'][channel] for r in selected]
            row.update(minimum=min(values),maximum=max(values),median=mid(values),source_first_row=min(r['row'] for r in selected),source_last_row=max(r['row'] for r in selected))
            if flag['issue']=='sensor frozen':row['distinct_values']=len(set(values))
            if channel=='rh_pct':row['above_100_samples']=sum(v>100 for v in values)
            if flag['issue']=='sunlight-dependent temperature drift':row['night_or_low_sun_samples_held']=sum(r['values']['ghi_wm2']<=100 for r in selected)
        if flag['issue'] in ('pressure calibration step','wind scale discontinuity'):
            row['independent_pair_changes']=[]
            for hours in (12,48,72):
                for other in peers(sid):
                    before=pair(sid,other,channel,flag['a']-timedelta(hours=hours),flag['a'])
                    after=pair(sid,other,channel,flag['a'],flag['a']+timedelta(hours=hours))
                    if before and after:
                        delta=mid(after)-mid(before)
                        row['independent_pair_changes'].append(dict(peer=other,window_hours=hours,before_n=len(before),after_n=len(after),
                             change=round(math.exp(delta) if channel=='wind_kmh' else delta,4)))
        if flag['issue']=='coherent mountain cold':
            choices=sorted((km(sites[sid],s)+abs(sites[sid]['elevation_m']-s['elevation_m'])/50,other)
                           for other,s in sites.items() if other!=sid and other not in disputed and km(sites[sid],s)<=180 and abs(sites[sid]['elevation_m']-s['elevation_m'])<=2500)[:4]
            a=[];b=[]
            for t,r in records[sid].items():
                refs=[records[other][t]['values']['temp_c'] for _,other in choices if t in records[other] and usable(other,t,'temp_c')]
                if len(refs)>=2:a.append(r['values']['temp_c']);b.append(mid(refs))
            ma,mb=sum(a)/len(a),sum(b)/len(b)
            corr=sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))
            row['independent_cold_support']=dict(paired_samples=len(a),correlation=round(corr,4),median_offset_c=round(mid(x-y for x,y in zip(a,b)),3),
                                                elevation_above_reference_median_m=sites[sid]['elevation_m']-mid(sites[other]['elevation_m'] for _,other in choices))
        if flag['issue']=='rain blockage and delayed release':
            e=evidence(flag);zero_start=datetime.fromisoformat(e['zero_run_start'])
            first_nonzero=min(t for t,r in records[sid].items() if t>=zero_start and r['values']['rain_mm']>0)
            release=[r for t,r in records[sid].items() if first_nonzero<=t<first_nonzero+timedelta(hours=1)]
            missed=[r for t,r in records[sid].items() if flag['a']<=t<first_nonzero and r['values']['temp_c']>2 and
                    sum(t in records[other] and records[other][t]['values']['rain_mm']>0 for other in peers(sid))>=2]
            row['independent_rain_support']=dict(zero_duration_hours=(first_nonzero-zero_start).total_seconds()/3600,
                missed_warm_peer_wet_minutes=len(missed)*sites[sid]['step'].total_seconds()/60,
                release_mm=round(sum(r['values']['rain_mm'] for r in release),3),
                peer_totals_mm={other:round(sum(r['values']['rain_mm'] for t,r in records[other].items() if flag['a']<=t<=flag['b']),3) for other in peers(sid)})
        ledger.append(row)
    begin=min(t for index in records.values() for t in index);end=max(t for index in records.values() for t in index)
    drift=[];policies=[]
    for sid in sites:
        ff=[f for f in flags if f['station_id']==sid and f['issue']=='sunlight-dependent temperature drift']
        if not ff:continue
        for other in peers(sid):
            sunny=lambda r:r['values']['ghi_wm2']>300
            dark=lambda r:r['values']['ghi_wm2']<5
            early_sunny=pair(sid,other,'temp_c',begin,begin+timedelta(days=7),sunny)
            late_sunny=pair(sid,other,'temp_c',end-timedelta(days=7),end+sites[sid]['step'],sunny)
            early_night=pair(sid,other,'temp_c',begin,begin+timedelta(days=7),dark)
            late_night=pair(sid,other,'temp_c',end-timedelta(days=7),end+sites[sid]['step'],dark)
            drift.append(dict(station_id=sid,peer=other,sunny_change_c=round(mid(late_sunny)-mid(early_sunny),3),
                              night_change_c=round(mid(late_night)-mid(early_night),3)))
        e=evidence(ff[0]);choices={'full_model':ff[0]['a'],'earliest_omission':datetime.fromisoformat(e['tested_onset_start']),
                                 'latest_successful_omission':datetime.fromisoformat(e['tested_onset_end'])}
        departure=e.get('matched_time_block_validation',{}).get('first_three_day_departure')
        if departure:choices['strong_matched_departure']=datetime.fromisoformat(departure)
        for name,a in choices.items():
            retained=[r['values']['temp_c'] for t,r in records[sid].items() if not(t>=a and r['values']['ghi_wm2']>100) and usable(sid,t,'temp_c')]
            held=sum(t>=a and r['values']['ghi_wm2']>100 for t,r in records[sid].items())
            policies.append(dict(station_id=sid,policy=name,hold_start=str(a),sunlit_samples_held=held,
                                 usable_percent=round(100*len(retained)/len(records[sid]),2),
                                 available_sample_mean_c=round(sum(retained)/len(retained),3),
                                 caveat='Sensitivity diagnostic only: an available-sample mean is not a complete daily or period mean.'))
    hashes={name:hashlib.sha256((pack/name).read_bytes()).hexdigest() for name in audit['input_hashes']}
    return dict(scope='Independent arithmetic consistency review; not calibrated field truth.',
                source_hashes_unchanged=hashes==audit['input_hashes'],raw_rows=raw_counts,
                unique_rows={sid:len(v) for sid,v in records.items()},removed_exact_copies=removed,
                conflicting_times=conflicts,all_flag_intervals_reviewed=len(ledger),ledger=ledger,
                gps={sid:gps_review(pack/'gps'/f'{sid}.nmea') for sid in sites},
                drift_pair_changes=drift,drift_policy_sensitivity=policies)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pack',type=Path)
    parser.add_argument('--submission',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();data=review(args.pack,args.submission)
    args.output.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:data[k] for k in ('source_hashes_unchanged','all_flag_intervals_reviewed','drift_pair_changes','drift_policy_sensitivity')},indent=2))
