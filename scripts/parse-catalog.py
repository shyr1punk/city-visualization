"""Parse the pinned Wikipedia HTML snapshot; keep uncertain dates explicit."""
import json,re,hashlib
from bs4 import BeautifulSoup
from pathlib import Path
s=BeautifulSoup(Path('data/raw/wikipedia-cities.html').read_text(),'html.parser')
legacy=json.loads(Path('data/raw/legacy-coords.json').read_text())
rows=[]
for table in s.select('table.standard.sortable'):
 for tr in table.select('tr')[1:]:
  t=tr.find_all('td',recursive=False)
  if len(t)!=9: continue
  for sup in tr.select('sup'):sup.decompose()
  a_tag=t[2].select_one('a[rel="mw:WikiLink"]') or t[2].select_one('a')
  if not a_tag:continue
  name=a_tag.get_text(' ',strip=True);region=t[3].get_text(' ',strip=True)
  match=[a for a in legacy if a[1]==name]
  if len(match)>1:match=[a for a in match if a[2]==region]
  a=match[0] if len(match)==1 else None
  date=t[6].get_text(' ',strip=True)
  year=int(date) if re.fullmatch(r'-?\d{1,4}',date) else None
  bc=re.search(r'(\d+)\s+год\s+до\s+н',date)
  if bc:year=-int(bc.group(1))
  link=a_tag['href']
  rows.append(dict(id='city-'+hashlib.sha1(link.encode()).hexdigest()[:10],name=name,region=region,country='Россия',coordinates=[a[7],a[6]] if a and len(a)>7 and isinstance(a[7],(int,float)) and isinstance(a[6],(int,float)) else None,founded=year,dateLabel=date,dateKind='foundation-or-mention',dateSource='https://ru.wikipedia.org/wiki/Список_городов_России',statusYear=t[7].get_text(' ',strip=True),formerNames=t[8].get_text(' ',strip=True),url=link,population=[],notes=[]))
Path('data/catalog-base.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
print('Catalog:',len(rows),'with coordinates:',sum(bool(r['coordinates']) for r in rows),'dates:',sum(r['founded'] is not None for r in rows))
