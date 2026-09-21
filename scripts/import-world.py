"""Offline world importer. A complete snapshot is mandatory unless exporting legacy UI data."""
import argparse
import collections
import hashlib
import gzip
import json
import math
import re
from pathlib import Path

ROOT = Path('data/raw/world')
CONTINENTS = {'Q46', 'Q48', 'Q15', 'Q49', 'Q18', 'Q55643', 'Q51'}
ALIASES = {'Q538': 'Q55643', 'Q3960': 'Q55643', 'Q664609': 'Q49'}
OVERRIDES = json.loads((Path(__file__).resolve().parents[1] / 'data/continent-overrides.json').read_text())['cities']
NE_CONTINENTS = {'Europe': 'Q46', 'Asia': 'Q48', 'Africa': 'Q15', 'North America': 'Q49', 'South America': 'Q18', 'Oceania': 'Q55643', 'Antarctica': 'Q51'}
# Conservative region assignments: geographical ambiguity is retained as unknown.
REGION_CONTINENTS = {
    'Москва': 'Q46', 'Санкт-Петербург': 'Q46', 'Московская область': 'Q46',
    'Ленинградская область': 'Q46', 'Калининградская область': 'Q46', 'Татарстан': 'Q46',
    'Удмуртия': 'Q46',
    'Курганская область': 'Q48',
    'Тюменская область': 'Q48', 'Омская область': 'Q48', 'Новосибирская область': 'Q48',
    'Красноярский край': 'Q48', 'Иркутская область': 'Q48', 'Саха': 'Q48',
    'Приморский край': 'Q48', 'Хабаровский край': 'Q48', 'Магаданская область': 'Q48',
}


def read(path):
    return json.loads(gzip.decompress(path.read_bytes())) if path.suffix == '.gz' else json.loads(path.read_text())


def val(row, key):
    return row.get(key, {}).get('value', '')


def qid(value):
    return value.rsplit('/', 1)[-1]


def year(value):
    match = re.match(r'^([+-]?\d+)-', value)
    # Wikidata BCE conversion is not guessed: these records remain explicitly undated.
    if not match or int(match[1]) <= 0:
        return None
    return int(match[1])


def coords(value):
    match = re.fullmatch(r'Point\(([-+\d.eE]+) ([-+\d.eE]+)\)', value)
    if not match:
        return None
    lon, lat = map(float, match.groups())
    return [lon, lat] if math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90 else None


def continents(rows, city, country_meta):
    def extract(key):
        values = {ALIASES.get(qid(val(r, key)), qid(val(r, key))) for r in rows if val(r, key)}
        return sorted(values & CONTINENTS)
    direct = extract('continent') or extract('adminContinent')
    if direct:
        return direct
    override = OVERRIDES.get(city.get('wikidata'))
    if override: return override['continents']
    region = city.get('region', '')
    if region in REGION_CONTINENTS:
        return [REGION_CONTINENTS[region]]
    countries = set(city['countryIds'])
    point = city.get('coordinates')
    # Broad unambiguous portions only; do not place a boundary along an invented meridian.
    if countries & {'Q159', 'Q232', 'Q43', 'Q230', 'Q227', 'Q79', 'Q252'}:
        if point:
            lon, lat = point
            if 'Q159' in countries and 0 <= lon < 40: return ['Q46']
            if 'Q159' in countries and (lon > 70 or lon < -160): return ['Q48']
            if 'Q232' in countries and lon > 60: return ['Q48']
            if 'Q43' in countries and lon > 30: return ['Q48']
            if 'Q79' in countries and lon < 32: return ['Q15']
            if 'Q252' in countries and lon < 120: return ['Q48']
        return ['unknown']
    inherited = extract('countryContinent')
    if len(inherited) == 1:
        return inherited
    fallback = {country_meta[c]['continent'] for c in countries if c in country_meta and country_meta[c]['continent']}
    return sorted(fallback) if len(fallback) == 1 else ['unknown']


