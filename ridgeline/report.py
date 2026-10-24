"""Self-contained coordinator page and a separate, derived evidence notebook."""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import timedelta
from html import escape as esc
import json
import math
import re
from .model import CHANNELS, med, stamp

LABELS = {'temp_c':'Temp','rh_pct':'RH','pressure_hpa':'Press','wind_kmh':'Wind',
          'wind_dir_deg':'Dir','rain_mm':'Rain','ghi_wm2':'Sun'}
VISITS = {
    'wind scale discontinuity': (10, 'Check the new anemometer\'s model, output units and logger coefficient first; compare with its specification and a reference instrument, then correct configuration and verify readings.',
                                 'A large continuing wind error may be fixed by checking sensor and logger compatibility within one visit.'),
    'pressure calibration step': (8, 'Compare station pressure with a calibrated reference at the same height; check the replacement board configuration and record any adjustment.',
                                  'The continuing pressure discontinuity needs an independent calibration reference.'),
    'sunlight-dependent temperature drift': (7, 'Inspect shield ventilation, mounting and nearby surfaces; compare with a shaded reference thermometer in sunlight before changing the installation.',
                                             'A probable continuing exposure bias needs a daylight comparison; its exact onset and cause remain uncertain.'),
    'sensor frozen': (9, 'Check power, sensor connection and logger diagnostics, then verify with a reference instrument before replacing the sensor.',
                          'A continuing frozen channel cannot be repaired from surrounding weather.'),
    'humidity saturation failure': (8, 'Inspect sensor contamination and ventilation, then compare with a reference humidity instrument.',
                                        'A continuing humidity failure needs a physical sensor check.'),
    'location mismatch': (3, 'Check the installation sheet and logger identity remotely first; verify coordinates at the physical installation if these do not resolve the discrepancy.',
                            'The location discrepancy affects spatial interpretation; records alone do not establish which location source is wrong.'),
}


def rank_visits(result):
    candidates = []
    for s in result.stations.values():
        if not s.records:
            continue
        active = [f for f in result.flags if f.station_id==s.id and f.issue in VISITS and
                  f.end >= s.bounds[1]-timedelta(hours=24)]
        if active:
            chosen=max(active,key=lambda f:VISITS[f.issue][0])
            score,work,why=VISITS[chosen.issue]
            candidates.append({'station_id':s.id,'name':s.name,'issue':chosen.issue,'priority':score,
                               'work':work,'reason':why,'confidence':chosen.confidence})
    return sorted(candidates,key=lambda c:(-c['priority'],c['station_id']))


