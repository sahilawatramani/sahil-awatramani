"""Synthetic data, never the private assignment pack, is committed here."""
import csv
import math
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ridgeline.analyze import analyze
from ridgeline.basic import basic_checks, solar_elevation
from ridgeline.gps import coordinate, parse_line
from ridgeline.integrity import inspect_cadence, inspect_duplicates, repair_clocks
from ridgeline.model import CHANNELS, Analysis, Record, Station
from ridgeline.peers import Peers


START = datetime(2024, 6, 1)


def nmea(logger, payload):
    checksum = 0
    for char in payload:
        checksum ^= ord(char)
    return logger.isoformat(sep=' ') + ',$' + payload + f'*{checksum:02X}'


def rmc(logger, utc, status='A'):
    return nmea(logger, f"GPRMC,{utc:%H%M%S}.00,{status},4000.0000,N,10500.0000,W,0,0,{utc:%d%m%y},,,A")


def make_station(sid='X', days=3, interval=10, elevation=1600):
    s = Station(sid, 'Test '+sid, 40, -105, elevation, interval, START-timedelta(days=30))
    for i in range(int(days*1440/interval)):
        t = START + timedelta(minutes=i*interval)
        hour = (t.hour + t.minute/60)
        vals = dict(zip(CHANNELS, (10+5*math.sin(hour/24*2*math.pi), 40+10*math.cos(hour/24*2*math.pi),
                                  830+5*math.sin(i*interval/1440), 10+5*math.sin(i*.1), 360, 0,
                                  max(0,800*math.sin(math.radians(solar_elevation(t-s.step/2,40,-105)))))))
        s.records.append(Record(i+2,t,t,vals))
    return s


def network(days=42, interval=20):
    result = Analysis({})
    for j in range(4):
        s=make_station(f'Z{j}',days,interval,1500+100*j)
        s.lat+=j*.05
        for r in s.records:
            r.values['pressure_hpa']-=j*10
            r.values['temp_c']-=j*.4
            r.values['wind_kmh']*=1+j*.1
        result.stations[s.id]=s
    return result


class GpsTests(unittest.TestCase):
    def test_checksum_and_hemispheres(self):
        f, reason=parse_line(rmc(START,START))
        self.assertEqual(reason,'accepted_rmc'); self.assertEqual(f.lon,-105)
        self.assertEqual(parse_line(rmc(START,START)[:-2]+'FF')[1],'checksum_failed')
        self.assertEqual(coordinate('1230.0000','S'),-12.5)

    def test_bad_fix_and_malformed(self):
        self.assertEqual(parse_line(rmc(START,START,'V'))[1],'invalid_fix')
        self.assertEqual(parse_line('not nmea')[1],'malformed')
        with self.assertRaises(ValueError):coordinate('4061.0','N')

    def test_gga_quality(self):
        self.assertEqual(parse_line(nmea(START,'GPGGA,000000.00,4000,N,10500,W,0,0,99,1500,M,-17,M,,'))[1],'poor_gga_fix')
        f, reason=parse_line(nmea(START,'GPGGA,000000.00,4000,N,10500,W,1,7,1.2,1500,M,-17,M,,'))
        self.assertEqual(reason,'accepted_gga'); self.assertEqual(f.altitude_msl,1500)
        self.assertIsNone(f.utc)  # GGA alone cannot establish a date.

    def test_midnight_and_fractional_rmc(self):
        t=datetime(2024,6,2)
        f,_=parse_line(rmc(t-timedelta(hours=6),t))
        self.assertEqual(f.utc,t)
        payload='GNRMC,000000.50,A,4000,N,10500,W,0,0,020624,,,A'
        self.assertEqual(parse_line(nmea(t,payload))[0].utc,t+timedelta(seconds=.5))


class IntegrityTests(unittest.TestCase):
    def test_backward_clock_preserves_distinct_rows(self):
        s=make_station(days=3)
        boundary=144
        for r in s.records[boundary:]:r.raw-=timedelta(hours=6);r.time=r.raw
        for hour in range(72):
            t=START+timedelta(hours=hour)
            logger=t-(timedelta(hours=6) if hour>=24 else timedelta(0))
            s.gps.append(parse_line(rmc(logger,t))[0])
        a=Analysis({'X':s});repair_clocks(a);inspect_duplicates(a)
        self.assertEqual(s.records[boundary].time,START+timedelta(days=1))
        self.assertEqual(sum(r.removed for r in s.records),0)
        self.assertEqual(a.flags[0].evidence['offset_seconds'],21600)

    def test_clock_returns_to_normal(self):
        s=make_station(days=4)
        for r in s.records[144:288]:r.raw-=timedelta(hours=6);r.time=r.raw
        for hour in range(96):
            t=START+timedelta(hours=hour);off=timedelta(hours=6) if 24<=hour<48 else timedelta(0)
            s.gps.append(parse_line(rmc(t-off,t))[0])
        a=Analysis({'X':s});repair_clocks(a)
        self.assertEqual(s.records[288].time,START+timedelta(days=2))
        self.assertEqual(a.flags[0].end,START+timedelta(days=2,minutes=-10))

    def test_exact_and_conflicting_duplicates(self):
        s=make_station(days=1)
        r=s.records[10];s.records.append(Record(999,r.raw,r.time,dict(r.values)))
        r=s.records[20];values=dict(r.values);values['temp_c']+=1
        s.records.append(Record(1000,r.raw,r.time,values))
        a=Analysis({'X':s});inspect_duplicates(a)
        self.assertEqual(sum(r.removed for r in s.records),1)
        self.assertEqual({f.issue for f in a.flags},{'exact retransmission','conflicting duplicate'})
        self.assertTrue(all(c in s.records[20].excluded for c in CHANNELS))

    def test_gap_counts_and_alternate_cadence(self):
        s=make_station(days=1,interval=20);del s.records[10:13]
        a=Analysis({'X':s});inspect_cadence(a)
        self.assertEqual(a.flags[0].evidence['missing_slots'],3)
        self.assertEqual(a.flags[0].start,START+timedelta(minutes=200))

    def test_initial_offset(self):
        s=make_station(days=1)
        for r in s.records:r.raw+=timedelta(hours=1);r.time=r.raw
        for h in range(24):
            t=START+timedelta(hours=h);s.gps.append(parse_line(rmc(t+timedelta(hours=1),t))[0])
        a=Analysis({'X':s});repair_clocks(a)
        self.assertEqual(s.records[0].time,START)


