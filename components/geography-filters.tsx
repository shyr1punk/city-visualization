'use client';
import { useMemo, useState, useRef } from 'react';
import type { City } from '../lib/atlas';
import {
  CONTINENTS,
  availableCountries,
  type Geography,
} from '../lib/geography';
import { Checkbox } from './ui/checkbox';
import { Switch } from './ui/switch';
export default function GeographyFilters({
  cities,
  countries,
  value,
  onChange,
}: {
  cities: City[];
  countries: Record<string, string>;
  value: Geography;
  onChange: (g: Geography) => void;
}) {
  const panel = useRef<HTMLDetailsElement>(null);
  const [search, setSearch] = useState('');
  const allowed = useMemo(
    () => availableCountries(cities, value.continents),
    [cities, value.continents],
  );
  const toggle = (list: string[], id: string) =>
    list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
  const count = value.countries.length + value.continents.length;
  return (
    <details className="geo-filters" ref={panel}>
      <summary>
        Континенты и страны{' '}
        <span>{count ? `Выбрано: ${count}` : 'Весь мир'}</span>
      </summary>
      <div className="geo-panel">
        <div className="geo-heading">
          <strong>География</strong>
          <button
            aria-label="Закрыть фильтры"
            onClick={() => {
              if (panel.current) panel.current.open = false;
            }}
          >
            Закрыть
          </button>
          <button
            onClick={() => {
              setSearch('');
              onChange({ continents: [], countries: [], showUndated: false });
            }}
          >
            Сбросить
          </button>
        </div>
        <fieldset>
          <legend>Континенты</legend>
          <div className="continent-options">
            {Object.entries(CONTINENTS).map(([id, name]) => (
              <label key={id} htmlFor={'continent-' + id}>
                <Checkbox
                  id={'continent-' + id}
                  checked={value.continents.includes(id)}
                  onCheckedChange={() =>
                    onChange({
                      ...value,
                      continents: toggle(value.continents, id),
                    })
                  }
                />
                {name}
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>Страны</legend>
          {value.countries.length > 0 && (
            <p className="geo-selection">
              {value.countries.map((id) => countries[id] ?? id).join(', ')}
            </p>
          )}
          <input
            aria-label="Найти страну"
            placeholder="Найти страну"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="country-options">
            {Object.entries(countries)
              .filter(
                ([id, name]) =>
                  allowed.has(id) &&
                  name
                    .toLocaleLowerCase('ru')
                    .includes(search.toLocaleLowerCase('ru')),
              )
              .sort((a, b) => a[1].localeCompare(b[1], 'ru'))
              .map(([id, name]) => (
                <label key={id} htmlFor={'country-' + id}>
                  <Checkbox
                    id={'country-' + id}
                    checked={value.countries.includes(id)}
                    onCheckedChange={() =>
                      onChange({
                        ...value,
                        countries: toggle(value.countries, id),
                      })
                    }
                  />
                  {name}
                </label>
              ))}
          </div>
        </fieldset>
        <label className="undated-switch" htmlFor="show-undated">
          <Switch
            id="show-undated"
            checked={value.showUndated}
            onCheckedChange={(showUndated) =>
              onChange({ ...value, showUndated })
            }
          />
          Показать города без даты
        </label>
      </div>
    </details>
  );
}
