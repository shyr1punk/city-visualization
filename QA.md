# Проверка 9 сентября 2026

- Исправление drag: убран `Map.stop()` из обработчиков начала ручного жеста, поскольку он сбрасывает активные обработчики MapLibre. В браузере проверены два противоположных перетаскивания на 250 px: карта переместилась полностью и вернулась практически в исходную точку (82 → −49.17 → 81.98°). Перетаскивание в путешествии переместило камеру и остановило год на 695; кнопка сменилась на «Продолжить путешествие».

- `npm run lint`: проверяется код приложения; неиспользуемые компоненты shadcn и исходный hook стартера исключены. React Compiler не включён; для явной синхронизации URL и жизненного цикла MapLibre отключено только правило совместимости с компилятором. Правила зависимостей hooks включены.
- `npm run typecheck`, `npm test`, `npm run build`: проходят. 11 тестов покрывают дату появления и перемотку назад, неизвестное население, рост/убыль, административные разрывы, площадь маркера, URL, все наблюдения, координаты и различение одноимённых городов.
- В браузере проверены поиск Москвы и карточка с численностью 1897 года, источниками и графиком; запуск и пауза путешествия; переход с Дербента на Великий Новгород; восстановление главы и года после перезагрузки; выбор современного года на ширине 390 px; отсутствие горизонтального переполнения.
- Производственный статический результат отдельно открыт через обычный HTTP-сервер. Реальная география, локальный MapLibre worker и маркеры загружаются. Это устраняет зависимость от dev-сервера и внешних картографических API. Проверены изменение года и переключение 2D/3D.
- Системная настройка уменьшения движения учитывается в коде; принудительная потеря WebGL-контекста и большой набор физических устройств не тестировались. При отказе движка остаются поиск, каталог и карточки.
- Дополнительный WebMCP-интерфейс зарегистрирован с ожидаемой схемой. Его вызов НЕ проверен: автоматическая проверка безопасности браузера отклонила тест после изменения контекста страницы. Обход не предпринимался. Это не требуется для обычной работы сайта.
- Данные: 1141 точный идентификатор и координаты; 1068 точных дат появления; 38457 наблюдений населения. Полный отчёт — `public/coverage.json`. Числовая полнота не гарантирует отсутствие исторических разночтений; они описаны в `DATA.md` и интерфейсе.

# Географические фильтры — 11 сентября 2026

- 25 тестов TypeScript и 10 тестов Python проверяют географические пересечения, сброс несовместимых стран, переход через 180°, старые и новые ссылки, неизвестные даты, импорт неполных записей, конфликты наблюдений и запрет импорта незавершённого снимка. Отдельная проверка сравнивает все прежние даты и ряды населения с сохранённым каталогом.
- На текущем каталоге 2573 записей: фильтр Европы ~1 мс, подготовка маркеров ~2 мс. На синтетическом наборе 100000 записей: ~4–5 мс и ~29–42 мс соответственно. Синтетические записи используются только при измерении, не входят в данные сайта. Это время вычисления в Node, а не замер частоты кадров MapLibre на телефоне.
- В браузере проверены выбор Европы, последующий выбор Беларуси и смена на Азию со снятием несовместимой страны. Счётчики и список меняются вместе. Переключатель неизвестных дат сохраняется как `undated=1`; исторический счётчик не меняется.
- Проверена панель на 390×844: все элементы доступны через прокрутку, отдельная кнопка закрывает фильтры. В глобальном виде подписи городов скрыты до приближения, чтобы не перекрывать друг друга.
- Проверка типов и линтер проходят. Статическая сборка успешно выполнена; предупреждение о размере пакета MapLibre сохраняется.
- Мировой снимок пока не завершён: актуальный флаг `worldComplete` находится в `public/coverage-summary.json`. Полный мировой охват и измерение на его реальных данных нельзя считать проверенными до завершения выгрузки.

## Settlement history update — 2026-09-21

- 30 TypeScript and 22 Python tests pass; typecheck, lint and static GitHub Pages build pass. The existing large MapLibre bundle warning remains.
- All 21,593 pre-change IDs and population year/value pairs survive in the 23,231-record catalog. The 51-record review cohort was checked against the pre-change population ranking; its hash, sources and unresolved questions are in `docs/history-review.md`.
- Repeated cached import is byte-identical (7.44 seconds in this run). Unit coverage includes fresh/repeated overrides, unclassified administrative inception, conflicting mentions, century precision, ancient reviewed dates, status transitions, census-only neutral markers and no fabricated population.
- Current catalog: Europe filtering 3.8 ms, 7,243 marker features 5.2 ms. Synthetic 100,000-record stress case: filtering 14.8 ms, 34,199 markers 20.7 ms. These are local computation timings, not network loading or GPU frame-rate measurements.
- Browser checked the production build with the `/city-visualization/` base path: Hong Kong visible in 1900 with settlement 1550, population beginning 1961 and unknown urban status; Shenzhen 1978/1979 switches the status description; no MapLibre console errors in the initial view. Desktop world view and 390×844 mobile card inspected. Main dates fit; supporting history is expandable; marker hit targets remain independent of drawn size.
- MapLibre interpolates clamped radius endpoints between zoom 2 and 6. At a minimum/maximum clamp crossover this differs slightly from evaluating the scalar formula at every intermediate zoom; both endpoints and the requested bounds are exact. Unknown population stays 3 px.
- This is an incomplete world download. Historical review is limited to the fixed 51-record cohort; unknown dates are intentional and are not evidence that a settlement did not exist.
- Browser regression found and fixed: initializing globe projection must not reset a saved city-scale URL to zoom 1.3. Projection changes still reframe intentionally; initial loading preserves the supplied camera.
