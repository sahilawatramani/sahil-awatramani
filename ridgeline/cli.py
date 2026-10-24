import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path
from .analyze import analyze
from .model import FIELDS
from .report import audit, write_evidence, write_report
from .output import generation, publish, source_hashes


def main(argv=None):
    parser=argparse.ArgumentParser(description='Check a weather data pack; write flags.csv, report.html, evidence.html and audit.json in the current directory.')
    parser.add_argument('pack',type=Path,help='Data pack folder containing stations.csv, data/ and optional gps/')
    args=parser.parse_args(argv)
    try:
        inputs=source_hashes(args.pack)
        result=analyze(args.pack)
        if inputs!=source_hashes(args.pack):
            raise ValueError('Input files changed during analysis; rerun against a stable pack')
        data=audit(result)
        data['input_hashes']=inputs
        data['generation']=generation(inputs)
        with tempfile.TemporaryDirectory(prefix='.ridgeline-',dir=Path.cwd()) as temporary:
            stage=Path(temporary)
            with (stage/'flags.csv').open('w',encoding='utf-8',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader()
                writer.writerows(f.as_row() for f in result.flags)
            write_report(result,data,stage/'report.html')
            write_evidence(result,data,stage/'evidence.html')
            (stage/'audit.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
            publish(stage,Path.cwd(),data['generation']['id'])
    except (ValueError,OSError) as error:
        print(f'Checker error: {error}',file=sys.stderr)
        return 2
    for warning in result.warnings:
        print(f'Warning: {warning}',file=sys.stderr)
    print(f'Checked {len(result.stations)} stations; wrote {len(result.flags)} incident intervals to flags.csv.')
    print('Coordinator: report.html | Evidence: evidence.html | Audit: audit.json')
    return 0
