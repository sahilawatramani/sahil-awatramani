"""Self-contained coordinator page and a separate, derived evidence notebook."""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import timedelta
from html import escape as esc
import math
import re
from .model import CHANNELS, med, network_bounds, stamp
from .config import DEFAULTS

LABELS = {'temp_c':'Temp','rh_pct':'RH','pressure_hpa':'Press','wind_kmh':'Wind',
          'wind_dir_deg':'Dir','rain_mm':'Rain','ghi_wm2':'Sun'}
VISITS = {
    'wind scale discontinuity': dict(repair_class=3,
        work="Check the anemometer model, output units and logger coefficient, then verify against its specification and an independent reference.",
        reason="The continuing large wind-ratio change has consistent reference-omission support and a plausible configuration fix within one hour.",
        tools="Sensor manual/model list, logger interface, known-compatible spare and portable wind reference.",
        plan="0-10 min: photograph model and configuration; 10-25: check units, wiring and coefficient; 25-45: compare simultaneous speed readings; 45-60: correct only a documented mismatch and repeat the comparison.",
        verification="Document the configured units/coefficient and compare several readings across changing wind; use manufacturer tolerance, without assuming the historical ratio is a calibration factor.",
        contingency="If no specification/reference or a safe representative comparison is available, log findings, leave calibration unchanged and keep future wind on hold.",
        remote="Request the model/configuration photograph before travel; cancel the visit if a verified remote fix passes comparison."),
    'pressure calibration step': dict(repair_class=2,
        work="Compare station pressure with a calibrated reference at the same height; check the replacement board and record any adjustment.",
        reason="Pressure is still affected, but a defensible adjustment requires a calibrated reference; this becomes first choice if that kit is available and the wind configuration is resolved remotely.",
        tools="Calibrated station-pressure reference, board documentation and logger interface.",
        plan="0-15 min: check board/settings; 15-40: co-locate and compare pressure; 40-60: apply only a documented adjustment and verify again.",
        verification="Agreement within combined instrument specification at the same height; retain before/after readings and settings.",
        contingency="Without a calibrated reference, inspect settings only and retain the pressure hold.",
        remote="Obtain the replacement-board specification and current settings before dispatch."),
    'sensor frozen': dict(repair_class=3,work="Check power, connection and diagnostics; verify a repaired or replacement sensor with an independent reference.",
        reason="A channel remains frozen; a connection or replacement check may restore future observations in one visit.",
        tools="Compatible spare, electrical tools and channel reference.",plan="Check diagnostics, isolate the connection fault, replace only as justified and verify variation.",
        verification="Independent reference agreement and resumed plausible variation.",contingency="Keep channel on hold if the reference check fails.",remote="Check logger diagnostics remotely first."),
    'humidity saturation failure': dict(repair_class=2,work="Inspect contamination and ventilation, then compare with a humidity reference.",
        reason="A humidity fault continues and requires an independent sensor check.",tools="Humidity reference and compatible probe.",
        plan="Inspect, compare, clean/replace if justified, then verify.",verification="Reference agreement within specification.",
        contingency="Retain the hold if no trustworthy comparison is possible.",remote="Check diagnostics and condensation context first."),
    'sunlight-dependent temperature drift': dict(repair_class=1,
        work="Inspect shield ventilation, mounting and nearby surfaces; compare with a shaded reference thermometer in sunlight.",
        reason="Exposure bias is probable, but cause and onset are uncertain; a daylight diagnosis may need longer than one visit.",
        tools="Shielded calibrated thermometer, mounting inspection kit and sunshine during the visit.",
        plan="Inspect exposure, co-locate a shielded reference, compare through sun/shade changes, document any intervention.",
        verification="A stable sunlight comparison within instrument tolerances, with no unexplained day/night difference.",
        contingency="Arrange a longer co-location if conditions are cloudy or a one-hour comparison is inconclusive.",
        remote="Check siting photographs; do not assign the cause from the maintenance note alone."),
    'location mismatch': dict(repair_class=0,work="Reconcile installation sheets and logger identity remotely before a coordinate-verification visit.",
        reason="Coordinate-dependent use is restricted; a remote metadata check can resolve this before spending the field hour.",
        tools="Installation history, logger serial number and GNSS receiver.",plan="Reconcile identity, then verify the physical location if necessary.",
        verification="Inventory, serial number and independent position agree.",contingency="Retain the spatial-use restriction.",remote="Remote inventory/identity check first."),
}


