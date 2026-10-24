"""Read-only local checks for obvious submission omissions; no publication."""
import csv
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    failures = []

    def check(ok, label):
        print(('READY     ' if ok else 'NEEDS YOU ') + label)
        if not ok:
            failures.append(label)

    required = ['checker.py', 'flags.csv', 'report.html', 'README.md', 'DECISIONS.md']
    check(all((ROOT / name).is_file() for name in required), 'Required root files exist')
    readme = (ROOT / 'README.md').read_text(encoding='utf-8').splitlines() if (ROOT / 'README.md').exists() else []
    check(len(readme) >= 4 and bool(readme[0].strip()) and '@' in readme[1]
          and readme[3].startswith('Run: '), 'README starts with name, email, video and Run lines')
    video = readme[2] if len(readme) >= 3 else ''
    check(bool(re.search(r'https://\S+', video)) and not re.search(r'TO ADD|TODO|PLACEHOLDER', video, re.I),
          'Actual recording link appears on README line three')
    decisions = (ROOT / 'DECISIONS.md').read_text(encoding='utf-8') if (ROOT / 'DECISIONS.md').exists() else ''
    markers = ('technical draft', 'complete personally', 'complete without code or ai', 'deliberately left for you')
    check(bool(decisions.strip()) and not any(marker in decisions.lower() for marker in markers),
          'Personal DECISIONS.md replaces the technical draft and unfinished sections')
    exports = [p for p in (ROOT / 'ai_logs').rglob('*') if p.is_file()
               and p.name.lower() not in ('readme.md', '.gitkeep') and p.stat().st_size]
    check(bool(exports), 'AI export files or genuine conversation share links have been added')
    try:
        with (ROOT / 'flags.csv').open(encoding='utf-8', newline='') as stream:
            reader = csv.DictReader(stream)
            schema = ['station_id','channel','start_utc','end_utc','issue','action','note']
            valid = reader.fieldnames == schema
            for row in reader:
                start = datetime.strptime(row['start_utc'], '%Y-%m-%d %H:%M')
                end = datetime.strptime(row['end_utc'], '%Y-%m-%d %H:%M')
                valid = valid and start <= end and row['action'] in ('keep','correct','exclude')
                valid = valid and all(row.get(key, '').strip() for key in schema)
        check(valid, 'flags.csv has the required schema and valid decisions/intervals')
    except (OSError, ValueError, KeyError, TypeError):
        check(False, 'flags.csv is readable and has valid required fields')
    try:
        manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
        audit=json.loads((ROOT/'audit.json').read_text(encoding='utf-8'))
        hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                for name in ('flags.csv','report.html','evidence.html','audit.json')}
        check(manifest['outputs']==hashes and manifest['generation_id']==audit['generation']['id'],
              'Output manifest matches one complete generation')
    except (OSError,ValueError,KeyError,TypeError):
        check(False,'Output manifest matches one complete generation')
    try:
        tracked = subprocess.check_output(['git','ls-files'], cwd=ROOT, text=True).splitlines()
        history = subprocess.check_output(['git','rev-list','--objects','--all'], cwd=ROOT, text=True).splitlines()
        paths = tracked + [line.split(' ',1)[1] for line in history if ' ' in line]
        private = [p for p in paths if p.lower().endswith(('.nmea','.zip'))
                   or p.lower().startswith(('data/','gps/','tmp/'))
                   or 'ridgeline_data_pack' in p.lower()
                   or (p.lower().endswith('.csv') and p != 'flags.csv')]
        check(not private, 'No obvious source-pack files in tracked paths or Git history')
    except (OSError, subprocess.CalledProcessError):
        check(False, 'Git tracked-file and history audit could be completed')
    print('\nManual checks still required: verify the exact deadline, full chat exports, recording access/length,')
    print('personal authorship, unaided calculation, document length and A4 layout; then publish and submit the form.')
    print('This checker cannot verify those human requirements or submit anything.')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
