"""Fetch already-discovered cities via Wikibase API, then prepare complete import rows."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from world_entities import EntityCache, Deferred, targets, rows_for, write_gzip

ROOT = Path('data/raw/world')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--known-only', action='store_true', help='Prefetch discovered IDs while WDQS census is incomplete')
    args = parser.parse_args()
    ids_path = ROOT / 'ids.json'
    if args.known_only and not ids_path.exists():
        ids = sorted({r['city']['value'].rsplit('/', 1)[-1] for p in ROOT.glob('ids-*.json') for r in json.loads(p.read_text())})
    else:
        ids = json.loads(ids_path.read_text())
    cache = EntityCache(ROOT)
    cache.ensure(ids)
    related_ids = {target for q in ids for prop in ['P17', 'P131'] for target in targets(cache.entities[q], prop, current=True)}
    cache.ensure(related_ids)
    if args.known_only:
        print(f'Prefetched {len(ids)} city entities; full census still incomplete.', flush=True)
        return
    batches = [ids[i:i + 300] for i in range(0, len(ids), 300)]
    manifest = {'complete': False, 'phase': 'normalize', 'snapshotDate': time.strftime('%Y-%m-%d'), 'cities': len(ids),
                'idsHash': hashlib.sha256(ids_path.read_bytes()).hexdigest(), 'batches': len(batches), 'batchPrefix': 'api-v1',
                'batchSuffix': '.json.gz', 'detailSource': 'https://www.wikidata.org/w/api.php?action=wbgetentities',
                'source': 'Wikidata classes Q515 and Q7930989 and their subclasses; no P576', 'entityCache': 'entities/*.json.gz'}
    for i, batch in enumerate(batches):
        rows = [row for q in batch for row in rows_for(q, cache.entities[q], cache.entities)]
        write_gzip(ROOT / f'api-v1-{i:05}.json.gz', rows)
    manifest.update(complete=True, phase='complete')
    path = ROOT / 'manifest.json'; temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':'))); temp.replace(path)
    print(f'Complete world snapshot: {len(ids)} cities, {len(batches)} import batches', flush=True)

if __name__ == '__main__':
    try: main()
    except Deferred as error:
        print(str(error) + '; cached progress retained.', file=sys.stderr)
        sys.exit(75)