def rank_visits(result):
    candidates=[]
    for station in result.stations.values():
        if not station.records:continue
        active=[f for f in result.flags if f.station_id==station.id and f.issue in VISITS
                and f.end>=station.bounds[1]-timedelta(hours=24)
                and f.evidence.get('status')!='recovered']
        for flag in active:
            policy=VISITS[flag.issue]
            start=station.bounds[1]-timedelta(days=7)+station.step
            channels=CHANNELS if flag.channel=='all' else (flag.channel,)
            affected=sum(any(c in r.excluded for c in channels) for r in station.records if r.time>=start and not r.removed)
            hours=round(affected*station.interval/60,1)
            strength=(flag.evidence.get('omission_detections',0),flag.confidence=='high')
            candidates.append(dict(station_id=station.id,name=station.name,issue=flag.issue,
                                   confidence=flag.confidence,recent_affected_hours=hours,
                                   ranking_basis='Ongoing fault; feasible one-hour intervention first, then reference support and affected hours; ordinal policy, not expected utility.',
                                   **policy,_sort=(policy['repair_class'],strength,hours)))
    ranked=sorted(candidates,key=lambda c:(-c['_sort'][0],-c['_sort'][1][0],-c['_sort'][1][1],-c['_sort'][2],c['station_id']))
    unique=[]
    for candidate in ranked:
        candidate.pop('_sort')
        if candidate['station_id'] not in {c['station_id'] for c in unique}:unique.append(candidate)
    return unique


def climate_use(flags,channels,unresolved=()):
    """Aggregation eligibility is distinct from a sample passing QC."""
    repaired=any(f.action=='correct' for f in flags)
    spatial=any(f.channel=='metadata' and f.action=='exclude' for f in flags)
    use={}
    for channel,stats in channels.items():
        pct=stats['percent']
        state='hold' if pct is None or pct==0 else ('partial' if pct<100 else ('repaired' if repaired else 'full'))
        restriction='Compare shared valid periods; a retained sample is not a calibration certificate.'
        if state=='partial':
            restriction='Use valid intervals only; report missing coverage and do not label an available-sample statistic a complete-period statistic.'
            if channel=='rain_mm':restriction='Incomplete accumulation: no complete-period rainfall total or redistribution of delayed rain.'
            if channel=='temp_c' and any(f.issue=='sunlight-dependent temperature drift' for f in flags):
                restriction='Retained nights cannot supply a complete daily mean or maximum; use pre-hold shared periods or explicitly nighttime-only statistics.'
        if state=='hold':restriction='No supported complete-period use; resolve the missing or invalid observations first.'
        if any(u['channel']==channel for u in unresolved):
            state='review'
            restriction='Reference groups disagree across a boundary; do not use an unqualified full-period change until an independent anchor resolves the groups.'
        use[channel]=dict(state=state,restriction=restriction,coordinate_dependent_use='hold' if spatial else 'available subject to checks')
    overall='hold' if all(v['state']=='hold' for v in use.values()) else ('review' if unresolved else ('partial' if any(v['state'] in ('partial','hold') for v in use.values()) else ('repaired' if repaired else 'full')))
    return dict(state=overall,spatial_hold=spatial,channels=use)


def audit(result):
    begin,end=network_bounds(result)
    out={'period_start':stamp(begin),'period_end':stamp(end),'version':'2.0.0',
         'warnings':result.warnings,'unresolved_checks':result.unresolved,
         'thresholds':DEFAULTS.as_dict(),'stations':{},'visit_ranking':rank_visits(result)}
    for s in result.stations.values():
        flags=[f for f in result.flags if f.station_id==s.id]
        unique={r.time:r for r in s.records if not r.removed}
        first,last,expected=s.grid(begin,end)
        safe={t:r for t,r in unique.items() if not r.clock_unsafe and first <= t <= last
              and (t-first) % s.step == timedelta(0)}
        channels={}
        for c in CHANNELS:
            usable=sum(math.isfinite(r.value(c)) for r in safe.values())
            channels[c]={'usable':usable,'expected':expected,'percent':round(usable/expected*100,1) if expected else None}
        out['stations'][s.id]={'name':s.name,'raw_rows':len(s.records),'unique_rows':len(unique),
                              'present_slots':len(safe),'off_grid_rows':sum(not r.clock_unsafe and (t-first) % s.step != timedelta(0) for t,r in unique.items()),
                              'expected_slots':expected,'missing_slots':sum(f.evidence.get('missing_slots',0) for f in flags),
                              'removed_retransmissions':sum(r.removed for r in s.records),
                              'clock_corrected_rows':sum(r.time!=r.raw for r in s.records),
                              'gps':s.gps_stats,'channels':channels,'climate_use':climate_use(flags,channels,[u for u in result.unresolved if u['station_id']==s.id]),
                              'maintenance_context':maintenance_context(s.notes),
                              'issues':dict(Counter(f.issue for f in flags))}
    out['flags']=[]
    out['diagnostics']={}
    for f in result.flags:
        evidence=f.evidence
        if 'daily_points' in evidence or 'hourly_points' in evidence:
            key=f"{f.station_id}/{'daylight-temperature-drift' if 'daily_points' in evidence else 'wind-scale'}"
            out['diagnostics'][key]=evidence
            evidence={'diagnostic_ref':key}
        out['flags'].append(dict(f.as_row(),confidence=f.confidence,evidence=evidence))
    return out


