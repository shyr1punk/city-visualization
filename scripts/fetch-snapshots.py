"""Refresh the upstream snapshots. Existing pinned files allow a fully offline import."""
import urllib.request,urllib.parse,json,time
from pathlib import Path
base=Path('data/raw');base.mkdir(exist_ok=True)
def download(url,path):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'CityTimeAtlas/1.0'}),timeout=90) as r:path.write_bytes(r.read())
 print(path,flush=True)
for remote,local in [('raw-data.json','legacy-raw.json'),('fill_cities_coords.json','legacy-coords.json')]:download('https://raw.githubusercontent.com/shyr1punk/city-visualization/d3d1ed91a9f281d35a780ae9ab27a41fc93ba060/'+remote,base/local)
download('https://ru.wikipedia.org/wiki/'+urllib.parse.quote('Список_городов_России'),base/'wikipedia-cities.html')
queries={
'wikidata-population':'SELECT ?city ?cityLabel ?coord ?inception ?date ?population WHERE { ?city wdt:P31 wd:Q7930989; wdt:P625 ?coord. OPTIONAL {?city wdt:P571 ?inception.} OPTIONAL {?city p:P1082 ?s. ?s ps:P1082 ?population; pq:P585 ?date.} SERVICE wikibase:label {bd:serviceParam wikibase:language "ru".}}',
'wikidata-references':'SELECT ?city ?statement ?date ?population ?reference ?part WHERE { ?city wdt:P31 wd:Q7930989; p:P1082 ?statement. ?statement ps:P1082 ?population; pq:P585 ?date; wikibase:rank ?rank. FILTER(?rank != wikibase:DeprecatedRank) OPTIONAL {?statement prov:wasDerivedFrom/pr:P854 ?reference.} OPTIONAL {?statement pq:P518 ?part.}}',
'wikidata-sitelinks':'SELECT ?city ?article WHERE { ?city wdt:P31 wd:Q7930989. ?article schema:about ?city; schema:isPartOf <https://ru.wikipedia.org/>.}'
}
for name,q in queries.items():
 download('https://query.wikidata.org/sparql?'+urllib.parse.urlencode({'query':q,'format':'json'}),base/(name+'.json'));time.sleep(2)
# Exact article identities are resolved by fetch-identities.py after parsing the new catalog.
for remote,local in [('ne_50m_admin_0_countries','world'),('ne_50m_rivers_lake_centerlines','rivers')]:download('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/'+remote+'.geojson',Path('public')/(local+'.geojson'))
