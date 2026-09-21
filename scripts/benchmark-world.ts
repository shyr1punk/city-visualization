import { readFileSync } from 'node:fs';
import { performance } from 'node:perf_hooks';
import { matchesGeography } from '../lib/geography.ts';
import { features } from '../lib/map-features.ts';
import type { City } from '../lib/atlas.ts';
const data = JSON.parse(readFileSync('public/catalog.json', 'utf8')) as City[];
for (const [name, cities] of [
  ['catalog', data],
  [
    'synthetic stress only',
    Array.from({ length: 100000 }, (_, i) => ({
      ...data[i % data.length],
      id: String(i),
    })),
  ],
] as const) {
  const start = performance.now();
  const filtered = cities.filter((c) =>
    matchesGeography(c, {
      continents: ['Q46'],
      countries: [],
      showUndated: false,
    }),
  );
  const filterMs = performance.now() - start;
  const frame = performance.now();
  const geo = features(filtered, 2026, 25, true);
  console.log(
    JSON.stringify({
      name,
      cities: cities.length,
      filtered: filtered.length,
      markers: geo.features.length,
      filterMs: +filterMs.toFixed(1),
      frameMs: +(performance.now() - frame).toFixed(1),
    }),
  );
}
