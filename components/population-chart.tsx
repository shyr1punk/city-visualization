/* oxlint-disable jsx-a11y/prefer-tag-over-role -- An inline SVG chart requires an accessible image role and label. */
import { City, formatNumber } from '../lib/atlas';
export default function PopulationChart({
  city,
  year,
}: {
  city: City;
  year: number;
}) {
  const ps = city.population;
  if (!ps.length)
    return <p className="chart-empty">Датированных наблюдений пока нет.</p>;
  const lo = ps[0].year,
    hi = ps.at(-1)!.year,
    max = Math.max(...ps.map((p) => p.value)),
    x = (y: number) => 10 + ((y - lo) / Math.max(1, hi - lo)) * 270,
    y = (n: number) => 78 - (n / max) * 65;
  const groups: (typeof ps)[] = [];
  for (const p of ps) {
    if (!groups.length || p.segment !== groups.at(-1)!.at(-1)!.segment)
      groups.push([]);
    groups.at(-1)!.push(p);
  }
  return (
    <div className="population-chart">
      <div className="chart-header">
        <span>НАСЕЛЕНИЕ ВО ВРЕМЕНИ</span>
        <span>{formatNumber(max)}</span>
      </div>
      <svg
        viewBox="0 0 290 95"
        role="img"
        aria-label={`Наблюдения населения ${city.name} с ${lo} по ${hi} год`}
      >
        <line x1="10" x2="280" y1="78" y2="78" stroke="#fff2" />
        {groups.map((g, i) => (
          <polyline
            key={i}
            points={g.map((p) => `${x(p.year)},${y(p.value)}`).join(' ')}
            fill="none"
            stroke="#e9cd96"
            strokeWidth="1.5"
          />
        ))}
        {ps.map((p) => (
          <circle
            key={p.year}
            cx={x(p.year)}
            cy={y(p.value)}
            r="1.5"
            fill="#e9cd96"
          />
        ))}
        {year >= lo && year <= hi && (
          <line
            x1={x(year)}
            x2={x(year)}
            y1="5"
            y2="79"
            stroke="#c5d9d0"
            strokeDasharray="3 3"
          />
        )}
      </svg>
      <div className="chart-axis">
        <span>{lo}</span>
        <span>{hi}</span>
      </div>
    </div>
  );
}
