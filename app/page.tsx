/* oxlint-disable react/react-compiler -- URL hydration and animation are explicitly managed; React Compiler is not enabled. */
/* oxlint-disable next/no-html-link-for-pages -- The home link intentionally resets the full exploration URL. */
'use client';
import { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import {
  Search,
  Play,
  Pause,
  Plus,
  Minus,
  Compass,
  ArrowUpRight,
  ArrowLeft,
  ArrowRight,
  X,
  Info,
  Share2,
  List,
  Check,
  ChevronRight,
} from 'lucide-react';
import coverage from '../public/coverage.json';
import {
  Camera,
  City,
  HOME_CAMERA,
  visibleAt,
  populationAt,
  formatNumber,
  yearLabel,
  parseView,
  serializeView,
  COLORS,
} from '../lib/atlas';
import { chapters } from '../lib/chapters';
import AtlasMap, { MapAction } from '../components/atlas-map';
import PopulationChart from '../components/population-chart';
const normalize = (s: string) => s.toLowerCase().replaceAll('ё', 'е');
const dateKinds: Record<string, string> = {
  foundation: 'Основание',
  'first-mention': 'Первое упоминание',
  'foundation-or-mention': 'Основание или первое упоминание',
  inception: 'Начало существования по Wikidata',
};
function populationCaption(c: City, year: number) {
  const p = populationAt(c, year);
  return p.kind === 'not-born'
    ? 'Город ещё не появился на ленте'
    : p.kind === 'unknown'
      ? 'Нет наблюдений для этого времени'
      : p.kind === 'estimate'
        ? `Оценка между ${p.year} и ${p.endYear}`
        : p.kind === 'last'
          ? `Последнее наблюдение: ${p.year}`
          : `Наблюдение за ${p.year} год`;
}
export default function Home() {
  const [loaded, setLoaded] = useState<City[] | null>(null),
    [error, setError] = useState(false);
  useEffect(() => {
    const ac = new AbortController();
    fetch('/catalog.json', { signal: ac.signal })
      .then((r) => {
        if (!r.ok) throw Error('catalog');
        return r.json();
      })
      .then((data) => {
        if (!Array.isArray(data) || !data.length) throw Error('catalog');
        setLoaded(data as City[]);
      })
      .catch((e) => {
        if (e.name !== 'AbortError') setError(true);
      });
    return () => ac.abort();
  }, []);
  if (!loaded)
    return (
      <main className="loading-atlas">
        <Compass size={40} />
        <h1>Города во времени</h1>
        <output>
          {error
            ? 'Не удалось загрузить каталог. Проверьте соединение.'
            : 'Открываем исторический атлас…'}
        </output>
        {error && (
          <button onClick={() => location.reload()}>Повторить загрузку</button>
        )}
      </main>
    );
  return <Atlas cities={loaded} />;
}
function Atlas({ cities }: { cities: City[] }) {
  const { MIN, MAX, ids, bins, histogramMax } = useMemo(() => {
    const MIN = Math.min(
      ...cities.filter((c) => c.founded !== null).map((c) => c.founded!),
    );
    const MAX = Math.max(
      ...cities.flatMap((c) => c.population.map((p) => p.year)),
    );
    const ids = new Set(cities.map((c) => c.id));
    const bins = Array.from({ length: 100 }, (_, i) => {
      const start = MIN + (i * (MAX - MIN)) / 100;
      return {
        start,
        count: cities.filter(
          (c) =>
            c.founded !== null &&
            c.founded >= start &&
            c.founded < start + (MAX - MIN) / 100,
        ).length,
      };
    });
    const histogramMax = Math.max(...bins.map((b) => b.count));

    return { MIN, MAX, ids, bins, histogramMax };
  }, [cities]);
  const [year, setYear] = useState(1897),
    [playing, setPlaying] = useState(false),
    [query, setQuery] = useState(''),
    [selected, setSelected] = useState<City | null>(null),
    [flat, setFlat] = useState(false),
    [speed, setSpeed] = useState(1),
    [period, setPeriod] = useState(0);
  const [mapAction, setMapAction] = useState<MapAction>({
      action: 'none',
      seq: 0,
    }),
    [modal, setModal] = useState<'about' | 'list' | null>(null),
    [listQuery, setListQuery] = useState(''),
    [chapter, setChapter] = useState<number | null>(null),
    [stop, setStop] = useState(0),
    [reduced, setReduced] = useState(false),
    [hydrated, setHydrated] = useState(false),
    [mapFailed, setMapFailed] = useState(false),
    [copied, setCopied] = useState(false),
    [shareError, setShareError] = useState(false);
  const [camera, setCamera] = useState<Camera>(HOME_CAMERA);
  const initialCamera = useRef(HOME_CAMERA),
    modalRef = useRef<HTMLDialogElement>(null),
    yearRef = useRef(year),
    searchRef = useRef<HTMLInputElement>(null);
  yearRef.current = year;
  const integerYear = Math.floor(year),
    count = cities.filter((c) => visibleAt(c, integerYear)).length,
    activeChapter = chapter === null ? null : chapters[chapter],
    activeStop = activeChapter?.stops[stop];
  const era =
    integerYear < 1000
      ? 'ПЕРВЫЕ ПОСЕЛЕНИЯ'
      : integerYear < 1500
        ? 'СРЕДНЕВЕКОВЫЕ ЦЕНТРЫ'
        : integerYear < 1800
          ? 'ДАЛЬШЕ НА ВОСТОК'
          : integerYear < 1900
            ? 'ВЕК БОЛЬШОГО РОСТА'
            : 'ГОРОДА НОВОЙ ЭПОХИ';
  const results = useMemo(
    () =>
      query
        ? cities
            .filter((c) =>
              normalize(c.name + ' ' + c.region).includes(normalize(query)),
            )
            .sort(
              (a, b) =>
                Number(normalize(b.name) === normalize(query)) -
                Number(normalize(a.name) === normalize(query)),
            )
            .slice(0, 8)
        : [],
    [query, cities],
  );
  const listResults = useMemo(
    () =>
      cities.filter((c) =>
        normalize(c.name + ' ' + c.region).includes(normalize(listQuery)),
      ),
    [listQuery, cities],
  );
  const chooseCity = useCallback((c: City) => {
    setPlaying(false);
    setChapter(null);
    setSelected(c);
    setQuery('');
    setModal(null);
    if (c.coordinates)
      setMapAction({
        action: 'city',
        seq: Date.now(),
        coordinates: c.coordinates,
      });
  }, []);
  const stopTravel = useCallback(() => setPlaying(false), []);
  const failMap = useCallback(() => setMapFailed(true), []);
  useEffect(() => {
    const v = parseView(window.location.search, MIN, MAX, ids);
    setYear(v.year);
    setSelected(cities.find((c) => c.id === v.cityId) ?? null);
    setChapter(v.chapter);
    setStop(v.stop);
    initialCamera.current = v.camera;
    setCamera(v.camera);
    setFlat(v.camera.pitch === 0);
    const mq = matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const change = () => setReduced(mq.matches);
    mq.addEventListener('change', change);
    setHydrated(true);
    return () => mq.removeEventListener('change', change);
  }, [cities, MIN, MAX, ids]);
  useEffect(() => {
    if (!hydrated) return;
    const t = setTimeout(() => {
      history.replaceState(
        null,
        '',
        serializeView({
          year: integerYear,
          cityId: selected?.id ?? null,
          chapter,
          stop,
          camera,
        }),
      );
    }, 200);
    return () => clearTimeout(t);
  }, [integerYear, selected, chapter, stop, camera, hydrated]);
  const goStop = useCallback(
    (ch: number, index: number, play = true) => {
      const def = chapters[ch].stops[index];
      const c = cities.find((c) => c.name === def.city)!;
      setChapter(ch);
      setStop(index);
      setYear(def.year);
      setSelected(c);
      setPlaying(play);
      setQuery('');
      if (c.coordinates)
        setMapAction({
          action: 'city',
          seq: Date.now(),
          coordinates: c.coordinates,
        });
    },
    [cities],
  );
  function nextStop() {
    if (chapter === null) return;
    if (stop < 2) goStop(chapter, stop + 1, playing);
    else if (chapter < 4) goStop(chapter + 1, 0, playing);
    else {
      setPlaying(false);
      setChapter(null);
      setSelected(null);
    }
  }
  function explore() {
    setChapter(null);
    setPlaying(false);
    setSelected(null);
    setMapAction({ action: 'home', seq: Date.now() });
  }
  useEffect(() => {
    if (!playing) return;
    if (chapter !== null) {
      const c = chapters[chapter];
      const target = stop < 2 ? c.stops[stop + 1].year : c.stops[stop].year;
      const from = yearRef.current;
      const begin = performance.now();
      const duration = 8000 / speed;
      const id = setInterval(() => {
        const t = Math.min(1, (performance.now() - begin) / duration);
        setYear(from + (target - from) * t);
        if (t >= 1) {
          clearInterval(id);
          if (stop < 2) goStop(chapter, stop + 1, true);
          else if (chapter < 4) goStop(chapter + 1, 0, true);
          else setPlaying(false);
        }
      }, 100);
      return () => clearInterval(id);
    }
    let last = performance.now();
    const id = setInterval(() => {
      const now = performance.now(),
        delta = (now - last) / 1000;
      last = now;
      setYear((y) => {
        const n = Math.min(MAX, y + delta * 45 * speed);
        if (n === MAX) setPlaying(false);
        return n;
      });
    }, 100);
    return () => clearInterval(id);
  }, [playing, chapter, stop, speed, goStop, MAX]);
  function togglePlay() {
    if (!playing && integerYear >= MAX && chapter === null) setYear(MIN);
    setPlaying((p) => !p);
  }
  function changeYear(n: number) {
    if (!Number.isFinite(n)) return;
    setYear(Math.max(MIN, Math.min(MAX, n)));
    setPlaying(false);
    setChapter(null);
  }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.key === 'Escape') {
        setModal(null);
        setQuery('');
        setSelected(null);
        setPlaying(false);
        return;
      }
      if (['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON', 'A'].includes(tag) || modal)
        return;
      if (e.code === 'Space') {
        e.preventDefault();
        setPlaying((p) => !p);
      }
      if (e.key === '/') {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [modal]);
  useEffect(() => {
    if (!modal) return;
    const previous = document.activeElement as HTMLElement;
    const el = modalRef.current;
    el?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !el) return;
      const nodes = [
        ...el.querySelectorAll<HTMLElement>(
          'button,a,input,select,[tabindex="0"]',
        ),
      ];
      const first = nodes[0],
        last = nodes.at(-1);
      if (
        e.shiftKey &&
        (document.activeElement === first || document.activeElement === el)
      ) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    };
    el?.addEventListener('keydown', onKey);
    return () => {
      el?.removeEventListener('keydown', onKey);
      previous?.focus();
    };
  }, [modal]);
  async function share() {
    try {
      const url =
        window.location.origin +
        window.location.pathname +
        serializeView({
          year: integerYear,
          cityId: selected?.id ?? null,
          chapter,
          stop,
          camera,
        });
      history.replaceState(null, '', url);
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setShareError(true);
    }
  }
  useEffect(() => {
    const context = (
      document as Document & {
        modelContext?: {
          registerTool: (
            tool: unknown,
            options: { signal: AbortSignal },
          ) => void | Promise<void>;
        };
      }
    ).modelContext;
    if (!context) return;
    const life = new AbortController();
    Promise.resolve(
      context.registerTool(
        {
          name: 'explore_city_at_year',
          title: 'Открыть город в выбранном году',
          description:
            'Найти город атласа по точному названию или идентификатору и открыть его карточку на выбранном году.',
          inputSchema: {
            type: 'object',
            properties: {
              city: { type: 'string' },
              year: { type: 'integer', minimum: MIN, maximum: MAX },
            },
            required: ['city', 'year'],
            additionalProperties: false,
          },
          annotations: { readOnlyHint: false, untrustedContentHint: true },
          execute: async (input: unknown) => {
            const a = input as { city?: unknown; year?: unknown };
            if (
              typeof a?.city !== 'string' ||
              typeof a.year !== 'number' ||
              !Number.isInteger(a.year) ||
              a.year < MIN ||
              a.year > MAX
            )
              throw Error('Нужны название города и допустимый целый год.');
            const found = cities.filter(
              (c) =>
                c.id === a.city ||
                normalize(c.name) === normalize(a.city as string),
            );
            if (found.length !== 1)
              throw Error(
                found.length
                  ? 'Название неоднозначно. Укажите идентификатор.'
                  : 'Город не найден.',
              );
            chooseCity(found[0]);
            setYear(a.year);
            await new Promise<void>((resolve) =>
              requestAnimationFrame(() => resolve()),
            );
            return {
              city: found[0].name,
              id: found[0].id,
              year: a.year,
              population: populationAt(found[0], a.year),
            };
          },
        },
        { signal: life.signal },
      ),
    ).catch(() => {});
    return () => life.abort();
  }, [chooseCity, cities, MIN, MAX]);
  const selectedPopulation = selected
    ? populationAt(selected, integerYear)
    : null;
  return (
    <main className={'atlas' + (activeChapter ? ' travelling' : '')}>
      {hydrated && (
        <AtlasMap
          cities={cities}
          year={year}
          flat={flat}
          selected={selected}
          onSelect={chooseCity}
          action={mapAction}
          initialCamera={initialCamera.current}
          onCamera={setCamera}
          onInteract={stopTravel}
          period={period}
          reduced={reduced}
          onFailure={failMap}
        />
      )}
      <div className="map-vignette" />
      <header className="topbar">
        <a className="brand" href="/" aria-label="Города во времени — начало">
          <span className="brand-icon">
            <Compass size={23} />
          </span>
          <span>
            Города<span className="brand-light"> во времени</span>
            <small>ИНТЕРАКТИВНЫЙ АТЛАС</small>
          </span>
        </a>
        <nav aria-label="Режим атласа">
          <button
            className={chapter === null ? 'nav-active' : ''}
            onClick={explore}
          >
            Исследовать
          </button>
          <button
            className={chapter !== null ? 'nav-active' : ''}
            onClick={() => goStop(0, 0)}
          >
            Путешествие <ArrowUpRight size={14} />
          </button>
        </nav>
        <div className="header-actions">
          <button
            className="icon-button"
            aria-label={copied ? 'Ссылка скопирована' : 'Поделиться видом'}
            onClick={share}
          >
            {copied ? <Check size={17} /> : <Share2 size={17} />}
          </button>
          <button
            className="about-button"
            aria-label="Об атласе"
            onClick={() => {
              setPlaying(false);
              setModal('about');
            }}
          >
            <Info size={16} />
            <span>Об атласе</span>
          </button>
        </div>
      </header>
      {activeChapter && activeStop ? (
        <section className="story-panel">
          <button className="back-link" onClick={explore}>
            <ArrowLeft size={14} /> К свободной карте
          </button>
          <div className="eyebrow" style={{ color: activeChapter.color }}>
            ГЛАВА 0{chapter! + 1} / 05{' '}
            <span className="story-period">{activeChapter.period}</span>
          </div>
          <h1>{activeChapter.title}</h1>
          <p className="story-subtitle">{activeChapter.description}</p>
          <div className="story-separator" />
          <span className="stop-number">
            0{stop + 1} <span>/ 03</span>
          </span>
          <h2>{activeStop.city}</h2>
          <p className="story-text">{activeStop.text}</p>
          <a
            className="story-source"
            href={cities.find((c) => c.name === activeStop.city)!.url}
            target="_blank"
            rel="noreferrer"
          >
            Источник <ArrowUpRight size={12} />
          </a>
          <div className="story-actions">
            <button
              aria-label={
                playing ? 'Остановить путешествие' : 'Продолжить путешествие'
              }
              onClick={() => setPlaying(!playing)}
            >
              {playing ? <Pause size={16} /> : <Play size={16} />}{' '}
              {playing ? 'Пауза' : 'Продолжить'}
            </button>
            <button aria-label="Следующая остановка" onClick={nextStop}>
              <ArrowRight size={20} />
            </button>
          </div>
          <div className="chapter-progress">
            {chapters.map((c, i) => (
              <button
                key={c.title}
                className={i === chapter ? 'current' : ''}
                aria-label={'Глава ' + (i + 1) + ': ' + c.title}
                onClick={() => goStop(i, 0)}
                style={{ '--chapter-color': c.color } as React.CSSProperties}
              />
            ))}
          </div>
        </section>
      ) : (
        <section className="intro">
          <div className="eyebrow">
            <span className="live-dot" /> ИСТОРИЯ НА КАРТЕ
          </div>
          <h1>
            У каждого города
            <br />
            есть начало<span>.</span>
          </h1>
          <p>
            От первых поселений до миллионников.
            <br />
            Смотрите, как меняется карта времени.
          </p>
          <div className="search-wrap">
            <Search size={18} />
            <input
              ref={searchRef}
              aria-label="Найти город"
              placeholder="Найти свой город"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && results[0]) chooseCity(results[0]);
                if (e.key === 'Escape') setQuery('');
              }}
            />
            <kbd>/</kbd>
            {query && (
              <div className="search-results" aria-label="Результаты поиска">
                {results.map((c) => (
                  <button key={c.id} onClick={() => chooseCity(c)}>
                    <span>
                      {c.name}
                      <small>{c.region}</small>
                    </span>
                    <ArrowUpRight size={16} />
                  </button>
                ))}
                {!results.length && <p>Город не найден</p>}
              </div>
            )}
          </div>
          <button
            className="browse-cities"
            onClick={() => {
              setPlaying(false);
              setModal('list');
            }}
          >
            <List size={14} /> Все {formatNumber(cities.length)} городов
          </button>
        </section>
      )}
      <aside className="year-stat">
        <span className="eyebrow">КАРТА В</span>
        <div className={integerYear < 0 ? 'ancient-year' : ''}>
          {yearLabel(integerYear)}
        </div>
        <span className="year-rule" />
        <p>
          <b>{formatNumber(count)}</b> городов появились
        </p>
        <small>из {formatNumber(cities.length)} в каталоге</small>
        <span className="era-label">{era}</span>
      </aside>
      <div className="map-controls">
        <button
          aria-label="Приблизить"
          onClick={() => {
            stopTravel();
            setMapAction({ action: 'in', seq: Date.now() });
          }}
        >
          <Plus />
        </button>
        <button
          aria-label="Отдалить"
          onClick={() => {
            stopTravel();
            setMapAction({ action: 'out', seq: Date.now() });
          }}
        >
          <Minus />
        </button>
        <i />
        <button
          aria-label="Вернуть карту"
          onClick={() => {
            stopTravel();
            setMapAction({ action: 'home', seq: Date.now() });
          }}
        >
          <Compass />
        </button>
        <button
          aria-label={flat ? 'Включить объёмный вид' : 'Включить плоский вид'}
          className={!flat ? 'active' : ''}
          onClick={() => {
            stopTravel();
            setFlat(!flat);
          }}
        >
          {flat ? '2D' : '3D'}
        </button>
      </div>
      {!activeChapter && (
        <div className="journey-teaser">
          <span className="teaser-number">01—05</span>
          <div>
            <span>Пять глав. Тысяча историй.</span>
            <small>От первых огней до городов науки</small>
          </div>
          <button
            aria-label="Начать историческое путешествие"
            onClick={() => goStop(0, 0)}
          >
            <ArrowUpRight size={22} />
          </button>
        </div>
      )}
      <section className="timeline-panel" aria-label="Лента времени">
        <div className="timeline-top">
          <span className="eyebrow">ЛЕНТА ВРЕМЕНИ</span>
          <span className="timeline-hint">
            Двигайте время. Открывайте города.
          </span>
          <label className="year-entry">
            Год{' '}
            <input
              aria-label="Выбрать год"
              type="number"
              min={MIN}
              max={MAX}
              value={integerYear}
              onChange={(e) => changeYear(e.target.valueAsNumber)}
            />
          </label>
          <label className="period-select">
            <span>Новые за</span>
            <select
              aria-label="Подсветить новые города"
              value={period}
              onChange={(e) => setPeriod(+e.target.value)}
            >
              <option value="0">всё время</option>
              <option value="25">25 лет</option>
              <option value="50">50 лет</option>
              <option value="100">100 лет</option>
            </select>
          </label>
        </div>
        <div className="timeline-main">
          <button
            className="play-button"
            aria-label={playing ? 'Пауза' : 'Воспроизвести'}
            onClick={togglePlay}
          >
            {playing ? (
              <Pause size={22} />
            ) : (
              <Play size={22} fill="currentColor" />
            )}
          </button>
          <div className="timeline-track">
            <div className="histogram" aria-hidden="true">
              {bins.map((bin, i) => (
                <span
                  key={i}
                  style={{
                    height: Math.max(2, (bin.count / histogramMax) * 40),
                    background: bin.start <= year ? '#b9ab87' : '#344545',
                  }}
                />
              ))}
            </div>
            <input
              type="range"
              aria-label="Год на карте"
              min={MIN}
              max={MAX}
              value={integerYear}
              onChange={(e) => changeYear(+e.target.value)}
            />
            <div className="ticks">
              {[MIN, 1, 500, 1000, 1500, MAX]
                .filter((n, i, a) => a.indexOf(n) === i && n >= MIN && n <= MAX)
                .map((y) => (
                  <button
                    key={y}
                    style={{ left: ((y - MIN) / (MAX - MIN)) * 100 + '%' }}
                    onClick={() => changeYear(y)}
                  >
                    {yearLabel(y)}
                  </button>
                ))}
            </div>
          </div>
          <button
            className="speed"
            aria-label="Скорость воспроизведения"
            title="Изменить скорость"
            onClick={() =>
              setSpeed(speed === 4 ? 0.5 : speed === 0.5 ? 1 : speed * 2)
            }
          >
            {speed}×
          </button>
        </div>
        <footer>
          <button
            className="legend-button"
            onClick={() => {
              setPlaying(false);
              setModal('about');
            }}
          >
            <i className="legend-dot" /> Размер — население{' '}
            <span className="muted">·</span> <i className="legend-hollow" /> Нет
            данных <Info size={12} />
          </button>
          <button
            onClick={() => {
              setPlaying(false);
              setModal('about');
            }}
          >
            Данные и методология <ArrowUpRight size={12} />
          </button>
        </footer>
      </section>
      {selected && !activeChapter && (
        <aside
          className="city-card"
          aria-label={'Карточка города ' + selected.name}
        >
          <button
            className="close"
            aria-label="Закрыть карточку"
            onClick={() => setSelected(null)}
          >
            <X size={18} />
          </button>
          <div className="eyebrow">{selected.region}</div>
          <h2>{selected.name}</h2>
          <div className="city-date">
            <strong>
              {selected.founded === null
                ? 'Дата неизвестна'
                : yearLabel(selected.founded)}
            </strong>
            <a
              href={selected.dateSource ?? selected.url}
              target="_blank"
              rel="noreferrer"
            >
              {dateKinds[selected.dateKind]} <ArrowUpRight size={12} />
            </a>
          </div>
          <p className="status-year">
            Статус города: {selected.statusYear || 'не указан'}
          </p>
          <div className="population-number">
            {selectedPopulation!.value === null
              ? '—'
              : formatNumber(selectedPopulation!.value)}
            <small>{populationCaption(selected, integerYear)}</small>
          </div>
          {selected.founded !== null && selected.founded > integerYear && (
            <button
              className="jump-birth"
              onClick={() => changeYear(selected.founded!)}
            >
              Перейти к появлению <ArrowRight size={14} />
            </button>
          )}
          <PopulationChart city={selected} year={integerYear} />
          {selected.formerNames && (
            <p className="former-names">
              Прежние названия: {selected.formerNames}
            </p>
          )}
          {selected.notes.length > 0 && (
            <details>
              <summary>Особенности данных ({selected.notes.length})</summary>
              <p>
                Формулировка справочника: {selected.dateLabel || 'не указана'}
              </p>
              {selected.notes.map((n, i) => (
                <p key={i}>{n}</p>
              ))}
            </details>
          )}
          <details className="observation-sources">
            <summary>
              Наблюдения и источники ({selected.population.length})
            </summary>
            <div className="source-table">
              {selected.population.map((p) => (
                <a
                  key={p.year}
                  href={p.source}
                  target="_blank"
                  rel="noreferrer"
                >
                  <span>{p.year}</span>
                  <span>{formatNumber(p.value)}</span>
                  <ArrowUpRight size={12} />
                </a>
              ))}
            </div>
          </details>
          <a
            className="city-source"
            href={selected.url}
            target="_blank"
            rel="noreferrer"
          >
            История города <ArrowUpRight size={14} />
          </a>
        </aside>
      )}
      {mapFailed && (
        <button className="fallback-list" onClick={() => setModal('list')}>
          <List size={15} /> Открыть доступный список городов
        </button>
      )}
      {(copied || shareError) && (
        <output className="toast">
          {copied
            ? 'Ссылка на этот момент скопирована'
            : 'Ссылка сохранена в адресной строке — её можно скопировать вручную.'}
          {shareError && (
            <button
              aria-label="Закрыть уведомление"
              onClick={() => setShareError(false)}
            >
              <X size={14} />
            </button>
          )}
        </output>
      )}
      {modal && (
        <div className="modal-backdrop">
          <button
            className="modal-dismiss-area"
            aria-label="Закрыть фон окна"
            onClick={() => setModal(null)}
          />
          <dialog
            open
            ref={modalRef}
            tabIndex={-1}
            aria-modal="true"
            aria-labelledby="modal-title"
            className={'modal ' + (modal === 'list' ? 'list-modal' : '')}
          >
            <button
              className="close"
              onClick={() => setModal(null)}
              aria-label="Закрыть окно"
            >
              <X />
            </button>
            {modal === 'list' ? (
              <>
                <div className="eyebrow">КАТАЛОГ АТЛАСА</div>
                <h2 id="modal-title">У каждого города — своя история</h2>
                <input
                  className="list-search"
                  aria-label="Поиск в списке городов"
                  placeholder="Название или регион"
                  value={listQuery}
                  onChange={(e) => setListQuery(e.target.value)}
                />
                <p className="list-count">
                  Найдено {listResults.length} · даты без подтверждения отмечены
                  отдельно
                </p>
                <div className="cities-list">
                  {listResults.map((c) => (
                    <button key={c.id} onClick={() => chooseCity(c)}>
                      <span>
                        {c.name}
                        <small>{c.region}</small>
                      </span>
                      <span>
                        {c.founded === null
                          ? 'Дата неизвестна'
                          : yearLabel(c.founded)}{' '}
                        <ChevronRight size={14} />
                      </span>
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <>
                <div className="eyebrow">ОТКРЫТАЯ ИСТОРИЯ</div>
                <h2 id="modal-title">Как читать этот атлас</h2>
                <p>
                  Перед вами современные города из открытого справочника и
                  история их появления. Счётчик показывает города нашего
                  каталога, уже появившиеся к выбранному году, а не все города,
                  существовавшие в прошлом.
                </p>
                <h3>Свет, размер и время</h3>
                <p>
                  Площадь круга пропорциональна населению: радиус равен 0,48 ×
                  √(население / 1000) пикселей, с минимумом 3 и максимумом 48
                  пикселей для читаемости. На этих пределах пропорция
                  ограничена. Декоративное свечение не обозначает численность.
                  Полый маркер — население неизвестно.
                </p>
                <div className="color-legend">
                  {Object.entries(COLORS).map(([k, color], i) => (
                    <span key={k}>
                      <i style={{ background: color }} />
                      {
                        [
                          'До 1000',
                          '1000–1499',
                          '1500–1799',
                          '1800–1899',
                          'С 1900',
                        ][i]
                      }
                    </span>
                  ))}
                </div>
                <p>
                  Цвет означает эпоху появления. Импульс отмечает первые три
                  года; кольцо подсвечивает города выбранного периода. Площадь
                  карты и государственные границы не меняются вместе с годом.
                </p>
                <h3>Наблюдения и оценки</h3>
                <p>
                  Между сопоставимыми наблюдениями используется линейная
                  интерполяция с подписью «оценка». До первого наблюдения размер
                  неизвестен; после последнего сохраняются значение и его год.
                  При известных изменениях границ или резких скачках
                  интерполяция отключается. Разные оценки за один год исключены,
                  кроме однозначно датированных наблюдений переписи.
                </p>
                <p>
                  Даже плавный участок — приближение между источниками, а не
                  ежегодная перепись. Военные потери, миграция и изменение
                  состава территории могли происходить неравномерно. Население
                  городских округов не добавляется к населению города; строки с
                  отдельным охватом в Wikidata исключаются.
                </p>
                <h3>Полнота данных</h3>
                <div className="coverage-grid">
                  <div>
                    <strong>{formatNumber(coverage.total)}</strong>
                    <span>записей каталога</span>
                  </div>
                  <div>
                    <strong>{formatNumber(coverage.withDates)}</strong>
                    <span>с датой появления</span>
                  </div>
                  <div>
                    <strong>{formatNumber(coverage.withPopulation)}</strong>
                    <span>с населением</span>
                  </div>
                  <div>
                    <strong>{formatNumber(coverage.observations)}</strong>
                    <span>наблюдений</span>
                  </div>
                </div>
                <p>
                  Снимок источников: {coverage.snapshotDate}. Координаты есть у{' '}
                  {coverage.withCoordinates} городов. Без даты:{' '}
                  {coverage.missingDates.length}; без численности:{' '}
                  {coverage.missingPopulation.length}. Они остаются в поиске и
                  каталоге. Даты, уточнённые через Wikidata, отмечены в
                  карточках.
                </p>
                <a
                  className="text-link"
                  href="/coverage.json"
                  target="_blank"
                  rel="noreferrer"
                >
                  Полный отчёт импорта <ArrowUpRight size={14} />
                </a>
                <h3>Территориальный охват</h3>
                <p>
                  Состав повторяет две таблицы «Списка городов России», включая
                  города внутри городов федерального значения. Подложка Natural
                  Earth отражает собственные современные картографические
                  соглашения. В каталог источника включены города Крыма и
                  Севастополь; их принадлежность оспаривается Россией и
                  Украиной, большинство государств признаёт их территорией
                  Украины. Их присутствие в каталоге не означает признания
                  изменения границ. Исторические границы государств здесь не
                  реконструируются.
                </p>
                <h3>Источники и права</h3>
                <ul className="source-links">
                  <li>
                    <a
                      href="https://ru.wikipedia.org/wiki/Список_городов_России"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Википедия — каталог, даты и дополнения к населению ↗
                    </a>
                    <small>
                      CC BY-SA 4.0. Переработанный каталог распространяется на
                      тех же условиях.
                    </small>
                  </li>
                  <li>
                    <a
                      href="https://www.wikidata.org/wiki/Wikidata:Licensing"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Wikidata — координаты, даты, наблюдения населения ↗
                    </a>
                    <small>
                      CC0. Ссылки на отдельные наблюдения доступны в карточках.
                    </small>
                  </li>
                  <li>
                    <a
                      href="https://rosstat.gov.ru/vpn/2020/Tom1_Chislennost_i_razmeshchenie_naseleniya"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Росстат — перепись 2021 года ↗
                    </a>
                  </li>
                  <li>
                    <a
                      href="https://www.rosstat.gov.ru/free_doc/new_site/perepis2010/croc/vol1.html"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Росстат — перепись 2010 года ↗
                    </a>
                  </li>
                  <li>
                    <a
                      href="https://www.demoscope.ru/weekly/ssp/census.php?cy=8"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Демоскоп — архив исторических переписей ↗
                    </a>
                    <small>
                      Переписи доступны через ссылки в записях Wikidata; полные
                      сборники не перепубликуются.
                    </small>
                  </li>
                  <li>
                    <a
                      href="https://www.naturalearthdata.com/about/terms-of-use/"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Natural Earth — география, public domain ↗
                    </a>
                  </li>
                  <li>
                    <a
                      href="https://github.com/shyr1punk/city-visualization"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Исходный проект shyr1punk/city-visualization ↗
                    </a>
                  </li>
                </ul>
                <p className="keyboard-note">
                  Клавиатура: пробел — воспроизведение, / — поиск, Esc —
                  закрыть. Стрелки изменяют выбранный ползунок. Настройка
                  уменьшения движения отключает полёты и пульсацию.
                </p>
              </>
            )}
          </dialog>
        </div>
      )}
    </main>
  );
}
