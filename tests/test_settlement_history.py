import sys, json, unittest, copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from settlement_history import apply_history, structured_evidence, event, OVERRIDE_PATH

def row(**values): return {k:{'value':str(v)} for k,v in values.items()}
def city(): return dict(wikidata='Q1', founded=None, dateKind='', dateLabel='', statusYear='', url='https://example.org', population=[dict(year=1900,value=100,source='https://example.org')])
class HistoryTests(unittest.TestCase):
 def test_unclassified_inception_is_not_foundation(self):
  c=city();c['historyEvents']=structured_evidence([row(inception='+1841-01-01',precision=9),row(inception='+1997-01-01',precision=9)],'Q1')
  apply_history(c,{})
  self.assertIsNone(c['settlement']);self.assertIsNone(c['cityStatus']);self.assertEqual(c['founded'],1900);self.assertIn('начало поселения неизвестно',c['dateLabel'])
 def test_century_precision_and_conflicts(self):
  c=city();c['population']=[];c['historyEvents']=structured_evidence([row(mention='+1800-01-01',mentionPrecision=7)],'Q1');apply_history(c,{})
  self.assertEqual(c['founded'],1800);self.assertEqual(c['settlement']['start'],1701);self.assertEqual(c['settlement']['precision'],'century')
  c=city();c['historyEvents']=structured_evidence([row(mention='+1700-01-01',mentionPrecision=9),row(mention='+1800-01-01',mentionPrecision=9)],'Q1');apply_history(c,{})
  self.assertIsNone(c['settlement']);self.assertEqual(c['founded'],1900)
 def test_overrides_survive_repeated_and_fresh_import(self):
  overrides=json.loads(OVERRIDE_PATH.read_text())['cities'];c=city();c['wikidata']='Q8646';pop=copy.deepcopy(c['population']);apply_history(c,overrides);first=copy.deepcopy(c);apply_history(c,overrides)
  self.assertEqual(c,first);self.assertEqual(c['population'],pop);self.assertEqual(c['settlement']['end'],1550)
  fresh=city();fresh['wikidata']='Q8646';apply_history(fresh,overrides);self.assertEqual(fresh,c)
 def test_review_cohort_sources_and_intervals(self):
  d=json.loads(OVERRIDE_PATH.read_text());self.assertEqual(len(d['cities']),51);self.assertEqual(set(d['cities']),set(d['selection']['qids']))
  ranked=sorted((q for q in d['cities'] if q!='Q8646'),key=lambda q:(-d['cities'][q]['population']['value'],q));self.assertEqual(d['selection']['qids'][1:],ranked)
  for c in d['cities'].values():
   self.assertTrue(c['sources']);self.assertTrue(c['statusReview']);self.assertTrue(c['reviewNote'])
   for e in [c['settlement'],c['cityStatus']]+c['events']:
    if not e:continue
    self.assertTrue(e['source'].startswith('https://'));self.assertTrue(e['explanation']);self.assertTrue(e['start'] is None or e['start']<=e['end'])
