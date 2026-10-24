import argparse
import csv
import json
import sys
import hashlib
from pathlib import Path
from .analyze import analyze
from .model import FIELDS
from .report import audit, write_evidence, write_report


def main(argv=None):
    parser=argparse.ArgumentParser(description='Check a weather data pack; write flags.csv, report.html, evidence.html and audit.json in the current directory.')
    parser.add_argument('pack',type=Path,help='Data pack folder containing stations.csv, data/ and optional gps/')
    args=parser.parse_args(argv)
    try:
        result=analyze(args.pack)
        data=audit(result)
        inputs=[args.pack/'stations.csv',args.pack/'maintenance_log.md']
        inputs+=sorted((args.pack/'data').glob('*.csv'))+sorted((args.pack/'gps').glob('*.nmea'))
        data['input_hashes']={str(p.relative_to(args.pack)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs if p.is_file()}
        with Path('flags.csv').open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader()
            writer.writerows(f.as_row() for f in result.flags)
        write_report(result,data,Path('report.html'))
        write_evidence(result,data,Path('evidence.html'))
        Path('audit.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    except (ValueError,OSError) as error:
        print(f'Checker error: {error}',file=sys.stderr)
        return 2
    for warning in result.warnings:
        print(f'Warning: {warning}',file=sys.stderr)
    print(f'Checked {len(result.stations)} stations; wrote {len(result.flags)} incident intervals to flags.csv.')
    print('Coordinator: report.html | Evidence: evidence.html | Audit: audit.json')
    return 0
