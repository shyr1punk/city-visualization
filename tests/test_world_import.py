import importlib.util
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

spec = importlib.util.spec_from_file_location('world', Path(__file__).resolve().parents[1] / 'scripts/import-world.py')
world = importlib.util.module_from_spec(spec)
spec.loader.exec_module(world)
def row(**values): return {k: {'value': str(v)} for k, v in values.items()}

class WorldImportTests(unittest.TestCase):
    def convert(self, rows):
        report = {'worldConflictingObservations': []}
        return world.convert('Q123', rows, {'unknown': {'name': 'Страна не определена', 'continent': None}}, report), report

    def test_explicit_cache_import_preserves_existing_records_and_reports_gaps(self):
        import hashlib
        import types
        old = self.convert([row(cityLabel='Existing')])[0]
        fake_cache = types.SimpleNamespace(entities={'Q10': {}})
        fake_module = types.SimpleNamespace(EntityCache=lambda root: fake_cache,
            rows_for=lambda q, entity, related: [row(city='http://www.wikidata.org/entity/' + q, cityLabel='New')])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def save(path, value):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(value))
            save('data/raw/world/ids.json', ['Q10', 'Q20'])
            save('data/raw/world/manifest.json', {'complete': False, 'snapshotDate': '2026-09-12', 'idsHash': hashlib.sha256((root / 'data/raw/world/ids.json').read_bytes()).hexdigest()})
            save('data/legacy-catalog.json', [])
            save('public/catalog.json', [old])
            save('public/world.geojson', {'features': []})
            save('public/coverage.json', {})
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict('sys.modules', {'world_entities': fake_module}):
                    world.build(cached=True)
                result = json.loads(Path('public/catalog-index.json').read_text())
                self.assertEqual({c['wikidata'] for c in result['cities']}, {'Q123', 'Q10'})
                self.assertFalse(result['snapshotComplete'])
                report = json.loads(Path('public/coverage.json').read_text())
                self.assertEqual(report['worldSnapshot']['missingCities'], 1)
            finally:
                os.chdir(previous)

    def test_missing_fields_do_not_drop_city(self):
        c, _ = self.convert([row(cityLabel='No date')])
        self.assertIsNone(c['founded']); self.assertIsNone(c['coordinates']); self.assertEqual(c['population'], [])

    def test_conflicting_population_is_not_arbitrarily_selected(self):
        c, report = self.convert([row(date='2000-01-01', population=20), row(date='2000-01-01', population=30)])
        self.assertEqual(c['population'], []); self.assertEqual(len(report['worldConflictingObservations']), 1)

    def test_population_date_fallback_is_explicit(self):
        c, _ = self.convert([row(cityLabel='Test', date='2000-01-01', population=20)])
        self.assertEqual(c['dateKind'], 'first-observation'); self.assertEqual(c['founded'], 2000)

    def test_no_population_required_for_confirmed_date(self):
        c, _ = self.convert([row(inception='1800-01-01', precision=9)])
        self.assertEqual(c['founded'], 1800); self.assertEqual(c['population'], [])

    def test_imprecise_and_bce_dates_are_not_invented(self):
        for r in [row(inception='1800-01-01', precision=7), row(inception='-0500-01-01', precision=9)]:
            c, _ = self.convert([r]); self.assertIsNone(c['founded'])

    def test_multiple_countries_remain_one_record(self):
        c, _ = self.convert([row(country='http://www.wikidata.org/entity/Q1', countryLabel='A'), row(country='http://www.wikidata.org/entity/Q2', countryLabel='B')])
        self.assertEqual(c['countryIds'], ['Q1', 'Q2'])

    def test_direct_continent_beats_transcontinental_country(self):
        c, _ = self.convert([row(country='http://www.wikidata.org/entity/Q159', countryLabel='Россия', continent='http://www.wikidata.org/entity/Q48')])
        self.assertEqual(c['continentIds'], ['Q48'])

    def test_incomplete_snapshot_does_not_touch_public_data(self):
        before = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                Path('data/raw/world').mkdir(parents=True); Path('public').mkdir()
                Path('data/legacy-catalog.json').write_text('[]')
                Path('data/raw/world/manifest.json').write_text('{"complete": false}')
                Path('public/catalog.json').write_text('unchanged')
                with self.assertRaises(ValueError): world.build()
                self.assertEqual(Path('public/catalog.json').read_text(), 'unchanged')
            finally: os.chdir(before)

class WorldResumeTests(unittest.TestCase):
    def loader(self, root):
        spec = importlib.util.spec_from_file_location('fetch_world', Path(__file__).resolve().parents[1] / 'scripts/fetch-world.py')
        loader = importlib.util.module_from_spec(spec); spec.loader.exec_module(loader)
        loader.ROOT = root
        return loader

    def test_completed_batches_are_reused_and_incomplete_batches_refetched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); loader = self.loader(root)
            (root / 'classes.json').write_text(json.dumps([row(class_='unused')]).replace('class_', 'class'))
            # Existing IDs bypass the discovery stage entirely.
            (root / 'ids.json').write_text('["Q123"]')
            response = [row(city='http://www.wikidata.org/entity/Q123', cityLabel='Test')]
            with patch.object(loader, 'fetch', return_value=response) as fetch, patch.object(loader.time, 'sleep'), patch('sys.argv', ['fetch-world.py']):
                loader.main()
                self.assertEqual(fetch.call_count, 1)
                self.assertTrue(json.loads((root / 'manifest.json').read_text())['complete'])
                loader.main()
                self.assertEqual(fetch.call_count, 1)
                batch = next(root.glob('batch-*.json')); batch.write_text('[]')
                loader.main()
                self.assertEqual(fetch.call_count, 2)

    def test_persisted_retry_after_prevents_any_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); loader = self.loader(root)
            (root / 'rate-limit.json').write_text(json.dumps({'retryAt': loader.time.time() + 1000}))
            with patch.object(loader.urllib.request, 'urlopen') as request:
                with self.assertRaises(loader.DownloadDeferred): loader.fetch('SELECT ?city WHERE {}')
                request.assert_not_called()

if __name__ == '__main__': unittest.main()