def convert(q, rows, country_meta, report):
    names = [val(r, 'cityLabel') for r in rows if val(r, 'cityLabel') and val(r, 'cityLabel') != q]
    countries = sorted({qid(val(r, 'country')) for r in rows if val(r, 'country')}) or ['unknown']
    for r in rows:
        if val(r, 'country'):
            key = qid(val(r, 'country'))
            country_meta.setdefault(key, {'name': val(r, 'countryLabel') or key, 'continent': None})
    native = next((val(r, 'nativeLabel') for r in rows if val(r, 'nativeLabel')), '') or next((val(r, 'fallbackLabel') for r in rows if val(r, 'fallbackLabel')), q)
    name = names[0] if names else native
    coordinate_values = [coords(val(r, 'coord')) for r in rows if val(r, 'coord')]
    coordinate_values = [p for p in coordinate_values if p is not None]
    c = {'id': 'city-' + hashlib.sha1(q.encode()).hexdigest()[:10], 'wikidata': q, 'name': name,
         'countryIds': countries, 'country': ' / '.join(country_meta[k]['name'] for k in countries),
         'region': next((val(r, 'adminLabel') for r in rows if val(r, 'adminLabel')), ''),
         'coordinates': coordinate_values[0] if coordinate_values else None,
         'coordinateSource': f'https://www.wikidata.org/wiki/{q}#P625',
         'founded': None, 'dateLabel': '', 'dateKind': '', 'statusYear': '', 'formerNames': '',
         'url': next((val(r, 'article') for r in rows if val(r, 'article')), f'https://www.wikidata.org/wiki/{q}'),
         'population': [], 'notes': []}
    c['continentIds'] = continents(rows, c, country_meta)
    for key, precision, kind, prop in [('inception', 'precision', 'inception', 'P571'), ('mention', 'mentionPrecision', 'first-mention', 'P1249')]:
        dates = {year(val(r, key)) for r in rows if val(r, precision).isdigit() and int(val(r, precision)) >= 9}
        dates.discard(None)
        if len(dates) == 1:
            c.update(founded=next(iter(dates)), dateKind=kind, dateSource=f'https://www.wikidata.org/wiki/{q}#{prop}')
            c['dateLabel'] = str(c['founded'])
            break
        if dates:
            c['notes'].append('Разночтения дат в Wikidata: ' + ', '.join(map(str, sorted(dates))))
    observed = collections.defaultdict(dict)
    for r in rows:
        y = year(val(r, 'date'))
        try: population = float(val(r, 'population'))
        except ValueError: continue
        if not y or y > 2026 or not math.isfinite(population) or population <= 0 or (c['founded'] and y < c['founded']): continue
        source = val(r, 'reference')
        if not source.startswith(('https://', 'http://')): source = f'https://www.wikidata.org/wiki/{q}#P1082'
        n = round(population)
        current = observed[y].get(n)
        if current is None or ('wikidata.org' in current and 'wikidata.org' not in source): observed[y][n] = source
    segment = 0
    for y, values in sorted(observed.items()):
        if len(values) != 1:
            report['worldConflictingObservations'].append({'qid': q, 'year': y, 'values': sorted(values)})
            continue
        n, source = next(iter(values.items()))
        prev = c['population'][-1] if c['population'] else None
        if prev and y - prev['year'] <= 5 and abs(n / prev['value'] - 1) > .35: segment += 1
        c['population'].append({'year': y, 'value': n, 'source': source, 'segment': str(segment)})
    if c['founded'] is None and c['population']:
        p = c['population'][0]
        c.update(founded=p['year'], dateKind='first-observation', dateSource=p['source'], dateLabel=f"не позднее {p['year']} года — первое наблюдение населения")
        c['notes'].append('Дата основания неизвестна; появление на карте привязано к первому датированному наблюдению населения.')
    if not c['region']: c['region'] = c['country']
    return c


