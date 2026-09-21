import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  historicalStatus,
  visibleAt,
  radiusFor,
  eventDateLabel,
  populationAt,
  type City,
} from '../lib/atlas.ts';
import { features } from '../lib/map-features.ts';
const catalog = JSON.parse(
  readFileSync(new URL('../public/catalog.json', import.meta.url), 'utf8'),
) as City[];
const city = (qid: string) => catalog.find((c) => c.wikidata === qid)!;
void test('Hong Kong settlement predates census; administrative events never grant city status', () => {
  const hk = city('Q8646');
  assert.equal(hk.appearanceYear, 1550);
  assert.equal(hk.settlement?.end, 1550);
  assert.equal(hk.firstPopulationObservation?.end, 1961);
  assert.equal(hk.cityStatus, null);
  assert.equal(visibleAt(hk, 1549), false);
  assert.equal(visibleAt(hk, 1550), true);
  assert.equal(populationAt(hk, 1900).value, null);
  assert.ok(hk.settlement?.explanation);
  assert.match(hk.settlement!.source, /epd.gov.hk/);
  for (const year of [1841, 1997])
    assert.equal(historicalStatus(hk, year), 'unknown');
});
void test('settlement then city status reverses without assuming an unknown status', () => {
  const c = city('Q15174');
  assert.equal(historicalStatus(c, 1978), 'settlement');
  assert.equal(historicalStatus(c, 1979), 'city');
  assert.equal(historicalStatus(c, 1978), 'settlement');
  assert.equal(historicalStatus({ ...c, cityStatus: null }, 2000), 'unknown');
  assert.equal(
    features([c], 1978, 0).features[0].properties?.status,
    'settlement',
  );
});
void test('interval uses upper bound and preserves uncertainty; ancient evidence remains dated', () => {
  const london = city('Q84');
  assert.equal(visibleAt(london, 49), false);
  assert.equal(visibleAt(london, 50), true);
  assert.match(eventDateLabel(london.settlement), /Не позднее/);
  const istanbul = city('Q406');
  assert.equal(istanbul.settlement?.end, -601);
  assert.equal(visibleAt(istanbul, -602), false);
  assert.equal(visibleAt(istanbul, -601), true);
});
void test('census-only appearance is neutral and has no historical pulse', () => {
  const c = catalog.find(
    (c) => c.appearanceBasis === 'population-observation' && c.coordinates,
  )!;
  const feature = features([c], c.appearanceYear!, 100).features[0];
  assert.equal(feature.properties?.color, '#9aa8b2');
  assert.equal(feature.properties?.born, false);
  assert.equal(feature.properties?.recent, false);
});
void test('population size respects world and street limits with smooth zoom scale', () => {
  for (const zoom of [0, 2, 3, 4, 5, 6, 12])
    for (const p of [1, 1000, 100000, 1000000, 1e10]) {
      const t = Math.max(0, Math.min(1, (zoom - 2) / 4));
      assert.equal(
        radiusFor(p, zoom),
        Math.max(
          2,
          Math.min(10 + 8 * t, 0.12 * Math.sqrt(p / 1000) * (1 + 0.8 * t)),
        ),
      );
      assert.equal(radiusFor(null, zoom), 3);
    }
});
