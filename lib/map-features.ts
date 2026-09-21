import type { FeatureCollection } from 'geojson';
import {
  type City,
  visibleAt,
  populationAt,
  radiusFor,
  cityColor,
  historicalEvidence,
  historicalStatus,
} from './atlas.ts';
export function features(
  cities: City[],
  year: number,
  period: number,
  showUndated = false,
): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: cities
      .filter(
        (c) =>
          c.coordinates &&
          (visibleAt(c, year) || (showUndated && c.founded === null)),
      )
      .map((c) => {
        const p = populationAt(c, year);
        return {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: c.coordinates! },
          properties: {
            id: c.id,
            name: c.name,
            radius: radiusFor(p.value),
            radiusClose: radiusFor(p.value, 6),
            status: historicalStatus(c, year),
            known: p.value !== null,
            color:
              c.founded === null || !historicalEvidence(c)
                ? '#9aa8b2'
                : cityColor(c.founded),
            recent:
              historicalEvidence(c) &&
              c.founded !== null &&
              year - c.founded < period,
            born:
              historicalEvidence(c) &&
              c.founded !== null &&
              year - c.founded < 3,
          },
        };
      }),
  };
}
