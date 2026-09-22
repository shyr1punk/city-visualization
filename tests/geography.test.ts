import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  EMPTY_GEOGRAPHY,
  matchesGeography,
  normalizeGeography,
  geographicBounds,
} from '../lib/geography.ts';
import {
  parseView,
  serializeView,
  HOME_CAMERA,
  type City,
} from '../lib/atlas.ts';
import { features } from '../lib/map-features.ts';
const city = (
  id: string,
  countryIds: string[],
  continentIds: string[],
  founded: number | null = 1000,
): City => ({
  id,
  name: id,
  country: countryIds.join(),
  countryIds,
  continentIds,
  founded,
  coordinates: [20, 30],
  region: '',
  dateLabel: '',
  dateKind: '',
  statusYear: '',
  formerNames: '',
  url: '',
  notes: [],
  population: [],
});
const sample = [
  city('Paris', ['FR'], ['Q46']),
  city('Tokyo', ['JP'], ['Q48']),
  city('London', ['GB'], ['Q46']),
  city('Istanbul', ['TR'], ['Q46', 'Q48']),
  city('unknown', ['unknown'], ['unknown'], null),
];
void test('union within geography groups, intersection between them', () => {
  const g = {
    continents: ['Q46', 'Q48'],
    countries: ['FR', 'JP'],
    showUndated: false,
  };
  assert.deepEqual(
    sample.filter((c) => matchesGeography(c, g)).map((c) => c.id),
    ['Paris', 'Tokyo'],
  );
  assert.equal(
    sample.filter((c) => matchesGeography(c, EMPTY_GEOGRAPHY)).length,
    5,
  );
  assert.equal(
    sample.filter((c) => matchesGeography(c, { ...g, continents: ['Q15'] }))
      .length,
    0,
  );
});
void test('transcontinental city is found on either continent without duplication', () => {
  for (const id of ['Q46', 'Q48'])
    assert.ok(
      matchesGeography(sample[3], { ...EMPTY_GEOGRAPHY, continents: [id] }),
    );
  assert.equal(
    sample.filter((c) =>
      matchesGeography(c, {
        continents: ['Q46', 'Q48'],
        countries: ['TR'],
        showUndated: false,
      }),
    ).length,
    1,
  );
});
void test('changing continent removes incompatible selections; invalid IDs are ignored', () => {
  assert.deepEqual(
    normalizeGeography(
      {
        continents: ['Q46', 'invalid', 'Q46'],
        countries: ['FR', 'JP', 'bad'],
        showUndated: true,
      },
      sample,
    ),
    { continents: ['Q5401'], countries: ['FR', 'JP'], showUndated: true },
  );
});
void test('unknown geography remains individually selectable', () => {
  assert.deepEqual(
    sample
      .filter((c) =>
        matchesGeography(c, { ...EMPTY_GEOGRAPHY, continents: ['unknown'] }),
      )
      .map((c) => c.id),
    ['unknown'],
  );
});
void test('new links preserve geography and undated layer; old links are unrestricted', () => {
  const state = {
    ...EMPTY_GEOGRAPHY,
    continents: ['Q46'],
    countries: ['FR'],
    showUndated: true,
    year: 1897,
    cityId: null,
    chapter: null,
    stop: 0,
    projection: 'globe' as const,
    camera: HOME_CAMERA,
  };
  assert.deepEqual(
    parseView(serializeView(state), -1499, 2026, new Set()),
    state,
  );
  const old = parseView('?year=1900', -1499, 2026, new Set());
  assert.deepEqual(old.continents, []);
  assert.deepEqual(old.countries, []);
  assert.equal(old.showUndated, false);
});
void test('antimeridian bounds frame nearby islands without a world-spanning box', () => {
  assert.deepEqual(
    geographicBounds([
      [179, -20],
      [-178, -15],
    ]),
    [
      [179, -20],
      [182, -15],
    ],
  );
  assert.deepEqual(geographicBounds([[30, 40]]), [
    [30, 40],
    [30, 40],
  ]);
  assert.equal(geographicBounds([]), null);
});
void test('undated markers have no era, pulse or historical appearance', () => {
  const undated = sample[4];
  assert.equal(features([undated], 1900, 25).features.length, 0);
  const result = features([undated], 1900, 25, true).features[0];
  assert.equal(result.properties?.color, '#9aa8b2');
  assert.equal(result.properties?.recent, false);
  assert.equal(result.properties?.born, false);
  assert.equal(
    features([{ ...undated, coordinates: null }], 1900, 25, true).features
      .length,
    0,
  );
  assert.equal(
    features([city('future', ['FR'], ['Q46'], 2000)], 1900, 25, true).features
      .length,
    0,
  );
});
void test('index and country shards cover every record and preserve all legacy city histories', () => {
  const load = (path: string) =>
    JSON.parse(readFileSync(new URL('../' + path, import.meta.url), 'utf8'));
  const index = load('public/catalog-index.json');
  const catalog = load('public/catalog.json') as City[];
  const byId = new Map(catalog.map((c) => [c.id, c]));
  assert.equal(index.cities.length, catalog.length);
  const shards = [...new Set(catalog.map((c) => c.detailKey))].flatMap((k) =>
    load(`public/catalog/${k}.json`),
  ) as City[];
  assert.equal(new Set(shards.map((c) => c.id)).size, catalog.length);
  for (const legacy of load('data/legacy-catalog.json') as City[]) {
    const updated = byId.get(legacy.id)!;
    assert.ok(updated);
    assert.deepEqual(updated.population, legacy.population);
    assert.equal(updated.originalDate?.founded, legacy.founded);
    assert.equal(updated.wikidata, legacy.wikidata);
  }
  for (const c of catalog) {
    assert.ok(c.countryIds?.length);
    assert.ok(c.continentIds?.length);
    assert.ok(c.countryIds?.every((id) => index.countries[id]));
  }
});

