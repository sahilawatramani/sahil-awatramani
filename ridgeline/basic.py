from __future__ import annotations
from datetime import timedelta
import calendar
import math
from .model import CHANNELS, Analysis, correlation, med, runs
from .model import mad
from .config import DEFAULTS as CFG
from .incidents import windows

# Broad sanity bounds, not a claim that this network's climate fills these ranges.
BOUNDS = {'temp_c': (-90, 60), 'rh_pct': (0, 100), 'pressure_hpa': (300, 1100),
          'wind_kmh': (0, 350), 'wind_dir_deg': (0, 360), 'rain_mm': (0, math.inf),
          'ghi_wm2': (-5, 1600)}


def solar_elevation(time, lat: float, lon: float) -> float:
    """NOAA fractional-year approximation, east-positive longitude, UTC input."""
    hour = time.hour + time.minute / 60 + time.second / 3600
    gamma = 2 * math.pi / (366 if calendar.isleap(time.year) else 365) * (time.timetuple().tm_yday - 1 + (hour - 12) / 24)
    eq = 229.18 * (.000075 + .001868 * math.cos(gamma) - .032077 * math.sin(gamma)
                   - .014615 * math.cos(2 * gamma) - .040849 * math.sin(2 * gamma))
    decl = (.006918 - .399912 * math.cos(gamma) + .070257 * math.sin(gamma)
            - .006758 * math.cos(2 * gamma) + .000907 * math.sin(2 * gamma)
            - .002697 * math.cos(3 * gamma) + .00148 * math.sin(3 * gamma))
    hour_angle = math.radians(((hour * 60 + eq + 4 * lon) % 1440) / 4 - 180)
    latitude = math.radians(lat)
    sine = math.sin(latitude) * math.sin(decl) + math.cos(latitude) * math.cos(decl) * math.cos(hour_angle)
    return math.degrees(math.asin(max(-1, min(1, sine))))


def saturated_humidity(result: Analysis, peers) -> None:
    for station in result.stations.values():
        records = sorted((r for r in station.records if not r.removed and not r.clock_unsafe), key=lambda r: r.time)
        for group in runs(records, (r.values['rh_pct'] >= 98 for r in records), station.step):
            if len(group) * station.interval < 12 * 60:
                continue
            impossible = sum(r.values['rh_pct'] > 100 for r in group)
            residuals = [peers.residual(station, r, 'rh_pct') for r in group if r.values['ghi_wm2'] > 250]
            disagreement = med(residuals)
            if impossible >= 3 or disagreement > 25:
                result.add(station, 'rh_pct', group[0].time, group[-1].time, 'humidity saturation failure', 'exclude',
                           f"Humidity remains at least 98% for {len(group) * station.interval / 60:.1f} hours, including {impossible} values above 100%; exclude the whole saturated episode, not just impossible samples.",
                           impossible_samples=impossible, samples=len(group), sunny_peer_difference=disagreement if math.isfinite(disagreement) else None)


def basic_checks(result: Analysis, peers) -> None:
    # Hard failures are admitted before temporal/spatial hypotheses. Each stage
    # sees one shared mask snapshot, independently of inventory iteration order.
    with result.stage():
        saturated_humidity(result,peers)
    with result.stage():
        sanity_checks(result)
    with result.stage():
        temporal_checks(result,peers)
    temperature_bursts(result,peers)


def sanity_checks(result: Analysis) -> None:
    for station in result.stations.values():
        records=sorted(station.index().values(),key=lambda r:r.time)
        for channel,(low,high) in BOUNDS.items():
            selected=[channel not in r.excluded and (not math.isfinite(r.values[channel]) or not low<=r.values[channel]<=high) for r in records]
            for group in runs(records,selected,station.step):
                values=[r.values[channel] for r in group]
                text='Non-finite or missing numeric values' if any(not math.isfinite(v) for v in values) else f'Values {min(values):g} to {max(values):g} outside broad sanity range [{low:g}, {high:g}]'
                result.add(station,channel,group[0].time,group[-1].time,'invalid value','exclude',text+'; do not clip or impute observations.')


