"""Extract sourced population tables from the 14 reviewed city article snapshots."""
import json,re
from pathlib import Path
from bs4 import BeautifulSoup
catalog=json.loads(Path('data/catalog.json').read_text());extra={}
for p in Path('data/raw/stories').glob('*.html'):
 s=BeautifulSoup(p.read_text(),'html.parser');city=next(c for c in catalog if c['name']==p.stem);obs={}
 for table in s.select('table'):
  caption=table.find('caption')
  # Only the dedicated population table, never density or municipal tables.
  if not caption or caption.get_text(' ',strip=True)!='Численность населения':continue
  trs=table.select('tr');pending=[]
  for tr in trs:
   for sup in tr.select('sup'):sup.decompose()
   cells=tr.find_all(['th','td'],recursive=False)
   values=[c.get_text(' ',strip=True) for c in cells]
   if values and all(re.fullmatch(r'\d{4}',x) for x in values):pending=list(map(int,values));continue
   if pending and len(values)==len(pending):
    for year,txt in zip(pending,values):
     num=re.sub(r'[\s↗↘→]','',txt)
     if num.isdigit() and year<=2026:obs[year]={'year':year,'value':int(num),'source':city['url']+'#Население','date':str(year),'statement':'wikipedia-table'}
    pending=[]
 extra[city['id']]=list(obs.values())
Path('data/story-observations.json').write_text(json.dumps(extra,ensure_ascii=False,indent=2));print('Story observations:',sum(map(len,extra.values())))