def maintenance_context(notes):
    """Derived themes only; do not reproduce the private notebook in outputs."""
    themes={'pressure':'pressure hardware/calibration note','anemometer':'wind hardware note',
            'repaint':'exposure or mounting change','rain gauge':'rain-gauge inspection',
            'battery':'power intervention','humidity':'humidity concern',
            'same day':'possible retransmission concern','SIM':'communications intervention',
            'snow':'snow/access conditions','routine':'routine inspection'}
    summaries=[]
    for line in notes:
        date=re.match(r'\d{4}-\d{2}-\d{2}',line)
        if not date:continue
        matches=[description for term,description in themes.items() if term.lower() in line.lower()]
        summaries.append({'date':date.group(),'themes':matches or ['general maintenance note']})
    return summaries


def short_date(t):
    return t.strftime('%d %b %H:%M')


def station_advice(flags):
    notes=[]
    for issue in dict.fromkeys(f.issue for f in flags):
        ff=[f for f in flags if f.issue==issue];f=ff[0]
        if issue=='coherent mountain cold':notes.append('Keep cold conditions; consistent with elevation and regional weather.')
        elif issue=='pressure calibration step':notes.append(f"Pressure: omit {short_date(f.start)} to {short_date(f.end)}; verify calibration.")
        elif issue=='sensor frozen':notes.append(f"{LABELS.get(f.channel,f.channel)}: omit {f.start:%d %b}-{f.end:%d %b} freeze.")
        elif issue in ('invalid value','isolated temperature spike','temperature error burst'):
            if not any('spike' in n for n in notes):notes.append('Omit isolated bad values/spikes.')
        elif issue=='sunlight-dependent temperature drift':notes.append(f"Temperature: omit sunlit windows from about {f.start:%d %b}; retain nights.")
        elif issue=='rain blockage and delayed release':notes.append(f"Rain: omit {f.start:%d %b}-{f.end:%d %b}; lost timing cannot be reconstructed.")
        elif issue=='humidity saturation failure':notes.append(f"RH: omit saturated episode {f.start:%d %b}-{f.end:%d %b}.")
        elif issue=='location mismatch':notes.append('Verify location before mapping or elevation-based comparisons.')
        elif issue=='logger clock offset':notes.append(f"Add {f.evidence['offset_seconds']/3600:+g} h from {short_date(f.start)} (corrected UTC); retain observations.")
        elif issue=='wind scale discontinuity':notes.append(f"Wind: omit {short_date(f.start)} to {short_date(f.end)}; verify configuration.")
        elif issue=='missing observations':notes.append(f"{f.evidence['missing_slots']} missing samples; do not fill or call zero.")
        elif issue in ('missing weather file','empty weather file'):notes.append('No weather file observations; omit this station from the summary.')
        elif issue=='installation date conflict':notes.append('Verify installation history before using records that predate the inventory.')
        elif issue=='exact retransmission':notes.append(f"Remove {f.evidence['extra_rows']} repeated rows; retain one copy.")
        else:notes.append(issue.capitalize()+'.')
    return ' '.join(notes) or 'No fault detected by these checks; retain with normal limitations.'


