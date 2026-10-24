"""Regression cases found during the second correctness review."""
import csv
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

import test_checker as fixtures
from test_checker import START, make_station, network
from ridgeline.advanced import pressure_steps
from ridgeline.analyze import analyze
from ridgeline.integrity import inspect_cadence, inspect_duplicates
from ridgeline.model import Analysis, CHANNELS, Record
from ridgeline.peers import Peers
from ridgeline.report import audit, write_report


class MissingStationTests(unittest.TestCase):
    def make_pack(self, root, empty=False):
        fixtures.PackTests().write_pack(root)
        with (root/'stations.csv').open('a',newline='') as f:
            csv.writer(f).writerow(['ABSENT','Absent site',40.1,-105,1600,'2024-01-01',20])
        if empty:
            (root/'data/ABSENT.csv').write_text('timestamp_utc,'+','.join(CHANNELS)+'\n')

    def test_missing_whole_file_has_an_exclusion_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make_pack(root);result=analyze(root)
            flags=[f for f in result.flags if f.station_id=='ABSENT']
            self.assertEqual(len(flags),1)
            self.assertEqual((flags[0].channel,flags[0].action),('all','exclude'))
            self.assertEqual(flags[0].evidence['missing_slots'],72)
            self.assertEqual(audit(result)['stations']['ABSENT']['missing_slots'],72)

    def test_empty_file_has_an_exclusion_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make_pack(root,empty=True);result=analyze(root)
            self.assertTrue(any(f.station_id=='ABSENT' and f.issue=='empty weather file' for f in result.flags))


class CoverageTests(unittest.TestCase):
    def test_extra_off_cadence_rows_do_not_inflate_coverage(self):
        s=make_station(days=1,interval=5);s.interval=10
        result=Analysis({'X':s});inspect_cadence(result);data=audit(result)
        self.assertEqual(data['stations']['X']['channels']['temp_c']['percent'],100)
        self.assertEqual(data['stations']['X']['present_slots'],144)
        self.assertEqual(sum(f.issue=='irregular cadence' for f in result.flags),1)

    def test_unresolved_clock_is_not_deduplicated(self):
        s=make_station(days=1)
        r=s.records[0]
        duplicate=Record(999,r.raw,r.time,dict(r.values),clock_unsafe=True)
        s.records.append(duplicate)
        for r in s.records:r.clock_unsafe=True
        result=Analysis({'X':s});inspect_duplicates(result)
        self.assertFalse(any(r.removed for r in s.records))
        self.assertFalse(result.flags)

    def test_inventory_date_conflict_does_not_crash_report(self):
        s=make_station(days=1);s.installed=START+timedelta(days=5)
        result=Analysis({'X':s});inspect_cadence(result);data=audit(result)
        self.assertEqual(data['stations']['X']['channels']['temp_c']['usable'],0)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.html';write_report(result,data,path)
            self.assertIn('N/A',path.read_text())


class PressureWindowTests(unittest.TestCase):
    def test_outage_cannot_supply_stale_before_window(self):
        result=network(days=12);s=result.stations['Z0']
        boundary=6*72
        for r in s.records[boundary:]:r.values['pressure_hpa']+=7
        s.records=s.records[:72]+s.records[boundary-1:]
        pressure_steps(result,Peers(result))
        self.assertFalse(any(f.station_id=='Z0' for f in result.flags))
