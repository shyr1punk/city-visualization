"""Resumable Wikidata snapshot. No public files are changed by downloading."""
import argparse
import concurrent.futures
import hashlib
import sys
import threading
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path('data/raw/world')
ENDPOINT = 'https://query.wikidata.org/sparql'
IDS_QUERY = '''SELECT DISTINCT ?city WHERE {
 hint:Query hint:optimizer "None".
 VALUES ?root { wd:Q515 wd:Q7930989 }
 ?class wdt:P279* ?root.
 ?city wdt:P31 ?class.
 FILTER NOT EXISTS { ?city wdt:P576 ?d. }
}'''
QUERY = '''SELECT ?city ?cityLabel ?nativeLabel ?fallbackLabel ?country ?countryLabel ?continent ?admin ?adminLabel
 ?adminContinent ?countryContinent ?coord ?inception ?precision ?mention ?mentionPrecision
 ?population ?date ?statement ?reference ?article WHERE {
 VALUES ?city { IDS }
 OPTIONAL { ?city wdt:P625 ?coord. }
 OPTIONAL { ?city wdt:P1705 ?nativeLabel. }
 OPTIONAL { FILTER NOT EXISTS { ?city rdfs:label ?knownLabel. FILTER(LANG(?knownLabel) IN ("ru", "en")) } ?city rdfs:label ?fallbackLabel. }
 OPTIONAL { ?city p:P17 ?countryStatement. ?countryStatement ps:P17 ?country. FILTER NOT EXISTS { ?countryStatement pq:P582 ?countryEnd. } FILTER NOT EXISTS { ?countryStatement wikibase:rank wikibase:DeprecatedRank. } OPTIONAL { ?country wdt:P30 ?countryContinent. } }
 OPTIONAL { ?city wdt:P30 ?continent. }
 OPTIONAL { ?city p:P131 ?adminStatement. ?adminStatement ps:P131 ?admin. FILTER NOT EXISTS { ?adminStatement pq:P582 ?adminEnd. } FILTER NOT EXISTS { ?adminStatement wikibase:rank wikibase:DeprecatedRank. } OPTIONAL { ?admin wdt:P30 ?adminContinent. } }
 OPTIONAL { ?city p:P571 ?s. ?s psv:P571 ?node. FILTER NOT EXISTS { ?s wikibase:rank wikibase:DeprecatedRank. } ?node wikibase:timeValue ?inception; wikibase:timePrecision ?precision. }
 OPTIONAL { ?city p:P1249 ?ms. ?ms psv:P1249 ?mn. FILTER NOT EXISTS { ?ms wikibase:rank wikibase:DeprecatedRank. } ?mn wikibase:timeValue ?mention; wikibase:timePrecision ?mentionPrecision. }
 OPTIONAL { ?city p:P1082 ?statement. ?statement ps:P1082 ?population; pq:P585 ?date.
 FILTER NOT EXISTS { ?statement wikibase:rank wikibase:DeprecatedRank. }
 FILTER NOT EXISTS { ?statement pq:P518 ?part. }
 OPTIONAL { ?statement prov:wasDerivedFrom/pr:P854 ?reference. } }
 OPTIONAL { ?article schema:about ?city; schema:isPartOf <https://ru.wikipedia.org/>. }
 SERVICE wikibase:label { bd:serviceParam wikibase:language "ru,en". }
}'''

