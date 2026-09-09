"""Resolve every catalog entry through its exact Wikipedia article, never a name alone."""
import json,urllib.request,urllib.parse,concurrent.futures,time
from pathlib import Path
known=json.loads(Path('data/raw/identities.json').read_text())
cities=[c for c in json.loads(Path('data/catalog-base.json').read_text()) if not known.get(c['id'])];titles=[urllib.parse.unquote(c['url'].split('/wiki/')[-1]).replace('_',' ') for c in cities]
def fetch(offset):
 batch=titles[offset:offset+15];query=urllib.parse.urlencode({'action':'query','prop':'pageprops','ppprop':'wikibase_item','titles':'|'.join(batch),'redirects':1,'format':'json'})
 for retry in range(3):
  try:
   with urllib.request.urlopen(urllib.request.Request('https://ru.wikipedia.org/w/api.php?'+query,headers={'User-Agent':'CityTimeAtlas/1.0'}),timeout=35) as r:data=json.load(r)
   mapping={p['title']:p.get('pageprops',{}).get('wikibase_item') for p in data['query']['pages'].values()};aliases={p['from']:p['to'] for p in data['query'].get('redirects',[])+data['query'].get('normalized',[])}
   return {cities[offset+i]['id']:mapping.get(aliases.get(t,t)) for i,t in enumerate(batch)}
  except Exception:
   if retry==2:raise
   time.sleep(5*(retry+1))
result={k:v for k,v in known.items() if v}
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
 for r in pool.map(fetch,range(0,len(titles),15)):
  result.update(r);Path('data/raw/identities.json').write_text(json.dumps(result,indent=2));print('Resolved batch',len(result),flush=True);time.sleep(1)
Path('data/raw/identities.json').write_text(json.dumps(result,indent=2));print('Resolved',sum(bool(v) for v in result.values()),'of',len(result))
rows=json.loads(Path('data/raw/wikidata-population.json').read_text())['results']['bindings']+json.loads(Path('data/raw/wikidata-missing.json').read_text())['results']['bindings'];existing={r['city']['value'].split('/')[-1] for r in rows};missing=sorted(set(result.values())-existing-{None})
query='''SELECT ?city ?cityLabel ?coord ?inception ?statement ?date ?population ?reference ?part WHERE { VALUES ?city {'''+ ' '.join('wd:'+qid for qid in missing)+'''} OPTIONAL {?city wdt:P625 ?coord.} OPTIONAL {?city wdt:P571 ?inception.} OPTIONAL {?city p:P1082 ?statement. ?statement ps:P1082 ?population; pq:P585 ?date; wikibase:rank ?rank. FILTER(?rank != wikibase:DeprecatedRank) OPTIONAL {?statement prov:wasDerivedFrom/pr:P854 ?reference.} OPTIONAL {?statement pq:P518 ?part.}} SERVICE wikibase:label {bd:serviceParam wikibase:language "ru".}}'''
Path('data/raw/exact-query.sparql').write_text(query)
url='https://query.wikidata.org/sparql?'+urllib.parse.urlencode({'query':query,'format':'json'})
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'CityTimeAtlas/1.0'}),timeout=90) as r:Path('data/raw/wikidata-exact.json').write_bytes(r.read())
print('Fetched',len(missing),'additional exact identities')