CSS = """
:root{--ink:#142c3c;--muted:#506473;--line:#d6e0e3;--paper:#fff;--teal:#11675e;--red:#9a3535;--amber:#8a5913}
*{box-sizing:border-box}body{margin:0;background:#e8edef;color:var(--ink);font:14px/1.45 'Segoe UI',Arial,sans-serif}
.page{width:210mm;min-height:297mm;padding:13mm 13mm 11mm;margin:25px auto;background:var(--paper);box-shadow:0 5px 30px #15304218}
.eyebrow{font-size:10px;letter-spacing:2px;text-transform:uppercase;font-weight:700;display:flex;justify-content:space-between;border-top:4px solid var(--ink);padding-top:12px;color:var(--muted)}
h1{font-size:36px;line-height:1.1;letter-spacing:-1.2px;margin:18px 0 10px;max-width:580px;font-weight:650}
.intro{font-size:14px;max-width:620px;margin:0 0 17px}.period{font-size:11px;color:var(--muted)}
.dispatch{background:var(--ink);color:white;padding:15px 18px;display:grid;grid-template-columns:120px 1fr;gap:16px;margin:17px 0}
.dispatch-label{font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:#bbd3d7}.dispatch-id{font-size:33px;line-height:1.2;margin:3px 0}.dispatch h2{font-size:16px;margin:0 0 4px}.dispatch p{font-size:12px;margin:0;line-height:1.5}
.stats{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:17px 0;padding:11px 0;gap:18px}.stat strong{font-size:23px;display:block}.stat span{font-size:11px;color:var(--muted)}
.section-label{font-size:11px;text-transform:uppercase;letter-spacing:1.3px;margin:18px 0 5px}table{width:100%;border-collapse:collapse;font-size:11px}th{font-size:9px;letter-spacing:.5px;text-transform:uppercase;text-align:left;padding:8px 4px;color:var(--muted);border-bottom:2px solid var(--ink)}td{padding:9px 4px;vertical-align:top;border-bottom:1px solid var(--line)}.site{width:100px}.site strong{font-size:12px;display:block}.site span{font-size:10px;line-height:1.25;display:block;color:var(--muted)}.pct{width:33px;text-align:center;font-variant-numeric:tabular-nums;font-size:10px;white-space:nowrap}.good{color:var(--teal)}.hold{background:#f7eded;color:var(--red);font-weight:700}.partial{background:#f8f2e7;color:var(--amber)}.advice{padding-left:12px;font-size:11.5px;line-height:1.4}.use{width:155px;font-size:11px}.use strong,.use span{display:block}.use span{font-size:10px;margin-top:3px;color:var(--muted)}.use.partial strong,.use.hold strong{color:var(--amber)}.use.repaired strong,.use.full strong{color:var(--teal)}.legend{font-size:10px;margin:7px 0;color:var(--muted)}
.bottom{display:grid;grid-template-columns:1.05fr 1fr;gap:22px;margin-top:16px}.bottom h3{font-size:12px;margin:0 0 4px}.bottom p{font-size:11px;line-height:1.5;margin:0}.foot{border-top:1px solid var(--line);padding-top:9px;margin-top:16px;font-size:9px;color:var(--muted);display:flex;justify-content:space-between;gap:16px}
.page{padding-top:10mm;padding-bottom:8mm}h1{font-size:32px;margin-top:14px}.intro{margin-bottom:12px}.dispatch{padding:12px 18px;margin:13px 0}.stats{margin:10px 0;padding:9px 0}td{padding-top:7px;padding-bottom:7px}.bottom{margin-top:12px}.foot{margin-top:10px}.section-label{margin-top:14px}.eyebrow{padding-top:9px}
@page{size:A4;margin:0}@media print{body{background:white}.page{margin:0;box-shadow:none;min-height:0;width:210mm}a{color:inherit;text-decoration:none}.no-print{display:none}}
"""