def temporal_checks(result: Analysis, peers) -> None:
    for station in result.stations.values():
        records=sorted(station.index().values(),key=lambda r:r.time)
        # Equal readings must persist for at least 12 h, with independent variation.
        for channel, peer_span in (('temp_c', 3), ('pressure_hpa', 2), ('rh_pct', 15)):
            blocks, current = [], []
            for r in records:
                if current and (r.time - current[-1].time != station.step or r.value(channel) != current[-1].value(channel)):
                    blocks.append(current)
                    current = []
                current.append(r)
            if current:
                blocks.append(current)
            for group in blocks:
                if len(group) * station.interval < 720 or not math.isfinite(group[0].value(channel)):
                    continue
                if channel == 'rh_pct' and group[0].values[channel] >= 98:
                    continue
                reference = [med(peers.values(station, r, channel)) for r in group]
                reference = [v for v in reference if math.isfinite(v)]
                internal = max(r.values['ghi_wm2'] for r in group) - min(r.values['ghi_wm2'] for r in group)
                if (len(reference) >= len(group) * .7 and max(reference) - min(reference) >= peer_span) or (channel == 'temp_c' and len(group) * station.interval >= 1440 and internal > 200):
                    result.add(station, channel, group[0].time, group[-1].time, 'sensor frozen', 'exclude',
                               f"{len(group)} consecutive readings are exactly {group[0].values[channel]:g} while independent conditions vary; exclude this sensor interval.", samples=len(group), value=group[0].values[channel])
        # Isolated reversals; a rapid but sustained real front does not satisfy this.
        selected = []
        for i, r in enumerate(records):
            neighbours = records[max(0, i-3):i] + records[i+1:i+4]
            neighbours = [n for n in neighbours if abs(n.time-r.time) <= timedelta(minutes=max(30, station.interval * 3))]
            vals = [n.value('temp_c') for n in neighbours if math.isfinite(n.value('temp_c'))]
            value = r.value('temp_c')
            selected.append(len(vals) >= 4 and math.isfinite(value) and abs(value-med(vals)) > 12 and max(vals)-min(vals) < 5)
        for group in runs(records, selected, station.step):
            result.add(station, 'temp_c', group[0].time, group[-1].time, 'isolated temperature spike', 'exclude',
                       "Temperature differs by over 12 C from at least four nearby readings whose range is under 5 C and immediately returns to baseline.")
        if station.id not in peers.disputed:
            nighttime = [r.values['ghi_wm2'] > 30 and 'ghi_wm2' not in r.excluded and solar_elevation(r.time - station.step / 2, station.lat, station.lon) < -6 for r in records]
            for group in runs(records, nighttime, station.step):
                if len(group) * station.interval >= 30:
                    result.add(station, 'ghi_wm2', group[0].time, group[-1].time, 'sunlight during astronomical night', 'exclude',
                               "GHI exceeds 30 W/m2 for at least 30 minutes with midpoint solar elevation below -6 degrees after supported clock correction.", 'medium')


def temperature_bursts(result: Analysis, peers) -> None:
    """Paired abrupt edges with clean context catch clustered, in-range errors."""
    from bisect import bisect_left
    with result.stage():
        for station in result.stations.values():
            records=sorted(station.index().values(),key=lambda r:r.time)
            times=[r.time for r in records]
            residuals=[peers.residual(station,r,'temp_c') for r in records]
            covered=set()
            for i in range(1,len(records)):
                jump=residuals[i]-residuals[i-1]
                if i in covered or not math.isfinite(jump) or abs(jump)<CFG.temperature_burst_c:continue
                if times[i]-times[i-1]!=station.step:continue
                a=bisect_left(times,times[i]-timedelta(hours=CFG.temperature_context_hours))
                before=residuals[a:i]
                if sum(math.isfinite(v) for v in before)<CFG.temperature_context_hours*60/station.interval*.75:continue
                baseline=med(before)
                for j in range(i+1,len(records)):
                    if times[j]-times[i]>timedelta(hours=CFG.temperature_burst_max_hours):break
                    if times[j]-times[j-1]!=station.step:break
                    reverse=residuals[j]-residuals[j-1]
                    if not math.isfinite(reverse) or reverse*jump>=0 or abs(reverse)<CFG.temperature_burst_c:continue
                    b=bisect_left(times,times[j]+timedelta(hours=CFG.temperature_context_hours))
                    after=residuals[j:b]
                    if sum(math.isfinite(v) for v in after)<CFG.temperature_context_hours*60/station.interval*.75:continue
                    if abs(med(after)-baseline)>3:continue
                    values=residuals[i:j];level=med(values)-baseline
                    noise=max(.3,1.4826*max(mad(before),mad(after)))
                    if abs(level)<max(CFG.temperature_burst_c,CFG.robust_noise_multiplier*noise):continue
                    if any(not math.isfinite(v) or abs(v-baseline)<CFG.temperature_burst_c*.75 for v in values):continue
                    result.add(station,'temp_c',times[i],times[j-1],'temperature error burst','exclude',
                               f"Temperature residual jumps {level:+.1f} C for {len(values)*station.interval:g} minutes then returns within 3 C of its prior peer-relative level, with clean three-hour context on both sides; exclude this bounded excursion.",
                               samples=len(values),peer_residual_change_c=round(level,3),
                               recovery_utc=times[j].isoformat(sep=' ',timespec='minutes'),status='recovered',
                               source_row_start=records[i].row,source_row_end=records[j-1].row)
                    covered.update(range(i,j));break


def retain_mountain_weather(result: Analysis, peers) -> None:
    for station in result.stations.values():
        reference_stations = peers.select(station, elevation_limit=2500)
        if len(reference_stations) < 2 or station.elevation - med(s.elevation for s in reference_stations) < 750:
            continue
        a, b = [], []
        for r in station.records:
            vals = [peers.indices[s.id][r.time].value('temp_c') for s in reference_stations if r.time in peers.indices[s.id]]
            value, ref = r.value('temp_c'), med(vals)
            if math.isfinite(value) and math.isfinite(ref):
                a.append(value); b.append(ref)
        if len(a) >= 144 and correlation(a, b) > .8 and med(x-y for x,y in zip(a,b)) < -3:
            result.add(station, 'temp_c', *station.bounds, 'coherent mountain cold', 'keep',
                       f"The site is over 750 m above comparison stations and its colder temperature tracks regional weather (r={correlation(a,b):.2f}); retain rather than applying lowland limits.",
                       correlation=round(correlation(a,b),3), temperature_difference=round(med(x-y for x,y in zip(a,b)),2))
