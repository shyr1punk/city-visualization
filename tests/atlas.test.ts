import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  populationAt,
  visibleAt,
  radiusFor,
  parseView,
  serializeView,
  HOME_CAMERA,
  focusCluster,
  timelinePosition,
  yearAtTimelinePosition,
} from '../lib/atlas.ts';
import type { City } from '../lib/atlas.ts';
const data = JSON.parse(
  readFileSync(new URL('../public/catalog.json', import.meta.url), 'utf8'),
) as City[];
const sample: City = {
  id: 'a',
  name: 'A',
  region: 'R',
  country: 'Россия',
  coordinates: [30, 50],
  founded: 1800,
  dateLabel: '1800',
  dateKind: 'foundation',
  statusYear: '1800',
  formerNames: '',
  url: 'https://example.org',
  notes: [],
  population: [
    { year: 1900, value: 10000, source: 'https://example.org', segment: '0' },
    { year: 1920, value: 30000, source: 'https://example.org', segment: '0' },
    { year: 1940, value: 20000, source: 'https://example.org', segment: '0' },
    { year: 1960, value: 90000, source: 'https://example.org', segment: '1' },
  ],
};
void test('appearance and reversing across founding boundary', () => {
  assert.equal(visibleAt(sample, 1799), false);
  assert.equal(visibleAt(sample, 1800), true);
  assert.equal(visibleAt(sample, 1799), false);
  assert.equal(visibleAt({ ...sample, founded: null }, 2025), false);
});
void test('no population invented before first observation or founding', () => {
  assert.equal(populationAt(sample, 1700).kind, 'not-born');
  assert.equal(populationAt(sample, 1850).value, null);
});
void test('population grows and shrinks between observations', () => {
  assert.equal(populationAt(sample, 1910).value, 20000);
  assert.equal(populationAt(sample, 1930).value, 25000);
  assert.equal(populationAt(sample, 1900).kind, 'observed');
  assert.equal(populationAt(sample, 1910).kind, 'estimate');
});
void test('administrative break never interpolates', () => {
  assert.deepEqual(populationAt(sample, 1950), {
    value: 20000,
    kind: 'last',
    year: 1940,
  });
  assert.equal(populationAt(sample, 1970).year, 1960);
});
void test('area ratio proportional away from display limits', () => {
  assert.ok(
    Math.abs(radiusFor(400000) ** 2 / radiusFor(100000) ** 2 - 4) < 1e-9,
  );
  assert.equal(radiusFor(null), 3);
  assert.equal(radiusFor(1e12), 48);
});
void test('URL roundtrip preserves view, city, chapter, stop and pitch', () => {
  const s = {
    continents: [],
    countries: [],
    showUndated: false,
    year: 1587,
    cityId: 'a',
    chapter: 2,
    stop: 1,
    projection: 'globe' as const,
    camera: { ...HOME_CAMERA, pitch: 22.5 },
  };
  assert.deepEqual(parseView(serializeView(s), -497, 2025, new Set(['a'])), s);
});
void test('malformed URLs fail safely', () => {
  const v = parseView(
    '?year=NaN&city=unknown&chapter=99&stop=-4&pitch=500&lng=Infinity',
    -497,
    2025,
    new Set(['a']),
  );
  assert.equal(v.year, 1897);
  assert.equal(v.cityId, null);
  assert.equal(v.chapter, null);
  assert.equal(v.stop, 0);
  assert.equal(v.projection, 'globe');
  assert.equal(v.camera.pitch, 60);
  assert.equal(v.camera.lng, HOME_CAMERA.lng);
});
void test('camera URLs preserve a wrapped world position east of Kamchatka', () => {
  const camera = { ...HOME_CAMERA, lng: 205 };
  const view = parseView(
    serializeView({
      year: 1900,
      cityId: null,
      chapter: null,
      stop: 0,
      projection: 'mercator',
      camera,
    }),
    -497,
    2025,
    new Set(),
  );
  assert.equal(view.camera.lng, 205);
  assert.equal(view.projection, 'mercator');
});
void test('globe projection is the default and survives URL roundtrip', () => {
  assert.equal(parseView('', -497, 2025, new Set()).projection, 'globe');
  const url = serializeView({
    year: 1900,
    cityId: null,
    chapter: null,
    stop: 0,
    projection: 'globe',
    camera: HOME_CAMERA,
  });
  assert.equal(parseView(url, -497, 2025, new Set()).projection, 'globe');
});
void test('auto focus chooses the densest nearby city cluster', () => {
  assert.deepEqual(
    focusCluster([
      [37.6, 55.7],
      [41, 56],
      [132, 43],
    ]),
    [
      [37.6, 55.7],
      [41, 56],
    ],
  );
});
void test('log timeline is reversible and gives recent centuries more room', () => {
  const min = -497;
  const max = 2025;
  for (const year of [min, 1, 1000, 1500, 1800, 1900, max]) {
    const restored = yearAtTimelinePosition(
      timelinePosition(year, min, max),
      min,
      max,
    );
    assert.ok(Math.abs(restored - year) < 1e-9);
  }
  assert.equal(timelinePosition(min, min, max), 0);
  assert.equal(timelinePosition(max, min, max), 1);
  assert.ok(
    timelinePosition(2025, min, max) - timelinePosition(1900, min, max) >
      timelinePosition(-372, min, max) - timelinePosition(min, min, max),
  );
});
void test('dataset has unique exact identities and valid geography', () => {
  assert.equal(new Set(data.map((c) => c.id)).size, data.length);
  assert.equal(new Set(data.map((c) => c.wikidata)).size, data.length);
  for (const c of data) {
    if (c.coordinates) {
      assert.ok(c.coordinates[0] >= -180 && c.coordinates[0] <= 180, c.name);
      assert.ok(c.coordinates[1] >= -90 && c.coordinates[1] <= 90, c.name);
    }
    assert.ok(c.country, c.name);
  }
});
void test('world catalog retains all 15 former Soviet republics', () => {
  const countries = new Set(data.map((c) => c.country));
  for (const country of [
    'Азербайджан',
    'Армения',
    'Беларусь',
    'Грузия',
    'Казахстан',
    'Кыргызстан',
    'Латвия',
    'Литва',
    'Молдова',
    'Россия',
    'Таджикистан',
    'Туркменистан',
    'Узбекистан',
    'Украина',
    'Эстония',
  ])
    assert.ok(countries.has(country), country);
});
void test('empty timeline bins are rendered without a minimum bar', () => {
  const page = readFileSync(
    new URL('../app/page.tsx', import.meta.url),
    'utf8',
  );
  assert.match(page, /bin\.count === 0\s*\? 0/);
});
void test('homonyms and federal city subdivisions remain distinct', () => {
  for (const n of ['Павловск', 'Троицк', 'Зеленогорск', 'Советск']) {
    const cs = data.filter((c) => c.name === n);
    assert.ok(cs.length >= 2);
    assert.equal(new Set(cs.map((c) => c.wikidata)).size, cs.length);
  }
  const b = data.find((c) => c.name === 'Балаклава')!;
  assert.ok(b.coordinates![1] > 44 && b.coordinates![1] < 45);
});
void test('population observations are ordered, sourced, finite and after founding', () => {
  for (const c of data) {
    let prev = -Infinity;
    for (const p of c.population) {
      assert.ok(p.year > prev, c.name);
      assert.ok(p.value > 0 && Number.isFinite(p.value), c.name);
      assert.match(p.source, /^https?:\/\//);
      assert.ok(c.founded === null || p.year >= c.founded, c.name);
      prev = p.year;
    }
  }
});
void test('story cities have expected dates and distinct status semantics', () => {
  const find = (n: string) =>
    data.find((c) => c.name === n && c.country === 'Россия')!;
  assert.equal(find('Москва').founded, 1147);
  assert.equal(find('Москва').dateKind, 'first-mention');
  assert.equal(find('Обнинск').founded, 1946);
  assert.match(find('Обнинск').statusYear, /1956/);
  assert.ok(find('Тюмень').population.length > 20);
});
