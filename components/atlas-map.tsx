/* oxlint-disable react/react-compiler -- Imperative MapLibre lifecycle is intentionally outside React Compiler. */
'use client';
import { useEffect, useRef, useState } from 'react';
import type { Map as MapType, GeoJSONSource, Marker } from 'maplibre-gl';
import type { FeatureCollection } from 'geojson';
import {
  Camera,
  City,
  HOME_CAMERA,
  visibleAt,
  populationAt,
  radiusFor,
  cityColor,
} from '../lib/atlas';
import 'maplibre-gl/dist/maplibre-gl.css';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
export type MapAction = {
  action: string;
  seq: number;
  coordinates?: [number, number];
};
type Props = {
  cities: City[];
  year: number;
  flat: boolean;
  selected: City | null;
  onSelect: (c: City) => void;
  action: MapAction;
  initialCamera: Camera;
  onCamera: (c: Camera) => void;
  onInteract: () => void;
  period: number;
  reduced: boolean;
  onFailure: () => void;
};
function features(
  cities: City[],
  year: number,
  period: number,
): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: cities
      .filter((c) => c.coordinates && visibleAt(c, year))
      .map((c) => {
        const p = populationAt(c, year);
        return {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: c.coordinates! },
          properties: {
            id: c.id,
            name: c.name,
            radius: radiusFor(p.value),
            known: p.value !== null,
            color: cityColor(c.founded!),
            recent: year - c.founded! < period,
            born: year - c.founded! < 3,
          },
        };
      }),
  };
}
const labelNames = [
  'Москва',
  'Санкт-Петербург',
  'Казань',
  'Екатеринбург',
  'Новосибирск',
  'Красноярск',
  'Иркутск',
  'Якутск',
  'Владивосток',
  'Хабаровск',
  'Магадан',
  'Норильск',
  'Архангельск',
  'Дербент',
  'Калининград',
];
export default function AtlasMap(props: Props) {
  const {
    cities,
    year,
    flat,
    selected,
    action,
    initialCamera,
    period,
    reduced,
  } = props;
  const el = useRef<HTMLDivElement>(null),
    map = useRef<MapType | null>(null),
    latest = useRef(props),
    labels = useRef<{ city: City; marker: Marker }[]>([]);
  latest.current = props;
  const previousFlat = useRef(flat);
  const [ready, setReady] = useState(false),
    [failed, setFailed] = useState(false);
  useEffect(() => {
    setReady(false);
    let cancelled = false;
    let frame = 0;
    let watchdog: ReturnType<typeof setTimeout>;
    import('maplibre-gl')
      .then((m) => {
        if (cancelled || !el.current) return;
        try {
          m.setWorkerUrl(workerUrl);
          const graticule: FeatureCollection = {
            type: 'FeatureCollection',
            features: [],
          };
          for (let lng = -180; lng < 180; lng += 15)
            graticule.features.push({
              type: 'Feature',
              properties: {},
              geometry: {
                type: 'LineString',
                coordinates: Array.from({ length: 33 }, (_, i) => [
                  lng,
                  -80 + i * 5,
                ]),
              },
            });
          for (let lat = -75; lat <= 75; lat += 15)
            graticule.features.push({
              type: 'Feature',
              properties: {},
              geometry: {
                type: 'LineString',
                coordinates: Array.from({ length: 73 }, (_, i) => [
                  -180 + i * 5,
                  lat,
                ]),
              },
            });
          const x = new m.Map({
            container: el.current,
            center: [initialCamera.lng, initialCamera.lat],
            zoom: initialCamera.zoom,
            pitch: initialCamera.pitch,
            bearing: initialCamera.bearing,
            minZoom: 1.5,
            maxZoom: 10,
            maxPitch: 60,
            renderWorldCopies: false,
            attributionControl: { compact: true },
            style: {
              version: 8,
              sources: {
                world: {
                  type: 'geojson',
                  data: '/world.geojson',
                  attribution: '© Natural Earth · Public domain',
                },
                rivers: { type: 'geojson', data: '/rivers.geojson' },
                grid: { type: 'geojson', data: graticule },
              },
              layers: [
                {
                  id: 'background',
                  type: 'background',
                  paint: { 'background-color': '#080f17' },
                },
                {
                  id: 'land',
                  type: 'fill',
                  source: 'world',
                  paint: {
                    'fill-color': [
                      'case',
                      ['==', ['get', 'ADM0_A3'], 'RUS'],
                      '#233a40',
                      '#14262d',
                    ],
                  },
                },
                {
                  id: 'grid',
                  type: 'line',
                  source: 'grid',
                  paint: {
                    'line-color': '#8ba8ac',
                    'line-width': 0.5,
                    'line-opacity': 0.1,
                  },
                },
                {
                  id: 'boundaries',
                  type: 'line',
                  source: 'world',
                  paint: {
                    'line-color': '#66888d',
                    'line-width': 0.7,
                    'line-opacity': 0.4,
                  },
                },
                {
                  id: 'rivers',
                  type: 'line',
                  source: 'rivers',
                  paint: {
                    'line-color': '#3f6571',
                    'line-width': [
                      'interpolate',
                      ['linear'],
                      ['zoom'],
                      2,
                      0.5,
                      6,
                      1.5,
                    ],
                    'line-opacity': 0.5,
                  },
                },
              ],
            },
          });
          map.current = x;
          const fail = () => {
            if (cancelled) return;
            setFailed(true);
            latest.current.onFailure();
          };
          watchdog = setTimeout(() => {
            if (!x.isStyleLoaded()) fail();
          }, 20000);
          x.on('load', () => {
            clearTimeout(watchdog);
            if (cancelled) return;
            x.addSource('cities', {
              type: 'geojson',
              data: features(
                cities,
                latest.current.year,
                latest.current.period,
              ),
            });
            x.addLayer({
              id: 'glow',
              type: 'circle',
              source: 'cities',
              paint: {
                'circle-radius': ['*', ['get', 'radius'], 2.8],
                'circle-color': ['get', 'color'],
                'circle-opacity': 0.19,
                'circle-blur': 1,
              },
            });
            x.addLayer({
              id: 'dots',
              type: 'circle',
              source: 'cities',
              paint: {
                'circle-radius': ['get', 'radius'],
                'circle-color': ['get', 'color'],
                'circle-opacity': ['case', ['get', 'known'], 0.8, 0.04],
                'circle-stroke-color': ['get', 'color'],
                'circle-stroke-width': 1,
                'circle-stroke-opacity': 0.9,
                'circle-radius-transition': { duration: 120 },
              },
            });
            x.addLayer({
              id: 'period',
              type: 'circle',
              source: 'cities',
              filter: ['==', ['get', 'recent'], true],
              paint: {
                'circle-radius': ['+', ['get', 'radius'], 5],
                'circle-opacity': 0,
                'circle-stroke-width': 1,
                'circle-stroke-color': '#fff1c7',
                'circle-stroke-opacity': latest.current.period ? 0.55 : 0,
              },
            });
            x.addLayer({
              id: 'birth',
              type: 'circle',
              source: 'cities',
              filter: ['==', ['get', 'born'], true],
              paint: {
                'circle-radius': 12,
                'circle-opacity': 0,
                'circle-stroke-width': 1,
                'circle-stroke-color': '#fff1c7',
                'circle-stroke-opacity': 0.5,
              },
            });
            x.addLayer({
              id: 'selected',
              type: 'circle',
              source: 'cities',
              filter: ['==', ['get', 'id'], latest.current.selected?.id ?? ''],
              paint: {
                'circle-radius': ['+', ['get', 'radius'], 7],
                'circle-opacity': 0,
                'circle-stroke-color': '#fff2cb',
                'circle-stroke-width': 1.5,
              },
            });
            for (const city of cities.filter(
              (c) => labelNames.includes(c.name) && c.coordinates,
            )) {
              const el = document.createElement('button');
              el.className = 'city-map-label';
              el.textContent = city.name;
              el.setAttribute('aria-label', 'Открыть ' + city.name);
              el.addEventListener('click', (e) => {
                e.stopPropagation();
                latest.current.onSelect(city);
              });
              el.style.display = visibleAt(city, latest.current.year)
                ? ''
                : 'none';
              const marker = new m.Marker({
                element: el,
                anchor: 'top',
                offset: [0, 11],
              })
                .setLngLat(city.coordinates!)
                .addTo(x);
              labels.current.push({ city, marker });
            }
            setReady(true);
            let last = 0;
            const pulse = (t: number) => {
              if (cancelled) return;
              if (t - last > 80) {
                const reduced = latest.current.reduced;
                x.setPaintProperty(
                  'birth',
                  'circle-radius',
                  reduced ? 8 : 7 + ((t % 1800) / 1800) * 17,
                );
                x.setPaintProperty(
                  'birth',
                  'circle-stroke-opacity',
                  reduced ? 0.35 : 0.65 * (1 - (t % 1800) / 1800),
                );
                last = t;
              }
              frame = requestAnimationFrame(pulse);
            };
            frame = requestAnimationFrame(pulse);
          });
          x.on('click', 'dots', (e) => {
            const c = cities.find(
              (c) => c.id === e.features?.[0].properties.id,
            );
            if (c) latest.current.onSelect(c);
          });
          x.on(
            'mouseenter',
            'dots',
            () => (x.getCanvas().style.cursor = 'pointer'),
          );
          x.on('mouseleave', 'dots', () => (x.getCanvas().style.cursor = ''));
          for (const event of [
            'dragstart',
            'zoomstart',
            'rotatestart',
            'pitchstart',
          ] as const)
            x.on(event, (e) => {
              if (e.originalEvent) {
                // MapLibre cancels camera flights when a gesture starts.
                // Calling stop() here also resets the active gesture handlers.
                latest.current.onInteract();
              }
            });
          x.on('moveend', () => {
            const c = x.getCenter();
            latest.current.onCamera({
              lng: c.lng,
              lat: c.lat,
              zoom: x.getZoom(),
              bearing: x.getBearing(),
              pitch: x.getPitch(),
            });
          });
          x.getCanvas().addEventListener('pointerdown', () =>
            latest.current.onInteract(),
          );
          x.getCanvas().addEventListener(
            'wheel',
            () => latest.current.onInteract(),
            { passive: true },
          );
          x.getCanvas().addEventListener('keydown', () =>
            latest.current.onInteract(),
          );
          x.getCanvas().addEventListener('webglcontextlost', fail);
          x.on('error', (e) => {
            console.warn('Map resource', e.error.message);
            if (e.error.message.includes('world.geojson')) fail();
          });
        } catch {
          setFailed(true);
          latest.current.onFailure();
        }
      })
      .catch(() => {
        setFailed(true);
        latest.current.onFailure();
      });
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      clearTimeout(watchdog);
      labels.current.forEach((l) => l.marker.remove());
      labels.current = [];
      map.current?.remove();
      map.current = null;
    };
  }, [cities, initialCamera]);
  useEffect(() => {
    if (!ready || !map.current?.getSource('cities')) return;
    const x = map.current;
    void (x.getSource('cities') as GeoJSONSource)?.setData(
      features(cities, year, period),
    );
    x.setPaintProperty('period', 'circle-stroke-opacity', period ? 0.55 : 0);
    for (const l of labels.current) {
      l.marker.getElement().style.display = visibleAt(l.city, year)
        ? ''
        : 'none';
      l.marker.setOffset([0, radiusFor(populationAt(l.city, year).value) + 6]);
    }
  }, [year, period, ready, cities]);
  useEffect(() => {
    if (ready && previousFlat.current !== flat) {
      previousFlat.current = flat;
      map.current?.easeTo({
        pitch: flat ? 0 : 35,
        duration: reduced ? 0 : 800,
      });
    }
  }, [flat, ready, reduced]);
  useEffect(() => {
    if (ready && map.current?.getLayer('selected'))
      map.current.setFilter('selected', [
        '==',
        ['get', 'id'],
        selected?.id ?? '',
      ]);
  }, [selected, ready]);
  useEffect(() => {
    if (!ready || !map.current) return;
    const m = map.current;
    const { flat, reduced } = latest.current;
    const duration = reduced ? 0 : 1600;
    if (action.action === 'in') m.zoomIn({ duration: reduced ? 0 : 300 });
    if (action.action === 'out') m.zoomOut({ duration: reduced ? 0 : 300 });
    if (action.action === 'home')
      m.flyTo({
        center: [HOME_CAMERA.lng, HOME_CAMERA.lat],
        zoom: HOME_CAMERA.zoom,
        bearing: HOME_CAMERA.bearing,
        pitch: flat ? 0 : 35,
        duration,
      });
    if (action.action === 'city' && action.coordinates)
      m.flyTo({
        center: action.coordinates,
        zoom: 5.1,
        duration,
        padding: { left: 0, right: 0, top: 20, bottom: 100 },
      });
  }, [action, ready]);
  return (
    <>
      <div
        ref={el}
        className="map-surface"
        aria-label="Интерактивная карта городов"
      />
      {failed && (
        <output className="map-fallback">
          Карта недоступна в этом браузере. Поиск, список городов и их история
          продолжают работать.
        </output>
      )}
    </>
  );
}