def write_report(result, data, path):
    total=sum(s['expected_slots'] for s in data['stations'].values())
    present=sum(s['present_slots'] for s in data['stations'].values())
    presence=f'{100*present/total:.1f}%' if total else 'N/A'
    missing=sum(s['missing_slots'] for s in data['stations'].values())
    corrected=sum(s['clock_corrected_rows'] for s in data['stations'].values())
    ranking=data['visit_ranking']
    if ranking:
        visit=ranking[0]
        dispatch=f"<div class='dispatch'><div><div class='dispatch-label'>One-hour visit</div><div class='dispatch-id'>{esc(visit['station_id'])}</div></div><div><h2>{esc(visit['name'])}</h2><p>{esc(visit['work'])}</p></div></div>"
    else:
        dispatch="<div class='dispatch'><div class='dispatch-label'>Next visit</div><div><h2>No defensible destination from these checks</h2><p>Review missing evidence and maintenance needs before dispatching.</p></div></div>"
    rows=[]
    for sid,s in data['stations'].items():
        ff=[f for f in result.flags if f.station_id==sid]
        use=s['climate_use']
        labels={'full':'Full-period use','repaired':'Use after repair','partial':'Partial periods','hold':'Hold','review':'Reference review'}
        affected=[f"{LABELS[c]} {s['channels'][c]['percent']:g}%" if s['channels'][c]['percent'] is not None else f"{LABELS[c]} N/A"
                  for c in CHANNELS if s['channels'][c]['percent'] is None or s['channels'][c]['percent']<100]
        percentages={v['percent'] for v in s['channels'].values()}
        if len(percentages)==1 and None not in percentages:
            detail=f"All seven: {next(iter(percentages)):g}%"
        else:detail=' / '.join(affected) if affected else 'All seven: 100%'
        if use['spatial_hold']:detail+='; spatial use on hold'
        restriction=''
        if any(f.issue=='sunlight-dependent temperature drift' for f in ff):restriction=' No complete daily temperature means or maxima from retained nights.'
        if s['channels']['rain_mm']['percent'] is not None and s['channels']['rain_mm']['percent']<100:restriction+=' No complete-period rain total.'
        advice=station_advice(ff)+restriction
        rows.append(f"<tr><td class='site'><a href='evidence.html#{esc(sid)}'><strong>{esc(sid)}</strong></a><span>{esc(s['name'])}</span></td><td class='use {use['state']}'><strong>{labels[use['state']]}</strong><span>{esc(detail)}</span></td><td class='advice'>{esc(advice)}</td></tr>")
    uncertain=[f for f in result.flags if f.issue=='sunlight-dependent temperature drift']
    if uncertain:
        f=uncertain[0]
        evidence=f.evidence
        if evidence.get('omission_tests'):
            start=evidence['tested_onset_start'][:10];end=evidence['tested_onset_end'][:10]
            uncertainty=f"{f.station_id}: {evidence['omission_detections']}/{evidence['omission_tests']} reference-omission checks detect warming; fitted starts range {start} to {end}. Keep the daytime hold pending a shielded reference comparison."
        else:
            uncertainty=f"{f.station_id}'s daylight warming is probable, not a proven paint effect; compare with a shielded reference before treating the estimated onset as fact."
    else:
        uncertainty="Peer checks can miss common faults or confuse local weather with sensor changes; unflagged data is not certified accuracy."
    if len(ranking)>1:
        runner=ranking[1]
        comparison=f"{ranking[0]['reason']} Next: {runner['station_id']}; {runner['issue']} needs independent verification. Resolve configuration remotely first if possible."
    elif ranking:comparison=ranking[0]['reason']
    else:comparison="No ongoing, diagnosable repair outranks the others on available evidence."
    warning=" ".join(data['warnings'])
    if result.unresolved:warning+=f' {len(result.unresolved)} unresolved reference comparisons require independent review; see evidence.'
    html=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ridgeline | Network health</title><style>{CSS}</style></head><body><main class="page">
