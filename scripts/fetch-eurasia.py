"""Download Eurasia first, reusing world cache; never mark the world complete."""
import fcntl
import importlib.util
import json
import os
import time
from pathlib import Path
from world_entities import EntityCache, Deferred, targets, rows_for, write_gzip

ROOT = Path('data/raw/world')
spec = importlib.util.spec_from_file_location('world_fetch', Path(__file__).with_name('fetch-world.py'))
wdqs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wdqs)
SCOPE = ROOT / 'eurasia'
QUERY = wdqs.IDS_QUERY.replace('FILTER NOT EXISTS', '''FILTER EXISTS {
 { ?city wdt:P30 ?continent. }
 UNION { ?city wdt:P17/wdt:P30 ?continent. }
 UNION { ?city wdt:P131/wdt:P30 ?continent. }
 VALUES ?continent { wd:Q46 wd:Q48 }
 }
 FILTER NOT EXISTS''')


def status(**fields):
    path = SCOPE / 'status.json'
    old = json.loads(path.read_text()) if path.exists() else {}
    wdqs.save(path, {**old, **fields, 'pid': os.getpid(), 'updatedAt': time.time()})


def main():
    SCOPE.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'download.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            try:
                status(state='discovering')
                ids_path = SCOPE / 'ids.json'
                if not ids_path.exists():
                    rows = wdqs.fetch(QUERY)
                    world = set(json.loads((ROOT / 'ids.json').read_text()))
                    ids = sorted({r['city']['value'].rsplit('/', 1)[-1] for r in rows} & world, key=lambda q: int(q[1:]))
                    if not ids: raise ValueError('Empty Eurasia census')
                    wdqs.save(ids_path, ids)
                    wdqs.save(SCOPE / 'selection.json', {'query': QUERY, 'retrievedAt': time.time(), 'scope': 'Cities in world census linked to Europe or Asia by city, immediate administration, or country. Transcontinental countries included in full for download; geographic classification remains separate.'})
                ids = json.loads(ids_path.read_text())
                cache = EntityCache(ROOT)
                status(state='downloading', total=len(ids), cached=len(set(ids) & cache.entities.keys()))
                print(f'Eurasia: {len(ids)} cities; {len(set(ids) & cache.entities.keys())} cached', flush=True)
                cache.ensure(ids)
                status(state='related-entities', cached=len(ids))
                related = {q for city in ids for prop in ['P17', 'P131'] for q in targets(cache.entities[city], prop, current=True)}
                cache.ensure(related)
                for i in range(0, len(ids), 300):
                    write_gzip(SCOPE / f'batch-{i // 300:05}.json.gz', [row for q in ids[i:i + 300] for row in rows_for(q, cache.entities[q], cache.entities)])
                status(state='complete', cached=len(ids), batches=(len(ids) + 299) // 300)
                print('Eurasia download complete; world snapshot and public catalog unchanged.', flush=True)
                return
            except (Deferred, wdqs.DownloadDeferred) as error:
                deadlines = [json.loads(p.read_text()).get('retryAt', 0) for p in [ROOT / 'api-rate-limit.json', ROOT / 'rate-limit.json'] if p.exists()]
                deadline = max([time.time() + 65, *deadlines])
                status(state='waiting', retryAt=deadline, message=str(error))
                print(str(error), flush=True)
                time.sleep(max(0, deadline - time.time()))
            except Exception as error:
                status(state='failed', error=str(error))
                raise

if __name__ == '__main__': main()
