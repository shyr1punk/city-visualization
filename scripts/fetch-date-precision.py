import json,urllib.request,urllib.parse
from pathlib import Path
identities=json.load(open('data/raw/identities.json'));known={r['city']['value'].split('/')[-1] for r in json.load(open('data/raw/wikidata-population.json'))['results']['bindings']};extra=set(identities.values())-known-{None}
query='''SELECT ?city ?date ?precision WHERE { { ?city wdt:P31 wd:Q7930989. } UNION { VALUES ?city {'''+ ' '.join('wd:'+q for q in extra)+'''} } ?city p:P571 ?s. ?s ps:P571 ?date; psv:P571 ?node; wikibase:rank ?rank. ?node wikibase:timePrecision ?precision. FILTER(?rank != wikibase:DeprecatedRank) }'''
Path('data/raw/dates-query.sparql').write_text(query)
url='https://query.wikidata.org/sparql?'+urllib.parse.urlencode({'query':query,'format':'json'})
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'CityTimeAtlas/1.0'}),timeout=60) as r:Path('data/raw/wikidata-dates.json').write_bytes(r.read())
print('Dates and precision downloaded')