<div class="eyebrow"><span>Ridgeline / Field notes</span><span>Network health &nbsp; 01</span></div>
<h1>Use the network<br>selectively.</h1><p class="intro">Keep reliable channels. Apply the supported time and duplicate repairs, then leave uncertain observations out of the six-week summary.</p>
<div class="period">{esc(data['period_start'])} - {esc(data['period_end'])} UTC &nbsp; | &nbsp; {len(data['stations'])} stations</div>{dispatch}
<div class="stats"><div class="stat"><strong>{presence}</strong><span>Expected observations present<br>after clock repair and deduplication</span></div><div class="stat"><strong>{missing:,}</strong><span>Missing time slots<br>leave missing, never treat as zero</span></div><div class="stat"><strong>{corrected:,}</strong><span>Observations with repaired time<br>preserve the measurements</span></div></div>
<h2 class="section-label">What can enter the summary</h2><table><thead><tr><th>Station</th><th>Summary use / retained samples</th><th style="padding-left:10px">Decision / UTC</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p class="legend">Use decisions apply after supported repairs. Percentages = usable samples / expected samples, not accuracy. Unlisted channels have full retained coverage. RH = humidity.</p>
<div class="bottom"><section><h3>Why this visit comes first</h3><p>{esc(comparison)}</p></section><section><h3>The call to verify</h3><p>{esc(uncertainty)}</p></section></div>
<div class="foot"><span>Use shared valid periods for comparisons. Omitted samples can bias means and totals: do not present partial rain totals as complete. Six weeks describe this period, not all of spring. Snow-related gauge undercatch remains unquantified. {esc(warning)}</span><span>Intervals and evidence:<br>flags.csv / evidence.html</span></div>
</main></body></html>"""
    path.write_text(html,encoding='utf-8')


def line_chart(series, title, y_label, dates=None):
    """Small inline SVG: list of (label, values, colour) sharing an ordinal x axis."""
    finite=[v for _,values,_ in series for v in values if v is not None and math.isfinite(v)]
    if not finite:return ''
    low,high=min(finite),max(finite)
    pad=max(.5,(high-low)*.12);low-=pad;high+=pad
    n=max(len(values) for _,values,_ in series);w,h=720,230
    left,right,top,bottom=55,15,20,52
    def x(i):return left+i*(w-left-right)/max(1,n-1)
    def y(v):return top+(high-v)/(high-low)*(h-top-bottom)
    parts=[f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}"><title>{esc(title)}</title>']
    for i in range(5):
        value=low+(high-low)*i/4;yy=y(value)
        parts.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{w-right}" y2="{yy:.1f}" stroke="#dde5e8"/><text x="{left-8}" y="{yy+4:.1f}" text-anchor="end" font-size="11" fill="#526676">{value:.1f}</text>')
    for label,values,colour in series:
        path=[]
        for i,v in enumerate(values):
            if v is None or not math.isfinite(v):
                if path:parts.append(f'<polyline points="{" ".join(path)}" fill="none" stroke="{colour}" stroke-width="2"/>');path=[]
            else:path.append(f'{x(i):.1f},{y(v):.1f}')
        if path:parts.append(f'<polyline points="{" ".join(path)}" fill="none" stroke="{colour}" stroke-width="2"/>')
    if dates:
        for i in sorted({round(j*(n-1)/4) for j in range(5)}):
            parts.append(f'<text x="{x(i):.1f}" y="{h-28}" text-anchor="middle" font-size="11" fill="#526676">{esc(str(dates[i])[5:])}</text>')
    parts.append(f'<text x="{left}" y="{h-5}" font-size="11" fill="#526676">UTC date (MM-DD); {esc(y_label)}</text></svg>')
    return ''.join(parts)


def write_evidence(result,data,path):
    plots=[]
    for station in result.stations.values():
        fixes=[f for f in station.gps if f.utc]
        if any(f.station_id==station.id and f.issue=='logger clock offset' for f in result.flags):
            byday=defaultdict(list)
            for f in fixes:byday[f.utc.date()].append((f.logger-f.utc).total_seconds()/3600)
            chart=line_chart([('Logger minus GPS',[med(v) for _,v in sorted(byday.items())],'#11675e')],f'{station.id} clock offset','hours, logger minus GPS',[d for d,_ in sorted(byday.items())])
            plots.append(f'<section class="card"><h2>{esc(station.id)} / supported correction: the clock</h2><p>Daily median of checksum-valid, active RMC fixes. A persistent offset is mapped to weather rows before repair; restoring UTC preserves distinct observations. Daily medians smooth the transition; exact source rows are in the ledger.</p>{chart}</section>')
    from .peers import Peers
    peers=Peers(result)
    for flag in result.flags:
        if flag.issue not in ('pressure calibration step','wind scale discontinuity'):continue
        station=result.stations[flag.station_id]
        daily=defaultdict(list)
        if flag.channel=='wind_kmh':
            for point in flag.evidence['hourly_points']:
                daily[point['time_utc'][:10]].append(math.exp(point['log_ratio']))
            units='ratio (target+0.5) / (peer median+0.5)'
            description='Daily median ratios from the pre-exclusion wind diagnostics. Local wind variability makes the exact start uncertain; the CSV holds from the earliest nearby reference-tested opening. This observed ratio is not an authorized calibration factor.'
        else:
            for r in station.index().values():
                reference=med(peers.values(station,r,'pressure_hpa'))
                if math.isfinite(reference) and math.isfinite(r.values['pressure_hpa']):
                    daily[str(r.time.date())].append(r.values['pressure_hpa']-reference)
            baseline=med(v for day,values in sorted(daily.items())[:7] for v in values)
            daily={day:[v-baseline for v in values] for day,values in daily.items()}
            units='hPa, target minus peers, centered on first week'
            description='The daily pressure difference is centered on the first week to remove the site-level offset. The abrupt detector uses paired differences and raw-cadence boundaries; daily smoothing is for inspection. Excluded target measurements remain visible here, without being re-admitted to the summary.'
        chart=line_chart([(flag.channel,[med(v) for _,v in sorted(daily.items())],'#b15e32')],f'{station.id} {flag.channel} diagnostic',units,[d for d,_ in sorted(daily.items())])
        plots.append(f'<section class="card"><h2>{esc(station.id)} / {esc(flag.issue)}</h2><p>{description}</p>{chart}</section>')
    drift=next((f for f in result.flags if f.issue=='sunlight-dependent temperature drift'),None)
    if drift:
        points=drift.evidence['daily_points']
        chart=line_chart([('Sunny residual',[p['sunny_residual'] for p in points],'#b15e32'),('Night residual',[p['night_residual'] for p in points],'#11675e')],f'{drift.station_id} temperature residuals','degrees C, target minus peer median',[p['day'] for p in points])
        detail=''
        if drift.evidence.get('omission_tests'):
            d=drift.evidence
            detail=f"<p><strong>Reference sensitivity:</strong> {d['omission_detections']}/{d['omission_tests']} single-reference omissions still detect warming, with fitted starts from {d['tested_onset_start']} to {d['tested_onset_end']} UTC; this range is not a statistical confidence interval, and the earliest true fault time remains unresolved.</p>"
        validation=drift.evidence.get('matched_time_block_validation',{})
        if validation:
            detail+=f"<p><strong>Separate time-block check:</strong> A first-week residual model matches two-hour UTC and sunlight bins, then tests the second week without refitting (median absolute error {validation['heldout_sunny_mae_c']:.2f} C); the last-week sunny residual rises another {validation['late_sunny_change_c']:.2f} C relative to that held-out week. The first three-day departure above the model's {validation['departure_threshold_c']:.2f} C noise threshold is {validation['first_three_day_departure'] or 'not identified'}. This supports the later warming pattern, while reinforcing that the earlier hinge onset is a precautionary holding choice.</p>"
        plots.append(f'<section class="card"><h2>{esc(drift.station_id)} / least certain: sunlight-dependent warming</h2><p><span style="color:#b15e32">Orange: GHI &gt;300 W/m2</span>; <span style="color:#11675e">green: GHI &lt;5 W/m2</span>. Daily residuals use suitable peers after confirmed exclusions. A rising sunny residual with little first/last-week night change supports exposure bias, but does not prove paint caused it. The hinge-model onset is approximate. Settle it with a co-located, shielded reference comparison in sunlight.</p>{detail}{chart}</section>')
    ranking=data['visit_ranking']
    if ranking:
        visit=ranking[0]
        runner=ranking[1] if len(ranking)>1 else None
        alternative=f"<p><strong>Strongest alternative: {esc(runner['station_id'])}.</strong> {esc(runner['reason'])}</p>" if runner else ''
        plots.append(f'<section class="card"><h2>One field hour / {esc(visit["station_id"])}</h2><p>{esc(visit["reason"])} {visit["recent_affected_hours"]:g} channel-hours remain affected in the last seven days.</p><p><strong>Before travel:</strong> {esc(visit["remote"])}</p><p><strong>Bring:</strong> {esc(visit["tools"])}</p><p>{esc(visit["plan"])}</p><p><strong>Verification:</strong> {esc(visit["verification"])}</p><p><strong>Contingency:</strong> {esc(visit["contingency"])}</p>{alternative}<p>Ranking assumes safe access, compatible equipment and the stated one-hour work scope; it is an operational policy, not a measured repair probability.</p></section>')
    if result.unresolved:
        plots.append('<section class="card"><h2>Unresolved reference comparisons</h2><p>No failed group or numerical correction is assigned. These outcomes are separate from a CSV keep decision; cross-boundary summary use needs independent evidence.</p>'+''.join(f"<p><strong>{esc(u['station_id'])} / {esc(u['channel'])} / {esc(u['time_utc'])}</strong><br>{esc(u['reason'])}</p>" for u in result.unresolved)+'</section>')
    rows=[]
    seen=set()
    for f in result.flags:
        # Show one summary of repeated daylight windows; exact rows remain in CSV.
        key=(f.station_id,f.issue)
        if f.issue=='sunlight-dependent temperature drift' and key in seen:continue
        seen.add(key)
        ff=[g for g in result.flags if (g.station_id,g.issue)==key]
        end=max(g.end for g in ff) if f.issue=='sunlight-dependent temperature drift' else f.end
        extra=f" ({len(ff)} separate sunlit windows)" if f.issue=='sunlight-dependent temperature drift' else ''
        rows.append(f'<tr data-station="{esc(f.station_id)}"><td>{esc(f.station_id)}</td><td>{esc(f.channel)}<br><strong>{esc(f.issue)}</strong>{extra}</td><td>{stamp(f.start)}<br>{stamp(end)}</td><td>{esc(f.action)}<br>{esc(f.confidence)}</td><td>{esc(f.note)}</td></tr>')
    gpsrows=[]
    for sid,s in data['stations'].items():
        gpsrows.append(f'<tr><td>{esc(sid)}</td><td>{s["gps"].get("accepted_rmc",0)}</td><td>{s["gps"].get("accepted_gga",0)}</td><td>{s["gps"].get("checksum_failed",0)}</td><td>{s["gps"].get("invalid_fix",0)}</td></tr>')
    options=''.join(f'<option>{esc(sid)}</option>' for sid in data['stations'])
    body=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ridgeline | Evidence notebook</title><style>{CSS}
.notebook{{max-width:1080px;margin:35px auto;padding:0 24px}}.card{{background:white;border:1px solid var(--line);padding:24px;margin:20px 0}}.card h2{{font-size:20px;margin:0 0 12px}}.card p{{max-width:900px}}.card svg{{max-width:850px;width:100%}}.card table{{font-size:12px}}.card td{{padding:10px}}#ledger th:nth-child(3),#ledger td:nth-child(3){{width:145px;white-space:nowrap;font-variant-numeric:tabular-nums}}select{{padding:8px;border:1px solid var(--line);font:inherit}}a{{color:var(--teal)}}@media print{{.card{{break-inside:avoid}}}}
</style></head><body><main class="notebook"><div class="eyebrow">Ridgeline / evidence notebook <a href="report.html">Coordinator report</a></div><h1>Show the evidence.</h1><p>Derived diagnostics, not a copy of the private pack. UTC intervals are inclusive and follow supported clock repair. Quality confidence is a judgment category, not a probability.</p>{''.join(plots)}
<section class="card"><h2>Incident ledger</h2><label>Station <select id="station"><option value="">All stations</option>{options}</select></label><table id="ledger"><thead><tr><th>Station</th><th>Channel / problem</th><th>Start / end UTC</th><th>Action / confidence</th><th>Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section class="card"><h2>GPS evidence admitted / rejected</h2><p>Rejected sentences do not automatically invalidate weather. Small isolated losses do not demonstrate a clock fault. No date is inferred from GGA alone.</p><table><thead><tr><th>Station</th><th>Valid RMC</th><th>Good GGA</th><th>Checksum failures</th><th>Inactive RMC</th></tr></thead><tbody>{''.join(gpsrows)}</tbody></table></section>
<section class="card"><h2>Maintenance context</h2><p>Detection does not use notebook dates as fault boundaries. Themes below are derived context, not copies of the private notebook. Notebook times have no stated time zone and are not silently interpreted as UTC.</p>{''.join('<p><strong>'+esc(sid)+'</strong><br>'+'<br>'.join(esc(n['date']+' / '+', '.join(n['themes'])) for n in s['maintenance_context'])+'</p>' for sid,s in data['stations'].items())}</section>
<section class="card"><h2>Limits of this decision</h2><p>Rainfall timing cannot be reconstructed from a blocked bucket. Peer agreement can miss common-mode faults. Mountain snowfall undercatch, gradual calibration changes and relocation history remain unquantified. See METHODS.md for thresholds, coverage assumptions and unsupported corrections.</p></section></main>
<script>const stationSelect=document.getElementById('station');function filterStation(){{document.querySelectorAll('#ledger tbody tr').forEach(row=>row.hidden=stationSelect.value!==''&&row.dataset.station!==stationSelect.value)}}stationSelect.addEventListener('change',filterStation);const requested=decodeURIComponent(location.hash.slice(1));if([...stationSelect.options].some(option=>option.value===requested)){{stationSelect.value=requested;filterStation()}}</script></body></html>"""
    path.write_text(body,encoding='utf-8')