def save(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    temp.replace(path)


class DownloadDeferred(RuntimeError):
    pass


REQUEST_LOCK = threading.Lock()
NEXT_REQUEST = 0.0


def retry_seconds(raw):
    try:
        return max(0, float(raw))
    except (ValueError, TypeError):
        try:
            return max(0, parsedate_to_datetime(raw).timestamp() - time.time())
        except (ValueError, TypeError):
            return 0


def fetch(query):
    global NEXT_REQUEST
    url = ENDPOINT + '?' + urllib.parse.urlencode({'query': query, 'format': 'json'})
    for attempt in range(7):
        with REQUEST_LOCK:
            rate_path = ROOT / 'rate-limit.json'
            if rate_path.exists():
                deadline = json.loads(rate_path.read_text())['retryAt']
                if deadline > time.time():
                    raise DownloadDeferred('Resume after ' + datetime.fromtimestamp(deadline, timezone.utc).isoformat())
            delay = max(0, NEXT_REQUEST - time.monotonic())
            if delay:
                time.sleep(delay)
            started = time.monotonic()
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'CityTimeAtlas/3.0 (open historical city atlas)', 'Accept': 'application/sparql-results+json'})
                with urllib.request.urlopen(request, timeout=100) as response:
                    result = json.load(response)['results']['bindings']
                # Leave processing capacity for other WDQS clients; never flood retries.
                NEXT_REQUEST = time.monotonic() + max(65, 2 * (time.monotonic() - started))
                return result
            except (urllib.error.URLError, TimeoutError, ValueError) as error:
                status = error.code if isinstance(error, urllib.error.HTTPError) else None
                retry_after = retry_seconds(error.headers.get('Retry-After')) if status else 0
                save(ROOT / 'last-error.json', {'status': status, 'time': time.time(), 'queryHash': hashlib.sha256(query.encode()).hexdigest(), 'message': str(error)})
                if status == 429 or retry_after > 60:
                    deadline = time.time() + max(60, retry_after)
                    save(rate_path, {'retryAt': deadline, 'status': status})
                    raise DownloadDeferred('Source deferred requests until ' + datetime.fromtimestamp(deadline, timezone.utc).isoformat()) from error
                if attempt == 6:
                    raise
                NEXT_REQUEST = time.monotonic() + max(65, 5 * 2 ** attempt)
                print(f'Retrying HTTP {status or "network error"}', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ids-file', type=Path)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--ids-only', action='store_true')
    parser.add_argument('--global-ids', action='store_true')
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / 'manifest.json'
    if not manifest_path.exists():
        save(manifest_path, {'complete': False, 'phase': 'city-ids', 'snapshotDate': time.strftime('%Y-%m-%d')})
    ids_path = ROOT / 'ids.json'
    if not ids_path.exists():
        if args.global_ids:
            rows = fetch(IDS_QUERY)
        elif args.ids_file:
            rows = json.loads(args.ids_file.read_text())['results']['bindings']
        else:
            class_path = ROOT / 'classes.json'
            if not class_path.exists():
                save(class_path, fetch('SELECT DISTINCT ?class WHERE { VALUES ?root { wd:Q515 wd:Q7930989 } ?class wdt:P279* ?root. }'))
            classes = sorted({r['class']['value'].rsplit('/', 1)[-1] for r in json.loads(class_path.read_text())})
            rows = []
            for offset in range(0, len(classes), 30):
                part = ROOT / f'ids-{offset:05}.json'
                if not part.exists():
                    values = ' '.join('wd:' + c for c in classes[offset:offset + 30])
                    save(part, fetch('SELECT DISTINCT ?city WHERE { VALUES ?class { ' + values + ' } ?city wdt:P31 ?class. FILTER NOT EXISTS { ?city wdt:P576 ?d. } }'))
                rows.extend(json.loads(part.read_text()))
                count = min(offset + 30, len(classes))
                save(manifest_path, {'complete': False, 'phase': 'city-ids', 'snapshotDate': time.strftime('%Y-%m-%d'), 'classes': len(classes), 'completedClasses': count, 'discoveredCityIds': len({r['city']['value'] for r in rows})})
                print(f'City IDs: classes {count}/{len(classes)}', flush=True)
        ids = sorted({r['city']['value'].rsplit('/', 1)[-1] for r in rows}, key=lambda s: int(s[1:]))
        if not ids:
            raise ValueError('Empty city census')
        save(ids_path, ids)
    ids = json.loads(ids_path.read_text())
    if args.ids_only:
        save(manifest_path, {'complete': False, 'phase': 'details', 'snapshotDate': time.strftime('%Y-%m-%d'), 'cities': len(ids), 'query': IDS_QUERY, 'idsHash': hashlib.sha256(ids_path.read_bytes()).hexdigest()})
        print(f'Complete city ID census: {len(ids)} cities', flush=True)
        return
    batches = [ids[i:i + 150] for i in range(0, len(ids), 150)]
    manifest = {'snapshotDate': time.strftime('%Y-%m-%d'), 'query': IDS_QUERY, 'detailQuery': QUERY, 'idsHash': hashlib.sha256(ids_path.read_bytes()).hexdigest(), 'cities': len(ids), 'batches': len(batches), 'batchPrefix': 'batch-' + hashlib.sha256(QUERY.encode()).hexdigest()[:12], 'complete': False}
    save(ROOT / 'manifest.json', manifest)
    def batch(item):
        i, qids = item
        path = ROOT / f"{manifest['batchPrefix']}-{i:05}.json"
        if path.exists():
            result = json.loads(path.read_text())
            if {r['city']['value'].rsplit('/', 1)[-1] for r in result} == set(qids):
                return
        rows = fetch(QUERY.replace('IDS', ' '.join('wd:' + q for q in qids)))
        present = {r['city']['value'].rsplit('/', 1)[-1] for r in rows}
        if present != set(qids):
            raise ValueError(f'Incomplete batch {i}: {len(present)}/{len(qids)}')
        save(path, rows)
        print(f'Batch {i + 1}/{len(batches)} ({len(rows)} rows)', flush=True)
        time.sleep(1)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(batch, enumerate(batches)))
    manifest['complete'] = True
    save(ROOT / 'manifest.json', manifest)
    print(f'Complete: {len(ids)} cities', flush=True)

if __name__ == '__main__':
    try:
        main()
    except DownloadDeferred as error:
        print(str(error) + '; progress saved, public catalog unchanged.', file=sys.stderr)
        sys.exit(75)
