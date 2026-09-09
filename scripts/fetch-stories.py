import json,urllib.request,concurrent.futures
from pathlib import Path
names=['Дербент','Великий Новгород','Псков','Москва','Казань','Тобольск','Тюмень','Якутск','Екатеринбург','Санкт-Петербург','Новосибирск','Магнитогорск','Норильск','Обнинск']
cs=[c for c in json.loads(Path('data/catalog.json').read_text()) if c['name'] in names]
def get(c):
 p=Path('data/raw/stories')/(c['name']+'.html');p.parent.mkdir(exist_ok=True)
 url=urllib.parse.quote(c['url'],safe=':/()%')
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'CityTimeAtlas/1.0'}),timeout=30) as r:p.write_bytes(r.read())
  return c['name']+' OK'
 except Exception as e:return c['name']+' '+str(e)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for s in pool.map(get,cs):print(s)