class SensorTests(unittest.TestCase):
    def test_healthy_dry_nights_and_direction_360(self):
        a=network(days=3);basic_checks(a,Peers(a));self.assertEqual(a.flags,[])

    def test_frozen_and_spike_are_channel_specific(self):
        a=network(days=5);s=a.stations['Z0']
        for r in s.records[72:216]:r.values['temp_c']=7.25
        s.records[300].values['temp_c']=-50
        basic_checks(a,Peers(a))
        self.assertIn('sensor frozen',[f.issue for f in a.flags])
        self.assertIn('isolated temperature spike',[f.issue for f in a.flags])
        self.assertNotIn('rh_pct',s.records[100].excluded)

    def test_nonfinite_and_humidity_episode(self):
        a=network(days=4);s=a.stations['Z0'];s.records[0].values['pressure_hpa']=math.nan
        for r in s.records[72:144]:r.values['rh_pct']=102
        basic_checks(a,Peers(a))
        self.assertEqual(sum(f.issue=='humidity saturation failure' for f in a.flags),1)
        self.assertIn('pressure_hpa',s.records[0].excluded)

    def test_pressure_step_not_elevation_difference(self):
        from ridgeline.advanced import pressure_steps
        a=network(days=10);p=Peers(a);pressure_steps(a,p);self.assertFalse(a.flags)
        for r in a.stations['Z0'].records[360:]:r.values['pressure_hpa']+=7
        pressure_steps(a,Peers(a))
        self.assertEqual([(f.station_id,f.issue) for f in a.flags],[('Z0','pressure calibration step')])

    def test_persistent_wind_scale(self):
        from ridgeline.advanced import wind_steps
        a=network();s=a.stations['Z0']
        for r in s.records[24*72:]:r.values['wind_kmh']*=.28
        wind_steps(a,Peers(a))
        self.assertEqual({f.station_id for f in a.flags},{'Z0'})
        self.assertEqual(a.flags[0].action,'exclude')

    def test_no_reference_abstains(self):
        from ridgeline.advanced import pressure_steps,wind_steps,daylight_temperature_drift
        s=make_station(days=30);a=Analysis({'X':s});p=Peers(a)
        pressure_steps(a,p);wind_steps(a,p);daylight_temperature_drift(a,p)
        self.assertFalse(a.flags)

    def test_solar_longitude_and_utc(self):
        self.assertGreater(solar_elevation(datetime(2024,6,1,19),40,-105),60)
        self.assertLess(solar_elevation(datetime(2024,6,1,7),40,-105),-20)
        # 00 UTC in Colorado is not local midnight.
        self.assertGreater(solar_elevation(datetime(2024,6,1,0),40,-105),0)


class PackTests(unittest.TestCase):
    def write_pack(self,root):
        (root/'data').mkdir();s=make_station('RENAMED',days=1,interval=20)
        with (root/'stations.csv').open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['station_id','name','lat','lon','elevation_m','installed','logger_interval_min'])
            w.writerow(['RENAMED','New name',40,-105,1600,'2024-01-01',20])
        with (root/'data/RENAMED.csv').open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['timestamp_utc',*CHANNELS])
            for r in s.records:w.writerow([r.time.strftime('%Y-%m-%d %H:%M'),*[r.values[c] for c in CHANNELS]])

    def test_missing_gps_arbitrary_ids_and_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.write_pack(root);a=analyze(root)
            self.assertFalse(a.flags);self.assertTrue(a.warnings)

    def test_invalid_timestamp_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.write_pack(root);path=root/'data/RENAMED.csv'
            path.write_text(path.read_text().replace('2024-06-01 00:00','bad date'))
            with self.assertRaisesRegex(ValueError,'invalid timestamp'):analyze(root)


if __name__=='__main__':unittest.main()