def audit(result):
    populated=[s for s in result.stations.values() if s.records]
    begin=min(s.bounds[0] for s in populated);end=max(s.bounds[1] for s in populated)
    out={'period_start':stamp(begin),'period_end':stamp(end),'version':'1.0.0',
         'warnings':result.warnings,'stations':{},'visit_ranking':rank_visits(result)}
    for s in result.stations.values():
        flags=[f for f in result.flags if f.station_id==s.id]
        unique={r.time:r for r in s.records if not r.removed}
        safe={t:r for t,r in unique.items() if not r.clock_unsafe}
        expected=max(0,int((end-max(begin,s.installed))/s.step)+1)
        channels={}
        for c in CHANNELS:
            usable=sum(math.isfinite(r.value(c)) for r in safe.values())
            channels[c]={'usable':usable,'expected':expected,'percent':round(usable/expected*100,1) if expected else 0}
        out['stations'][s.id]={'name':s.name,'raw_rows':len(s.records),'unique_rows':len(unique),
                              'expected_slots':expected,'missing_slots':sum(f.evidence.get('missing_slots',0) for f in flags),
                              'removed_retransmissions':sum(r.removed for r in s.records),
                              'clock_corrected_rows':sum(r.time!=r.raw for r in s.records),
                              'gps':s.gps_stats,'channels':channels,
                              'maintenance_context':maintenance_context(s.notes),
                              'issues':dict(Counter(f.issue for f in flags))}
    out['flags']=[]
    out['diagnostics']={}
    for f in result.flags:
        evidence=f.evidence
        if 'daily_points' in evidence:
            key=f'{f.station_id}/daylight-temperature-drift'
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
        elif issue=='pressure calibration step':notes.append(f"Pressure: omit from {short_date(f.start)}; calibrate replacement board.")
        elif issue=='sensor frozen':notes.append(f"Temperature: omit {f.start:%d %b}-{f.end:%d %b} freeze.")
        elif issue in ('invalid value','isolated temperature spike'):
            if not any('spike' in n for n in notes):notes.append('Omit isolated bad values/spikes.')
        elif issue=='sunlight-dependent temperature drift':notes.append(f"Temperature: omit sunlit windows from about {f.start:%d %b}; retain nights.")
        elif issue=='rain blockage and delayed release':notes.append(f"Rain: omit {f.start:%d %b}-{f.end:%d %b}; lost timing cannot be reconstructed.")
        elif issue=='humidity saturation failure':notes.append(f"RH: omit {f.start:%d %b}-{f.end:%d %b}; later readings recover.")
        elif issue=='location mismatch':notes.append('Verify location before mapping or elevation-based comparisons.')
        elif issue=='logger clock offset':notes.append(f"Add {f.evidence['offset_seconds']/3600:+g} h from {short_date(f.start)} (corrected UTC); retain observations.")
        elif issue=='wind scale discontinuity':notes.append(f"Wind speed: omit from about {short_date(f.start)}; verify calibration.")
        elif issue=='missing observations':notes.append(f"{f.evidence['missing_slots']} missing samples; do not fill or call zero.")
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
.section-label{font-size:11px;text-transform:uppercase;letter-spacing:1.3px;margin:18px 0 5px}table{width:100%;border-collapse:collapse;font-size:11px}th{font-size:9px;letter-spacing:.5px;text-transform:uppercase;text-align:left;padding:8px 4px;color:var(--muted);border-bottom:2px solid var(--ink)}td{padding:9px 4px;vertical-align:top;border-bottom:1px solid var(--line)}.site{width:112px}.site strong{font-size:12px;display:block}.site span{font-size:10px;line-height:1.25;display:block;color:var(--muted)}.pct{width:33px;text-align:center;font-variant-numeric:tabular-nums;font-size:10px;white-space:nowrap}.good{color:var(--teal)}.hold{background:#f7eded;color:var(--red);font-weight:700}.partial{background:#f8f2e7;color:var(--amber)}.advice{padding-left:10px;font-size:10.5px;line-height:1.4}.legend{font-size:10px;margin:7px 0;color:var(--muted)}
.bottom{display:grid;grid-template-columns:1.05fr 1fr;gap:22px;margin-top:16px}.bottom h3{font-size:12px;margin:0 0 4px}.bottom p{font-size:11px;line-height:1.5;margin:0}.foot{border-top:1px solid var(--line);padding-top:9px;margin-top:16px;font-size:9px;color:var(--muted);display:flex;justify-content:space-between;gap:16px}
.page{padding-top:10mm;padding-bottom:8mm}h1{font-size:32px;margin-top:14px}.intro{margin-bottom:12px}.dispatch{padding:12px 18px;margin:13px 0}.stats{margin:10px 0;padding:9px 0}td{padding-top:7px;padding-bottom:7px}.bottom{margin-top:12px}.foot{margin-top:10px}.section-label{margin-top:14px}.eyebrow{padding-top:9px}
@page{size:A4;margin:0}@media print{body{background:white}.page{margin:0;box-shadow:none;min-height:0;width:210mm}a{color:inherit;text-decoration:none}.no-print{display:none}}
"""


def write_report(result, data, path):
    total=sum(s['expected_slots'] for s in data['stations'].values())
    unique=sum(s['unique_rows'] for s in data['stations'].values())
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
        cells=[]
        for c in CHANNELS:
            pct=s['channels'][c]['percent'];level='good' if pct>=99.95 else ('partial' if pct>=90 else 'hold')
            cells.append(f"<td class='pct {level}'>{pct:g}</td>")
        rows.append(f"<tr><td class='site'><strong>{esc(sid)}</strong><span>{esc(s['name'])}</span></td>{''.join(cells)}<td class='advice'>{esc(station_advice(ff))}</td></tr>")
    uncertain=[f for f in result.flags if f.issue=='sunlight-dependent temperature drift']
    if uncertain:
        f=uncertain[0]
        uncertainty=f"{f.station_id}'s daylight warming is probable, not a proven paint effect. Its onset is estimated; a shaded reference thermometer beside the shield would test the diagnosis."
    else:
        uncertainty="Peer checks can miss common faults or confuse local weather with sensor changes; unflagged data is not certified accuracy."
    if len(ranking)>1:
        runner=ranking[1]
        comparison=f"{ranking[0]['reason']} Next: {runner['station_id']}. {runner['reason']}"
    elif ranking:comparison=ranking[0]['reason']
    else:comparison="No ongoing, diagnosable repair outranks the others on available evidence."
    warning=" ".join(data['warnings'])
    html=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ridgeline | Network health</title><style>{CSS}</style></head><body><main class="page">
<div class="eyebrow"><span>Ridgeline / Field notes</span><span>Network health &nbsp; 01</span></div>
<h1>Use the network<br>selectively.</h1><p class="intro">Keep reliable channels. Apply the supported time and duplicate repairs, then leave uncertain observations out of the six-week summary.</p>
<div class="period">{esc(data['period_start'])} - {esc(data['period_end'])} UTC &nbsp; | &nbsp; {len(data['stations'])} stations</div>{dispatch}
<div class="stats"><div class="stat"><strong>{100*unique/total:.1f}%</strong><span>Expected observations present<br>after clock repair and deduplication</span></div><div class="stat"><strong>{missing:,}</strong><span>Missing time slots<br>leave missing, never treat as zero</span></div><div class="stat"><strong>{corrected:,}</strong><span>Observations with repaired time<br>preserve the measurements</span></div></div>
<h2 class="section-label">What can enter the summary</h2><table><thead><tr><th>Station</th>{''.join(f'<th class="pct">{LABELS[c]}</th>' for c in CHANNELS)}<th style="padding-left:10px">Decision / UTC</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p class="legend">Numbers = usable % of expected samples after exclusions and supported repairs. 100 = no exclusion by these checks. Metadata restrictions still apply; see station notes. Sun = sunlight; RH = humidity.</p>
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
    drift=next((f for f in result.flags if f.issue=='sunlight-dependent temperature drift'),None)
    if drift:
        points=drift.evidence['daily_points']
        chart=line_chart([('Sunny residual',[p['sunny_residual'] for p in points],'#b15e32'),('Night residual',[p['night_residual'] for p in points],'#11675e')],f'{drift.station_id} temperature residuals','degrees C, target minus peer median',[p['day'] for p in points])
        plots.append(f'<section class="card"><h2>{esc(drift.station_id)} / least certain: sunlight-dependent warming</h2><p><span style="color:#b15e32">Orange: GHI &gt;300 W/m2</span>; <span style="color:#11675e">green: GHI &lt;5 W/m2</span>. Daily residuals use suitable peers after confirmed exclusions. A rising sunny residual with little first/last-week night change supports exposure bias, but does not prove paint caused it. The hinge-model onset is approximate. Settle it with a co-located, shielded reference comparison in sunlight.</p>{chart}</section>')
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
<script>document.getElementById('station').addEventListener('change',function(){{document.querySelectorAll('#ledger tbody tr').forEach(row=>row.hidden=this.value!==''&&row.dataset.station!==this.value)}});</script></body></html>"""
    path.write_text(body,encoding='utf-8')