void test('combined Eurasia includes every Russian city without guessing its individual continent', () => {
  const catalog = JSON.parse(
    readFileSync(new URL('../public/catalog.json', import.meta.url), 'utf8'),
  ) as City[];
  const russia = catalog.filter((c) => c.countryIds?.includes('Q159'));
  const combined = { ...EMPTY_GEOGRAPHY, continents: ['Q46', 'Q48'] };
  assert.ok(russia.length > 1000);
  assert.deepEqual(
    russia.filter((c) => matchesGeography(c, combined)).map((c) => c.id),
    russia.map((c) => c.id),
  );
  const unresolved = city('Ural', ['Q159'], ['unknown']);
  for (const continents of [['Q15']])
    assert.equal(
      matchesGeography(unresolved, { ...combined, continents }),
      false,
    );
  assert.equal(
    matchesGeography(unresolved, { ...combined, continents: ['unknown'] }),
    true,
  );
  assert.equal(
    matchesGeography(unresolved, { ...combined, countries: ['Q43'] }),
    false,
  );
  assert.equal(
    matchesGeography(
      city('Unknown country', ['unknown'], ['unknown']),
      combined,
    ),
    false,
  );
  assert.deepEqual(
    normalizeGeography({ ...combined, countries: ['Q159'] }, [unresolved])
      .countries,
    ['Q159'],
  );
  assert.equal(
    matchesGeography(
      city('Uncertain countries', ['Q159', 'unknown'], ['unknown']),
      combined,
    ),
    false,
  );
});

void test('Eurasia replaces both old continent IDs and keeps country intersection', () => {
  for (const ids of [['Q46'], ['Q48'], ['Q46', 'Q48'], ['Q5401']]) {
    const g = normalizeGeography(
      { ...EMPTY_GEOGRAPHY, continents: ids },
      sample,
    );
    assert.deepEqual(g.continents, ['Q5401']);
    assert.deepEqual(
      sample.filter((c) => matchesGeography(c, g)).map((c) => c.id),
      ['Paris', 'Tokyo', 'London', 'Istanbul'],
    );
    assert.deepEqual(
      sample
        .filter((c) => matchesGeography(c, { ...g, countries: ['JP'] }))
        .map((c) => c.id),
      ['Tokyo'],
    );
  }
  assert.deepEqual(
    normalizeGeography(
      { ...EMPTY_GEOGRAPHY, continents: ['Q15'], countries: ['FR', 'JP'] },
      sample,
    ).countries,
    [],
  );
  const catalog = JSON.parse(
    readFileSync(new URL('../public/catalog.json', import.meta.url), 'utf8'),
  ) as City[];
  assert.ok(
    catalog
      .filter((c) => c.countryIds?.includes('Q159'))
      .every((c) =>
        matchesGeography(c, { ...EMPTY_GEOGRAPHY, continents: ['Q5401'] }),
      ),
  );
});
