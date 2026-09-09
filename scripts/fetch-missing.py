import json,urllib.request,urllib.parse
from pathlib import Path
c=json.loads(Path('data/catalog-base.json').read_text());rows=json.loads(Path('data/raw/wikidata-population.json').read_text())['results']['bindings']; names=set(x['cityLabel']['value'] for x in rows)
missing=[x['name'] for x in c if x['name'] not in names]
values=' '.join(json.dumps(n,ensure_ascii=False)+'@ru' for n in missing)
query='''SELECT ?city ?cityLabel ?coord ?inception ?statement ?date ?population ?reference ?part WHERE { VALUES ?cityLabel {'''+values+'''} ?city rdfs:label ?cityLabel; wdt:P625 ?coord. OPTIONAL {?city wdt:P571 ?inception.} OPTIONAL {?city p:P1082 ?statement. ?statement ps:P1082 ?population; pq:P585 ?date; wikibase:rank ?rank. FILTER(?rank != wikibase:DeprecatedRank) OPTIONAL {?statement prov:wasDerivedFrom/pr:P854 ?reference.} OPTIONAL {?statement pq:P518 ?part.}}}'''
Path('data/raw/missing-query.sparql').write_text(query)
req=urllib.request.Request('https://query.wikidata.org/sparql?'+urllib.parse.urlencode({'query':query,'format':'json'}),headers={'User-Agent':'CityTimeAtlas/1.0 (open data visualization)'})
with urllib.request.urlopen(req,timeout=90) as r:Path('data/raw/wikidata-missing.json').write_bytes(r.read())
print('Downloaded missing cities')
