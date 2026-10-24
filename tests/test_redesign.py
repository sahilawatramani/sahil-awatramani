"""Regression contracts for bounded incidents, abstention and output integrity."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import timedelta
from test_checker import network, START
import test_checker as fixtures
from ridgeline.advanced import pressure_steps, wind_steps
from ridgeline.basic import basic_checks
from ridgeline.cli import main
from ridgeline.model import CHANNELS
from ridgeline.output import OUTPUTS, publish, sha256
from ridgeline.peers import Peers


class BoundedIncidentTests(unittest.TestCase):
    def inject(self, channel, size, days=12, duration=2):
        result=network(days=days,interval=10)
        begin=START+timedelta(days=4,hours=3)
        end=begin+timedelta(days=duration)
        for r in result.stations['Z0'].records:
            if begin<=r.time<end:
                if channel=='wind_kmh':r.values[channel]*=size
                else:r.values[channel]+=size
        return result,begin,end

    def assert_exact_mask(self,result,channel,begin,end):
        for sid,s in result.stations.items():
            for r in s.records:
                self.assertEqual(channel in r.excluded,sid=='Z0' and begin<=r.time<end)
                self.assertFalse(r.excluded-{channel})

    def test_pressure_recovers(self):
        result,begin,end=self.inject('pressure_hpa',7)
        pressure_steps(result,Peers(result))
        self.assert_exact_mask(result,'pressure_hpa',begin,end)
        self.assertEqual(result.flags[0].evidence['status'],'recovered')

    def test_short_wind_fault_recovers(self):
        result,begin,end=self.inject('wind_kmh',.28,duration=1)
        wind_steps(result,Peers(result))
        self.assert_exact_mask(result,'wind_kmh',begin,end)

    def multiple_incidents(self,channel,detector,size):
        result=network(days=18,interval=10)
        windows=[(START+timedelta(days=a),START+timedelta(days=b)) for a,b in ((4,6),(10,12))]
        for r in result.stations['Z0'].records:
            if any(a<=r.time<b for a,b in windows):
                if channel=='wind_kmh':r.values[channel]*=size
                else:r.values[channel]+=size
        detector(result,Peers(result))
        self.assertEqual([(f.start,f.end) for f in result.flags],[(a,b-result.stations['Z0'].step) for a,b in windows])
        for sid,s in result.stations.items():
            for r in s.records:
                self.assertEqual(channel in r.excluded,sid=='Z0' and any(a<=r.time<b for a,b in windows))

    def test_two_separate_pressure_faults_preserve_the_healthy_middle(self):
        self.multiple_incidents('pressure_hpa',pressure_steps,7)

    def test_two_separate_wind_faults_preserve_the_healthy_middle(self):
        self.multiple_incidents('wind_kmh',wind_steps,.28)

    def test_temperature_burst_is_bounded(self):
        result,begin,end=self.inject('temp_c',25,duration=2/24)
        basic_checks(result,Peers(result))
        self.assert_exact_mask(result,'temp_c',begin,end)
        self.assertEqual(result.flags[0].issue,'temperature error burst')

    def test_equal_groups_abstain_without_csv_keep_or_false_masks(self):
        result=network(days=12,interval=10)
        for sid in ('Z1','Z2'):
            for r in result.stations[sid].records[4*144:]:r.values['pressure_hpa']+=7
        pressure_steps(result,Peers(result))
        self.assertFalse(result.flags)
        self.assertEqual(len(result.unresolved),4)
        self.assertTrue(all(not r.excluded for s in result.stations.values() for r in s.records))

    def test_station_iteration_order_does_not_change_decisions(self):
        a,_,_=self.inject('pressure_hpa',7)
        b=copy.deepcopy(a);b.stations=dict(reversed(list(b.stations.items())))
        for result in (a,b):
            basic_checks(result,Peers(result));pressure_steps(result,Peers(result));wind_steps(result,Peers(result))
        def signature(result):return sorted(json.dumps(f.as_row(),sort_keys=True) for f in result.flags)
        self.assertEqual(signature(a),signature(b))


class OutputIntegrityTests(unittest.TestCase):
    def test_render_failure_leaves_previous_generation_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);fixtures.PackTests().write_pack(root)
            output=root/'output';output.mkdir();old=Path.cwd()
            try:
                os.chdir(output)
                self.assertEqual(main([str(root)]),0)
                before={name:(output/name).read_bytes() for name in (*OUTPUTS,'manifest.json')}
                with patch('ridgeline.cli.write_evidence',side_effect=OSError('simulated disk error')):
                    self.assertEqual(main([str(root)]),2)
                self.assertEqual(before,{name:(output/name).read_bytes() for name in before})
                manifest=json.loads((output/'manifest.json').read_text())
                self.assertEqual(manifest['outputs'],{name:sha256(output/name) for name in OUTPUTS})
            finally:os.chdir(old)

    def test_publish_rolls_back_an_ordinary_rename_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);stage=root/'stage';target=root/'out';stage.mkdir();target.mkdir()
            for name in OUTPUTS:(stage/name).write_text('new');(target/name).write_text('old')
            real_replace=os.replace;calls=[]
            def fail_once(source,destination):
                calls.append(str(source))
                if len(calls)==3:raise OSError('simulated rename failure')
                return real_replace(source,destination)
            with patch('ridgeline.output.os.replace',side_effect=fail_once):
                with self.assertRaises(OSError):publish(stage,target,'test')
            self.assertTrue(all((target/name).read_text()=='old' for name in OUTPUTS))
            self.assertFalse((target/'manifest.json').exists())
