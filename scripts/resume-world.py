"""One resumable background download; honors both Wikidata service cooldowns.

It exits after importing and validating the complete local catalog. It does not
publish the site, change access, or keep a recurring daemon running.
"""
import concurrent.futures
import fcntl
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / 'data/raw/world'
STOP = threading.Event()
STATUS_LOCK = threading.Lock()
STATUS = {'state': 'running', 'pid': os.getpid(), 'startedAt': datetime.now(timezone.utc).isoformat()}


def status(**fields):
    with STATUS_LOCK:
        STATUS.update(fields, updatedAt=datetime.now(timezone.utc).isoformat())
        tmp = ROOT / 'download-status.tmp'
        tmp.write_text(json.dumps(STATUS, ensure_ascii=False, indent=2)); tmp.replace(ROOT / 'download-status.json')


def wait_service(name):
    path = ROOT / ('rate-limit.json' if name == 'ids' else 'api-rate-limit.json')
    if not path.exists(): return
    deadline = json.loads(path.read_text()).get('retryAt', 0)
    if deadline <= time.time(): return
    status(**{name + 'State': 'waiting', name + 'ResumeAt': datetime.fromtimestamp(deadline, timezone.utc).isoformat()})
    print(f'{name}: honoring Retry-After until {datetime.fromtimestamp(deadline).isoformat()}', flush=True)
    while deadline > time.time():
        if STOP.wait(min(30, max(0, deadline - time.time()))): raise RuntimeError('Download stopped')


def run(script, *args):
    if STOP.is_set(): raise RuntimeError('Download stopped')
    return subprocess.run([sys.executable, str(PROJECT / 'scripts' / script), *args], cwd=PROJECT).returncode


def discover_ids():
    broad_failed = (ROOT / 'global-query-failed.json').exists()
    while not (ROOT / 'ids.json').exists():
        wait_service('ids')
        status(idsState='downloading')
        args = ['--ids-only'] + ([] if broad_failed else ['--global-ids'])
        result = run('fetch-world.py', *args)
        if result == 75: continue
        if result and not broad_failed:
            broad_failed = True
            (ROOT / 'global-query-failed.json').write_text(json.dumps({'time': time.time(), 'exitCode': result}))
            continue
        if result: raise RuntimeError(f'City discovery exited with {result}')
    count = len(json.loads((ROOT / 'ids.json').read_text()))
    status(idsState='complete', cityIds=count)
    print(f'Full city census ready: {count}', flush=True)


def download_entities():
    while True:
        wait_service('entities')
        complete_ids = (ROOT / 'ids.json').exists()
        status(entitiesState='downloading')
        result = run('fetch-world-entities.py', *([] if complete_ids else ['--known-only']))
        if result == 75: continue
        if result: raise RuntimeError(f'Entity download exited with {result}')
        if complete_ids:
            status(entitiesState='complete')
            return
        status(entitiesState='waiting-for-census')
        while not (ROOT / 'ids.json').exists():
            if STOP.wait(10): raise RuntimeError('Download stopped')


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'download.lock').open('w') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another world download is already running.', flush=True)
            return
        status()
        print(f'Started world download PID {os.getpid()}', flush=True)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                jobs = [pool.submit(discover_ids), pool.submit(download_entities)]
                for job in concurrent.futures.as_completed(jobs):
                    try: job.result()
                    except Exception:
                        STOP.set()
                        raise
            status(state='importing')
            result = run('import-world.py')
            if result: raise RuntimeError(f'World import exited with {result}')
            status(state='validating')
            result = subprocess.run(['npm', 'test'], cwd=PROJECT).returncode
            if result: raise RuntimeError(f'World catalog validation exited with {result}')
            summary = json.loads((PROJECT / 'public/coverage-summary.json').read_text())
            status(state='complete', catalogCities=summary['total'])
            print(f"Complete: local atlas now has {summary['total']} cities. Site has not been published.", flush=True)
        except Exception as error:
            STOP.set()
            status(state='failed', error=str(error))
            raise

if __name__ == '__main__': main()
