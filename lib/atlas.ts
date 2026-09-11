export type Observation = {
  year: number;
  value: number;
  source: string;
  segment?: string;
};
export type City = {
  id: string;
  name: string;
  region: string;
  coordinates: [number, number] | null;
  founded: number | null;
  dateLabel: string;
  dateKind: string;
  dateSource?: string;
  statusYear: string;
  formerNames: string;
  url: string;
  population: Observation[];
  notes: string[];
  wikidata?: string;
};
export function populationAt(city: City, year: number) {
  const points = city.population;
  if (city.founded !== null && year < city.founded)
    return { value: null, kind: 'not-born' as const };
  const before = points.filter((p) => p.year <= year).at(-1);
  const after = points.find((p) => p.year > year);
  if (!before) return { value: null, kind: 'unknown' as const };
  if (before.year === year)
    return {
      value: before.value,
      kind: 'observed' as const,
      year: before.year,
    };
  if (after && before.segment === after.segment)
    return {
      value:
        before.value +
        ((after.value - before.value) * (year - before.year)) /
          (after.year - before.year),
      kind: 'estimate' as const,
      year: before.year,
      endYear: after.year,
    };
  return { value: before.value, kind: 'last' as const, year: before.year };
}
export const visibleAt = (c: City, year: number) =>
  c.founded !== null && c.founded <= year;
export const radiusFor = (population: number | null) =>
  population === null
    ? 3
    : Math.max(3, Math.min(48, Math.sqrt(population / 1000) * 0.48));
export const formatNumber = (n: number) =>
  Math.round(n).toLocaleString('ru-RU');
export const yearLabel = (n: number) =>
  n < 0 ? `${Math.abs(n)} до н. э.` : String(n);
export function timelinePosition(year: number, min: number, max: number) {
  if (max <= min) return 0;
  const clamped = Math.max(min, Math.min(max, year));
  const span = max - min;
  const offset = Math.max(1, span / 25);
  return (
    Math.log((span + offset) / (max - clamped + offset)) /
    Math.log((span + offset) / offset)
  );
}
export function yearAtTimelinePosition(
  position: number,
  min: number,
  max: number,
) {
  if (max <= min) return min;
  const clamped = Math.max(0, Math.min(1, position));
  const span = max - min;
  const offset = Math.max(1, span / 25);
  return (
    max +
    offset -
    (span + offset) * Math.exp(-clamped * Math.log((span + offset) / offset))
  );
}
export const COLORS = {
  ancient: '#edc68d',
  medieval: '#f3bc72',
  siberia: '#7cceb7',
  industrial: '#75bce3',
  modern: '#ad9be6',
};
export function cityColor(year: number) {
  return year < 1000
    ? COLORS.ancient
    : year < 1500
      ? COLORS.medieval
      : year < 1800
        ? COLORS.siberia
        : year < 1900
          ? COLORS.industrial
          : COLORS.modern;
}
export function focusCluster(points: [number, number][]) {
  if (points.length < 2) return points;
  const distance = (a: [number, number], b: [number, number]) => {
    const meanLat = ((a[1] + b[1]) / 2) * (Math.PI / 180);
    return Math.hypot((a[0] - b[0]) * Math.cos(meanLat), a[1] - b[1]);
  };
  return points
    .map((center) => points.filter((point) => distance(center, point) <= 7))
    .reduce((best, cluster) => (cluster.length > best.length ? cluster : best));
}
export type Camera = {
  lng: number;
  lat: number;
  zoom: number;
  bearing: number;
  pitch: number;
};
export const HOME_CAMERA: Camera = {
  lng: 82,
  lat: 57,
  zoom: 2.25,
  bearing: -8,
  pitch: 35,
};
export type ViewState = {
  year: number;
  cityId: string | null;
  chapter: number | null;
  stop: number;
  camera: Camera;
};
export function parseView(
  search: string,
  min: number,
  max: number,
  ids: Set<string>,
): ViewState {
  const p = new URLSearchParams(search);
  const n = (key: string, fallback: number, lo: number, hi: number) => {
    const raw = p.get(key);
    const v = raw === null ? NaN : Number(raw);
    return Number.isFinite(v) ? Math.max(lo, Math.min(hi, v)) : fallback;
  };
  const id = p.get('city');
  const ch = p.get('chapter');
  return {
    year: n('year', 1897, min, max),
    cityId: id && ids.has(id) ? id : null,
    chapter: ch !== null && /^[0-4]$/.test(ch) ? Number(ch) : null,
    stop: Math.floor(n('stop', 0, 0, 2)),
    camera: {
      lng: n('lng', HOME_CAMERA.lng, -540, 540),
      lat: n('lat', HOME_CAMERA.lat, -80, 80),
      zoom: n('zoom', HOME_CAMERA.zoom, 1.5, 10),
      bearing: n('bearing', HOME_CAMERA.bearing, -180, 180),
      pitch: n('pitch', HOME_CAMERA.pitch, 0, 60),
    },
  };
}
export function serializeView(state: ViewState) {
  const p = new URLSearchParams({
    year: String(Math.floor(state.year)),
    lng: state.camera.lng.toFixed(4),
    lat: state.camera.lat.toFixed(4),
    zoom: state.camera.zoom.toFixed(2),
    bearing: state.camera.bearing.toFixed(1),
    pitch: state.camera.pitch.toFixed(1),
  });
  if (state.cityId) p.set('city', state.cityId);
  if (state.chapter !== null) {
    p.set('chapter', String(state.chapter));
    p.set('stop', String(state.stop));
  }
  return '?' + p.toString();
}
