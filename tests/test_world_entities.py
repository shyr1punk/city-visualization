import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('entities', Path(__file__).resolve().parents[1] / 'scripts/world_entities.py')
entities = importlib.util.module_from_spec(spec); spec.loader.exec_module(entities)

def snak(value): return {'snaktype': 'value', 'datavalue': {'value': value}}
def claim(value, rank='normal', qualifiers=None):
    return {'mainsnak': snak(value), 'rank': rank, 'qualifiers': qualifiers or {}}

class EntityRowsTests(unittest.TestCase):
    def test_label_fallback_and_projection_keep_source_revision(self):
        value = {'id': 'Q1', 'lastrevid': 42, 'labels': {'fr': {'value': 'Ville'}}, 'claims': {'P17': [], 'P999999': []}}
        projected = entities.project(value)
        self.assertEqual(entities.label(projected, 'Q1'), 'Ville')
        self.assertEqual(projected['lastrevid'], 42)
        self.assertNotIn('P999999', projected['claims'])
        self.assertEqual(entities.label({'labels': {'ru': {'value': 'Город'}, 'en': {'value': 'City'}}}, 'Q1'), 'Город')

    def test_only_current_non_deprecated_countries_are_used(self):
        value = {'claims': {'P17': [claim({'id': 'Q10'}, qualifiers={'P582': [snak({'time': '+1991-01-01'})]}), claim({'id': 'Q20'}), claim({'id': 'Q30'}, rank='deprecated')]}}
        self.assertEqual(entities.targets(value, 'P17', current=True), ['Q20'])

    def test_population_keeps_date_and_reference_without_part_or_deprecated_claims(self):
        observation = claim({'amount': '+123'}, qualifiers={'P585': [snak({'time': '+2000-01-01T00:00:00Z', 'precision': 9})]})
        observation['references'] = [{'snaks': {'P854': [snak('https://example.org/census')]}}]
        scoped = claim({'amount': '+999'}, qualifiers={'P518': [snak({'id': 'Q3'})], 'P585': [snak({'time': '+2000-01-01', 'precision': 9})]})
        value = {'claims': {'P1082': [observation, scoped, claim({'amount': '+1'}, rank='deprecated')]}}
        rows = entities.rows_for('Q1', value, {})
        observed = [r for r in rows if 'population' in r]
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0]['population']['value'], '+123')
        self.assertEqual(observed[0]['reference']['value'], 'https://example.org/census')

    def test_non_earth_coordinates_are_not_plotted(self):
        value = {'claims': {'P625': [claim({'longitude': 20, 'latitude': 10, 'globe': entities.ENTITY_URL + 'Q111'})]}}
        self.assertFalse(any('coord' in r for r in entities.rows_for('Q1', value, {})))

    def test_missing_history_still_has_identity_and_continents_follow_related_entities(self):
        value = {'labels': {'en': {'value': 'City'}}, 'claims': {'P131': [claim({'id': 'Q2'})]}}
        related = {'Q2': {'labels': {'ru': {'value': 'Регион'}}, 'claims': {'P30': [claim({'id': 'Q48'})]}}}
        rows = entities.rows_for('Q1', value, related)
        self.assertEqual(rows[0]['city']['value'], entities.ENTITY_URL + 'Q1')
        self.assertIn('Регион', [r.get('adminLabel', {}).get('value') for r in rows])
        self.assertIn(entities.ENTITY_URL + 'Q48', [r.get('adminContinent', {}).get('value') for r in rows])

    def test_network_disconnect_defers_after_bounded_retries(self):
        import http.client
        import json
        with tempfile.TemporaryDirectory() as tmp:
            cache = entities.EntityCache(Path(tmp))
            with patch.object(entities.urllib.request, 'urlopen', side_effect=http.client.RemoteDisconnected('closed')), patch.object(entities.time, 'sleep'):
                with self.assertRaises(entities.Deferred):
                    cache.request(['Q1'])
            self.assertTrue(cache.blocked)
            self.assertGreater(json.loads((Path(tmp) / 'api-rate-limit.json').read_text())['retryAt'], entities.time.time())

    def test_entity_cache_resumes_without_redownloading_saved_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = entities.EntityCache(Path(tmp))
            with patch.object(cache, 'request', return_value={'Q1': {'id': 'Q1', 'claims': {}}}) as request:
                cache.ensure(['Q1']); self.assertEqual(request.call_count, 1)
            resumed = entities.EntityCache(Path(tmp))
            with patch.object(resumed, 'request') as request:
                resumed.ensure(['Q1']); request.assert_not_called()

if __name__ == '__main__': unittest.main()
