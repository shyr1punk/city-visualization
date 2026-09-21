"""Read-only Wikibase entity snapshots and lossless rows for the atlas importer.

WDQS discovers membership; wbgetentities supplies properties, without large SPARQL
joins. Both services have independent persisted Retry-After handling.
"""
import concurrent.futures
import gzip
import http.client
import hashlib
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

PROPERTIES = {'P17', 'P30', 'P31', 'P131', 'P571', 'P1249', 'P1082', 'P625', 'P1705', 'P576'}
ENTITY_URL = 'http://www.wikidata.org/entity/'
API = 'https://www.wikidata.org/w/api.php'


class Deferred(RuntimeError):
    pass


def read_gzip(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def write_gzip(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_bytes(gzip.compress(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode(), mtime=0))
    temp.replace(path)


def project(entity):
    labels = entity.get('labels', {})
    keep_labels = {k: v for k, v in labels.items() if k in {'ru', 'en', 'mul'}}
    if not keep_labels and labels:
        key = sorted(labels)[0]; keep_labels[key] = labels[key]
    return {**{k: entity[k] for k in ['id', 'lastrevid', 'modified', 'missing'] if k in entity},
            'labels': keep_labels, 'claims': {k: v for k, v in entity.get('claims', {}).items() if k in PROPERTIES},
            'sitelinks': {'ruwiki': entity['sitelinks']['ruwiki']} if 'ruwiki' in entity.get('sitelinks', {}) else {}}


def statements(entity, prop, current=False, truthy=False):
    claims = [c for c in entity.get('claims', {}).get(prop, []) if c.get('rank') != 'deprecated' and c.get('mainsnak', {}).get('snaktype') == 'value']
    if current:
        claims = [c for c in claims if 'P582' not in c.get('qualifiers', {})]
    if truthy and any(c.get('rank') == 'preferred' for c in claims):
        claims = [c for c in claims if c.get('rank') == 'preferred']
    return claims


def snak_value(snak):
    return snak.get('datavalue', {}).get('value')


def targets(entity, prop, current=False):
    return sorted({value['id'] for c in statements(entity, prop, current=current, truthy=True)
                   if isinstance(value := snak_value(c['mainsnak']), dict) and 'id' in value})


def label(entity, fallback):
    labels = entity.get('labels', {})
    for language in ['ru', 'en', 'mul']:
        if language in labels: return labels[language]['value']
    native = [snak_value(c['mainsnak']) for c in statements(entity, 'P1705', truthy=True)]
    for n in native:
        if isinstance(n, dict) and n.get('text'): return n['text']
    return next((v['value'] for _, v in sorted(labels.items())), fallback)


def rows_for(qid, entity, related):
    base = {'city': {'value': ENTITY_URL + qid}, 'cityLabel': {'value': label(entity, qid)}}
    rows = [base]
    def add(**fields):
        rows.append({'city': base['city'], **{k: {'value': str(v)} for k, v in fields.items()}})
    for c in statements(entity, 'P625', truthy=True):
        p = snak_value(c['mainsnak'])
        if isinstance(p, dict) and p.get('globe', ENTITY_URL + 'Q2') == ENTITY_URL + 'Q2':
            add(coord=f"Point({p['longitude']} {p['latitude']})")
    for continent in targets(entity, 'P30'): add(continent=ENTITY_URL + continent)
    for prop, field in [('P17', 'country'), ('P131', 'admin')]:
        for target in targets(entity, prop, current=True):
            other = related.get(target, {})
            add(**{field: ENTITY_URL + target, field + 'Label': label(other, target)})
            for continent in targets(other, 'P30'):
                add(**{field + 'Continent': ENTITY_URL + continent})
    for prop, field, precision in [('P571', 'inception', 'precision'), ('P1249', 'mention', 'mentionPrecision')]:
        for c in statements(entity, prop):
            d = snak_value(c['mainsnak'])
            if isinstance(d, dict) and 'time' in d: add(**{field: d['time'], precision: d['precision']})
    for c in statements(entity, 'P1082'):
        qualifiers = c.get('qualifiers', {})
        if 'P518' in qualifiers: continue
        amount = snak_value(c['mainsnak'])
        if not isinstance(amount, dict): continue
        sources = sorted({url for ref in c.get('references', []) for snak in ref.get('snaks', {}).get('P854', [])
                          if isinstance(url := snak_value(snak), str) and url.startswith(('http://', 'https://'))})
        source = sources[0] if sources else f'https://www.wikidata.org/wiki/{qid}#P1082'
        for snak in qualifiers.get('P585', []):
            date = snak_value(snak)
            if isinstance(date, dict) and 'time' in date and date.get('precision', 0) >= 9:
                add(population=amount['amount'], date=date['time'], statement=c.get('id', ''), reference=source)
    article = entity.get('sitelinks', {}).get('ruwiki', {}).get('url')
    if article: add(article=article)
    return rows


class EntityCache:
    def __init__(self, root):
        self.root = root
        self.directory = root / 'entities'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.entities = {}
        for path in sorted(self.directory.glob('*.json.gz')):
            self.entities.update(read_gzip(path))
        self.lock = threading.Lock()
        self.next_request = 0.0
        self.blocked = False

    def request(self, qids):
        url = API + '?' + urllib.parse.urlencode({'action': 'wbgetentities', 'ids': '|'.join(qids),
             'props': 'labels|claims|sitelinks/urls|info', 'sitefilter': 'ruwiki', 'format': 'json', 'maxlag': 5})
        for attempt in range(5):
            with self.lock:
                if self.blocked: raise Deferred('Wikibase API temporarily deferred requests')
                rate_path = self.root / 'api-rate-limit.json'
                if rate_path.exists():
                    until = json.loads(rate_path.read_text())['retryAt']
                    if until > time.time(): raise Deferred(f'API resumes after {datetime.fromtimestamp(until, timezone.utc).isoformat()}')
                time.sleep(max(0, self.next_request - time.monotonic()))
                self.next_request = time.monotonic() + 6.5
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'CityTimeAtlas/3.0 (open historical city atlas)', 'Accept-Encoding': 'gzip'})
                with urllib.request.urlopen(request, timeout=90) as response:
                    raw = response.read()
                    if response.headers.get('Content-Encoding') == 'gzip': raw = gzip.decompress(raw)
                    result = json.loads(raw)
                if 'error' in result:
                    with self.lock:
                        self.blocked = True
                        (self.root / 'api-rate-limit.json').write_text(json.dumps({'retryAt': time.time() + 65, 'error': result['error']}))
                    raise Deferred('Wikibase API: ' + result['error'].get('code', 'unknown error'))
                entities = result['entities']
                # Redirect targets may add extra entities to an otherwise complete response.
                if not set(qids).issubset(entities):
                    write_gzip(self.root / 'incomplete-response.json.gz', {'requested': qids, 'response': result})
                    raise ValueError('Entity response incomplete: ' + ', '.join(sorted(set(qids) - set(entities))))
                if any('missing' in e for e in entities.values()): raise ValueError('A city entity was deleted; census must be reconciled')
                return {q: project(entities[q]) for q in qids}
            except urllib.error.HTTPError as error:
                raw_delay = error.headers.get('Retry-After', '60')
                try: delay = float(raw_delay)
                except ValueError: delay = max(60, parsedate_to_datetime(raw_delay).timestamp() - time.time())
                (self.root / 'api-last-error.json').write_text(json.dumps({'status': error.code, 'message': str(error), 'retryAfter': delay, 'time': time.time()}))
                if error.code == 429 or delay > 60:
                    with self.lock:
                        self.blocked = True
                        (self.root / 'api-rate-limit.json').write_text(json.dumps({'retryAt': time.time() + max(60, delay), 'status': error.code}))
                    raise Deferred(str(error)) from error
                if attempt == 4: raise
                time.sleep(min(60, 5 * 2 ** attempt))
            except (urllib.error.URLError, TimeoutError, http.client.HTTPException, ConnectionError) as error:
                if attempt == 4:
                    with self.lock:
                        self.blocked = True
                        (self.root / 'api-rate-limit.json').write_text(json.dumps({'retryAt': time.time() + 120, 'error': str(error)}))
                    raise Deferred('Temporary network failure: ' + str(error)) from error
                time.sleep(min(60, 5 * 2 ** attempt))

    def ensure(self, ids):
        missing = sorted(set(ids) - self.entities.keys(), key=lambda q: int(q[1:]))
        batches = [missing[i:i + 50] for i in range(0, len(missing), 50)]
        completed = 0
        def fetch_batch(qids):
            result = self.request(qids)
            digest = hashlib.sha256('|'.join(qids).encode()).hexdigest()[:16]
            write_gzip(self.directory / (digest + '.json.gz'), result)
            return result
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for result in pool.map(fetch_batch, batches):
                self.entities.update(result)
                completed += len(result)
                if completed % 500 == 0 or completed == len(missing):
                    print(f'Entities: {completed}/{len(missing)} downloaded; cache {len(self.entities)}', flush=True)
        return self.entities
