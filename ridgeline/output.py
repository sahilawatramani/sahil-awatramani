"""Stage a complete generation, then publish with a manifest commit marker."""
import hashlib
import json
import os
from pathlib import Path
import shutil

OUTPUTS=('flags.csv','report.html','evidence.html','audit.json')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(pack):
    paths=[pack/'stations.csv',pack/'maintenance_log.md']
    paths+=sorted((pack/'data').glob('*.csv'))+sorted((pack/'gps').glob('*.nmea'))
    return {p.relative_to(pack).as_posix():sha256(p) for p in paths if p.is_file()}


def generation(inputs):
    root=Path(__file__).resolve().parents[1]
    paths=[root/'checker.py']+sorted((root/'ridgeline').glob('*.py'))
    engine=hashlib.sha256('\n'.join(p.name+':'+sha256(p) for p in paths).encode()).hexdigest()
    digest=hashlib.sha256(json.dumps(dict(inputs=inputs,engine=engine),sort_keys=True).encode()).hexdigest()
    return dict(id=digest[:20],engine_sha256=engine,
                contract='manifest.json is the final commit marker; verify all output hashes after an interrupted run')


def publish(stage, target, generation_id):
    """Individual renames are atomic; rollback on ordinary write errors.

    A crash between renames is detectable by the old/missing manifest. There is
    no claim of filesystem-wide atomicity across five separate filenames.
    """
    manifest=dict(generation_id=generation_id,outputs={name:sha256(stage/name) for name in OUTPUTS})
    (stage/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    names=(*OUTPUTS,'manifest.json')
    backups=stage/'previous';backups.mkdir()
    for name in names:
        if (target/name).exists():shutil.copy2(target/name,backups/name)
    replaced=[]
    try:
        for name in names:
            os.replace(stage/name,target/name);replaced.append(name)
    except OSError:
        for name in reversed(replaced):
            if (backups/name).exists():os.replace(backups/name,target/name)
            else:(target/name).unlink(missing_ok=True)
        raise
