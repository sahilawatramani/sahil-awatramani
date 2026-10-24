"""Controlled review counterexamples; all observations are synthetic.

Run: python benchmarks/review_cases.py --output tmp/review_results.json
This is a diagnostic baseline, not an estimate of real-world accuracy.
"""
import argparse
import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
from test_checker import network, START
from ridgeline.advanced import pressure_steps, wind_steps
from ridgeline.basic import basic_checks
from ridgeline.peers import Peers


def measure(name, result, channel, truth, detector):
    detector(result, Peers(result))
    tp = fp = fn = tn = 0
    for sid, station in result.stations.items():
        for record in station.records:
            actual = truth(sid, record)
            predicted = channel in record.excluded
            if actual and predicted:
                tp += 1
            elif actual:
                fn += 1
            elif predicted:
                fp += 1
            else:
                tn += 1
    return {'case': name, 'channel': channel, 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'precision': tp/(tp+fp) if tp+fp else None,
            'recall': tp/(tp+fn) if tp+fn else None,
            'flags': [f.as_row() for f in result.flags]}


def run_cases():
    rows = []
    result = network(interval=10)
    start, end = START+timedelta(days=12), START+timedelta(days=17)
    for record in result.stations['Z0'].records:
        if start <= record.time < end:
            record.values['pressure_hpa'] += 7
    rows.append(measure('five_day_pressure_fault_then_recovery', result, 'pressure_hpa',
                        lambda sid,r: sid=='Z0' and start<=r.time<end, pressure_steps))

    result = network(interval=10)
    start, end = START+timedelta(days=20), START+timedelta(days=23)
    for record in result.stations['Z0'].records:
        if start <= record.time < end:
            record.values['wind_kmh'] *= .28
    rows.append(measure('three_day_wind_scale_fault_then_recovery', result, 'wind_kmh',
                        lambda sid,r: sid=='Z0' and start<=r.time<end, wind_steps))

    result = network(interval=10)
    start, end = START+timedelta(days=8,hours=12), START+timedelta(days=8,hours=14)
    for record in result.stations['Z0'].records:
        if start <= record.time < end:
            record.values['temp_c'] += 30
    rows.append(measure('two_hour_temperature_error_burst', result, 'temp_c',
                        lambda sid,r: sid=='Z0' and start<=r.time<end, basic_checks))

    result = network(interval=10)
    start, end = START+timedelta(days=12), START+timedelta(days=42)
    for sid in ('Z1','Z2'):
        for record in result.stations[sid].records:
            if record.time >= start:
                record.values['pressure_hpa'] += 7
    rows.append(measure('two_of_four_pressure_boards_shift_together', result, 'pressure_hpa',
                        lambda sid,r: sid in ('Z1','Z2') and start<=r.time<end, pressure_steps))

    result = network(interval=10)
    start, end = START+timedelta(days=12), START+timedelta(days=15)
    for station in result.stations.values():
        for record in station.records:
            if start <= record.time < end:
                record.values['temp_c'] += 8
    rows.append(measure('real_regional_temperature_change', result, 'temp_c',
                        lambda sid,r: False, basic_checks))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    report = {'engine_commit': commit, 'stations': 4, 'cadence_minutes': 10,
              'duration_days': 42, 'scope': 'targeted synthetic counterexamples, not field accuracy',
              'cases': run_cases()}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    for case in report['cases']:
        print(json.dumps({k:v for k,v in case.items() if k!='flags'}))


if __name__ == '__main__':
    main()
