"""Reproducible offline import. Run parse-catalog.py first; raw snapshots are authoritative."""
import json,re,collections,math,gzip,unicodedata
from pathlib import Path
R=Path('data/raw')
def read(name):
 p=R/(name+'.json')
 return json.loads(p.read_text() if p.exists() else gzip.decompress((R/(name+'.json.gz')).read_bytes()))['results']['bindings']
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.casefold().replace('ё','е')) if not unicodedata.combining(c))
def v(r,k):return r.get(k,{}).get('value','')
def point(s):
 n=re.findall(r'-?\d+(?:\.\d+)?',s)
 return list(map(float,n)) if len(n)==2 else None
precise_dates=collections.defaultdict(set)
for d in read('wikidata-dates'):
 if int(v(d,'precision'))>=9 and re.match(r'^\d{4}-',v(d,'date')):precise_dates[v(d,'city')].add(int(v(d,'date')[:4]))
rows=read('wikidata-population');missing=read('wikidata-missing') if (R/'wikidata-missing.json').exists() or (R/'wikidata-missing.json.gz').exists() else []
exact=read('wikidata-exact')
missing+=exact
refs=read('wikidata-references')+missing
entities=collections.defaultdict(list)
for r in rows+missing:entities[v(r,'city')].append(r)
byname=collections.defaultdict(list)
for key,rs in entities.items():byname[norm(v(rs[0],'cityLabel'))].append(key)
byqid=collections.defaultdict(list)
for r in refs:byqid[v(r,'city')].append(r)
extras=json.loads(Path('data/story-observations.json').read_text()) if Path('data/story-observations.json').exists() else {}
identities=json.loads(Path('data/raw/identities.json').read_text())
catalog=json.loads(Path('data/catalog-base.json').read_text());report={'conflictingObservations':[],'unmatched':[],'coordinateCorrections':[],'dateCorrections':[],'excludedObservations':0}
boundaries={'Москва':[1939,1960,1984,2012],'Норильск':[2005],'Балашиха':[2015],'Подольск':[2015],'Сочи':[1961],'Новосибирск':[1960]}
for c in catalog:
 if c.get('wikidata') and c['id'] not in identities:continue
 qid=identities.get(c['id']);candidates=['http://www.wikidata.org/entity/'+qid] if qid and 'http://www.wikidata.org/entity/'+qid in entities else []
 if not candidates:report['unmatched'].append(c['name']);continue
 key=candidates[0]; rs=entities[key]; qid=key.split('/')[-1];c['wikidata']=qid
 coords=point(v(rs[0],'coord'))
 if coords:
  if c['coordinates'] and math.dist(coords,c['coordinates'])>.2:report['coordinateCorrections'].append(c['name'])
  c['coordinates']=coords;c['coordinateSource']='https://www.wikidata.org/wiki/'+qid+'#P625'
 dates=sorted(precise_dates[key])
 if c['founded'] is None and len(dates)==1:
  c['founded']=dates[0];c['dateKind']='inception';c['dateSource']='https://www.wikidata.org/wiki/'+qid+'#P571';c['notes'].append('Дата начала существования из Wikidata; формулировка справочника: '+c['dateLabel'])
 if c['founded'] and len(dates)==1 and dates[0]!=c['founded']:c['notes'].append('Wikidata указывает другую дату начала существования: '+str(dates[0])+'. На карте принята дата справочника.');report['dateCorrections'].append(c['name'])
 years=collections.defaultdict(list)
 for r in byqid[key]:
  if not re.match(r'^\d{4}-',v(r,'date')) or not v(r,'population') or v(r,'part'):report['excludedObservations']+=1;continue
  y=int(v(r,'date')[:4]);value=float(v(r,'population'))
  if not 1<=y<=2026 or value<=0 or (c['founded'] is not None and y<c['founded']):report['excludedObservations']+=1;continue
  source=v(r,'reference');source=source if source.startswith(('http://','https://')) else 'https://www.wikidata.org/wiki/'+qid+'#P1082'
  years[y].append({'year':y,'value':round(value),'source':source,'statement':v(r,'statement').split('/')[-1],'date':v(r,'date')[:10]})
 for observation in extras.get(c['id'],[]):
  if observation['year'] not in years:years[observation['year']].append(observation)
 population=[]
 for y,entries in sorted(years.items()):
  vals=set(e['value'] for e in entries)
  if len(vals)>1:
   census=[e for e in entries if e['date'] in ['2021-10-01','2010-10-14','2002-10-09']]
   if census and len(set(e['value'] for e in census))==1:entries=census
   else:report['conflictingObservations'].append({'city':c['name'],'year':y,'values':sorted(vals)});continue
  best=sorted(entries,key=lambda e:('wikidata.org'in e['source'],e['source']))[0]
  population.append(best)
 segment=0;previous=None;breaks=boundaries.get(c['name'],[])
 for p in population:
  boundary=previous and any(previous['year']<b<=p['year'] for b in breaks)
  sudden=previous and p['year']-previous['year']<=5 and abs(p['value']/previous['value']-1)>.35
  if boundary or sudden:
   segment+=1;p['breakBefore']=True
   c['notes'].append(f"{previous['year']}–{p['year']}: интерполяция отключена — "+('изменение административного охвата.' if boundary else 'резкий скачок ряда требует проверки сопоставимости.'))
  p['segment']=str(segment);previous=p
 c['population']=population
# First mention dates used in the narrated chapters; each comes from the linked city article.
for c in catalog:
 if c['name']=='Магнитогорск':c['notes'].append('1929 — начало строительства индустриального города; Магнитная крепость основана в 1743 году.')
 if c['name'] in ['Москва','Великий Новгород','Псков']:c['dateKind']='first-mention';c['dateSource']=c['url']
 elif c['name'] in ['Тобольск','Тюмень','Якутск','Санкт-Петербург','Новосибирск','Магнитогорск','Норильск','Обнинск']:c['dateKind']='foundation';c['dateSource']=c['url']
 if c['coordinates'] and not(-180<=c['coordinates'][0]<=180 and -90<=c['coordinates'][1]<=90):c['coordinates']=None
 if c['population'] and c['population'][-1]['year']>2026:raise ValueError(c['name'])
report.update({'snapshotDate':'2026-09-11','total':len(catalog),'withCoordinates':sum(c['coordinates'] is not None for c in catalog),'withDates':sum(c['founded'] is not None for c in catalog),'withPopulation':sum(bool(c['population']) for c in catalog),'observations':sum(len(c['population']) for c in catalog),'countryCounts':dict(sorted(collections.Counter(c.get('country','Россия') for c in catalog).items())),'missingDates':[c['name'] for c in catalog if c['founded'] is None],'missingCoordinates':[c['name'] for c in catalog if c['coordinates'] is None],'missingPopulation':[c['name'] for c in catalog if not c['population']]})
Path('data/catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,separators=(',',':')))
Path('public/catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,separators=(',',':')))
Path('public/coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print({k:report[k] for k in ['total','withCoordinates','withDates','withPopulation','observations']})
print('Missing coordinates',report['missingCoordinates']);print('Missing population',report['missingPopulation'])