def build(legacy_only=False):
    legacy_path = Path('data/legacy-catalog.json')
    if not legacy_path.exists():
        raise ValueError('Missing preserved legacy catalog')
    legacy = read(legacy_path)
    manifest = read(ROOT / 'manifest.json') if (ROOT / 'manifest.json').exists() else {'complete': False, 'snapshotDate': '2026-09-11', 'cities': 0}
    if legacy_only: manifest = {**manifest, 'complete': False}
    if not legacy_only:
        manifest = read(ROOT / 'manifest.json')
        if not manifest.get('complete'): raise ValueError('World snapshot is incomplete; public catalog unchanged')
        ids_path = ROOT / 'ids.json'
        if hashlib.sha256(ids_path.read_bytes()).hexdigest() != manifest['idsHash']: raise ValueError('City census hash mismatch')
    country_meta = {'unknown': {'name': 'Страна не определена', 'continent': None}}
    for f in read(Path('public/world.geojson'))['features']:
        p = f['properties']; q = p['WIKIDATAID']
        country_meta[q] = {'name': p.get('NAME_RU') or p['NAME_EN'], 'continent': NE_CONTINENTS.get(p['CONTINENT'])}
    name_to_id = {v['name']: k for k, v in country_meta.items()}
    name_to_id.update({'Беларусь': 'Q184', 'Молдова': 'Q217', 'Туркменистан': 'Q874', 'Кыргызстан': 'Q813'})
    for c in legacy:
        key = name_to_id.get(c['country'])
        if key: country_meta[key]['name'] = c['country']
    report = read(Path('public/coverage.json'))
    report['worldConflictingObservations'] = []
    report['worldSnapshot'] = manifest
    catalog = {}
    if not legacy_only:
        ids = set(read(ROOT / 'ids.json'))
        for i in range(manifest['batches']):
            grouped = collections.defaultdict(list)
            for r in read(ROOT / f"{manifest.get('batchPrefix', 'batch')}-{i:05}{manifest.get('batchSuffix', '.json')}"): grouped[qid(val(r, 'city'))].append(r)
            for q, rows in grouped.items():
                if q in catalog: raise ValueError('Duplicate QID across batches: ' + q)
                catalog[q] = convert(q, rows, country_meta, report)

        if set(catalog) != ids: raise ValueError('Snapshot city IDs are incomplete')
    for c in legacy:
        q = c.get('wikidata') or c['id']
        fresh = catalog.get(q)
        if fresh:
            c['countryIds'] = fresh['countryIds']; c['continentIds'] = fresh['continentIds']
        else:
            c['countryIds'] = [name_to_id.get(c['country'], 'unknown')]
            c['continentIds'] = continents([], c, country_meta)
        catalog[q] = c
    cities = sorted(catalog.values(), key=lambda c: (c['country'], c['name'], c['id']))
    if len({c['id'] for c in cities}) != len(cities): raise ValueError('Duplicate city ID')
    shards = collections.defaultdict(list)
    country_offsets = collections.Counter()
    index = []
    for c in cities:
        country = c['countryIds'][0]
        key = country + '-' + str(country_offsets[country] // 300).zfill(4)
        country_offsets[country] += 1
        c['detailKey'] = key
        shards[key].append(c)
        index.append({k: c[k] for k in ['id', 'wikidata', 'name', 'region', 'country', 'countryIds', 'continentIds', 'coordinates', 'founded', 'dateKind', 'url', 'detailKey'] if k in c})
    report.update(snapshotDate=manifest['snapshotDate'], total=len(cities), withCoordinates=sum(c['coordinates'] is not None for c in cities), withDates=sum(c['founded'] is not None for c in cities), withPopulation=sum(bool(c['population']) for c in cities), observations=sum(len(c['population']) for c in cities),
        countryCounts=dict(sorted(collections.Counter(c['country'] for c in cities).items())), continentCounts=dict(collections.Counter(x for c in cities for x in c['continentIds'])),
        missingDates=[c['name'] for c in cities if c['founded'] is None], missingCoordinates=[c['name'] for c in cities if c['coordinates'] is None], missingPopulation=[c['name'] for c in cities if not c['population']])
    outputs = {Path('public/catalog.json'): cities, Path('data/catalog.json'): cities, Path('public/coverage.json'): report,
        Path('public/catalog-index.json'): {'cities': index, 'countries': {k: country_meta[k]['name'] for k in sorted({q for c in cities for q in c['countryIds']})}, 'maxYear': max([2026] + [p['year'] for c in cities for p in c['population']]), 'snapshotComplete': manifest['complete']}}
    summary = {k: report[k] for k in ['snapshotDate', 'total', 'withCoordinates', 'withDates', 'withPopulation', 'observations']}
    summary.update(missingDates=len(report['missingDates']), missingCoordinates=len(report['missingCoordinates']), missingPopulation=len(report['missingPopulation']), worldComplete=manifest['complete'])
    outputs[Path('public/coverage-summary.json')] = summary
    outputs.update({Path(f'public/catalog/{k}.json'): values for k, values in shards.items()})
    # Serialize every output before replacing any working artifact.
    serialized = {p: json.dumps(v, ensure_ascii=False, separators=(',', ':')) for p, v in outputs.items()}
    for path in sorted(serialized, key=lambda p: p.name == 'catalog-index.json'):
        content = serialized[path]
        path.parent.mkdir(exist_ok=True, parents=True)
        temp = path.with_suffix('.tmp'); temp.write_text(content); temp.replace(path)
    print(json.dumps({k: report[k] for k in ['total', 'withDates', 'withPopulation', 'observations', 'continentCounts']}, ensure_ascii=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--legacy-only', action='store_true')
    build(parser.parse_args().legacy_only)
