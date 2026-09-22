import type { City } from './atlas';
export const CONTINENTS: Record<string, string> = {
  Q46: 'Европа',
  Q48: 'Азия',
  Q15: 'Африка',
  Q49: 'Северная Америка',
  Q18: 'Южная Америка',
  Q55643: 'Океания',
  Q51: 'Антарктида',
  unknown: 'Не определён',
};
export type Geography = {
  continents: string[];
  countries: string[];
  showUndated: boolean;
};
export const EMPTY_GEOGRAPHY: Geography = {
  continents: [],
  countries: [],
  showUndated: false,
};
// Conservative geographic extents, not a per-city assignment. A city whose
// continent is unresolved is included only if its entire possible extent is selected.
const COUNTRY_CONTINENT_EXTENTS: Record<string, readonly string[]> = {
  Q159: ['Q46', 'Q48'], // Russia
  Q232: ['Q46', 'Q48'], // Kazakhstan
  Q43: ['Q46', 'Q48'], // Turkey
};
export function matchesContinents(c: City, selected: string[]) {
  if (!selected.length) return true;
  const continents = c.continentIds?.length ? c.continentIds : ['unknown'];
  if (continents.some((id) => selected.includes(id))) return true;
  if (!continents.includes('unknown') || !c.countryIds?.length) return false;
  return c.countryIds.every((id) => {
    const extent = COUNTRY_CONTINENT_EXTENTS[id];
    return extent?.every((continent) => selected.includes(continent)) ?? false;
  });
}
export function matchesGeography(c: City, g: Geography) {
  return (
    matchesContinents(c, g.continents) &&
    (!g.countries.length ||
      (c.countryIds ?? ['unknown']).some((id) => g.countries.includes(id)))
  );
}
export function availableCountries(cities: City[], continents: string[]) {
  return new Set(
    cities
      .filter((c) => matchesContinents(c, continents))
      .flatMap((c) => c.countryIds ?? ['unknown']),
  );
}
export function normalizeGeography(g: Geography, cities: City[]): Geography {
  const continents = [...new Set(g.continents)].filter(
    (id) => id in CONTINENTS,
  );
  const allowed = availableCountries(cities, continents);
  return {
    continents,
    countries: [...new Set(g.countries)].filter((id) => allowed.has(id)),
    showUndated: g.showUndated,
  };
}
/** Smallest longitude arc, so Fiji and Samoa do not frame the whole planet. */
export function geographicBounds(
  points: [number, number][],
): [[number, number], [number, number]] | null {
  if (!points.length) return null;
  const lngs = points
    .map((p) => ((p[0] % 360) + 360) % 360)
    .sort((a, b) => a - b);
  let gap = -1,
    start = lngs[0];
  for (let i = 0; i < lngs.length; i++) {
    const next = i + 1 < lngs.length ? lngs[i + 1] : lngs[0] + 360;
    if (next - lngs[i] > gap) {
      gap = next - lngs[i];
      start = next % 360;
    }
  }
  if (start > 180) start -= 360;
  let south = 85,
    north = -85;
  for (const [, lat] of points) {
    south = Math.min(south, lat);
    north = Math.max(north, lat);
  }
  return [
    [start, Math.max(-85, south)],
    [start + 360 - gap, Math.min(85, north)],
  ];
}
