/* oxlint-disable react/react-compiler -- External shard loading lifecycle explicitly manages pending and error state. */
'use client';
import { useEffect, useState } from 'react';
import type { City } from '../lib/atlas';
const cache = new Map<string, City[]>();
const pending = new Map<string, Promise<City[]>>();
function load(key: string) {
  if (cache.has(key)) return Promise.resolve(cache.get(key)!);
  if (!pending.has(key)) {
    const promise = fetch(import.meta.env.BASE_URL + `catalog/${key}.json`)
      .then(async (r) => {
        if (!r.ok) throw Error('Не удалось загрузить данные городов');
        const rows = (await r.json()) as City[];
        if (!Array.isArray(rows)) throw Error('Некорректные данные');
        cache.set(key, rows);
        return rows;
      })
      .finally(() => pending.delete(key));
    pending.set(key, promise);
  }
  return pending.get(key)!;
}
export function useCityDetails(keys: string[]) {
  const signature = [...new Set(keys)].sort().join(',');
  const [attempt, retry] = useState(0);
  const [state, setState] = useState<{
    signature: string;
    details: Map<string, City>;
    loading: boolean;
    error: boolean;
  }>({ signature: '', details: new Map(), loading: true, error: false });
  useEffect(() => {
    let active = true;
    const needed = signature.split(',').filter(Boolean);
    setState((s) => ({ ...s, signature, loading: true, error: false }));
    const queue = needed.filter((k) => !cache.has(k));
    async function worker() {
      while (active && queue.length) await load(queue.shift()!);
    }
    Promise.all(Array.from({ length: Math.min(4, queue.length) }, worker))
      .then(() => {
        if (active)
          setState({
            signature,
            details: new Map(
              needed.flatMap((k) => cache.get(k) ?? []).map((c) => [c.id, c]),
            ),
            loading: false,
            error: false,
          });
      })
      .catch(() => {
        if (active)
          setState((s) => ({ ...s, signature, loading: false, error: true }));
      });
    return () => {
      active = false;
    };
  }, [signature, attempt]);
  return {
    ...state,
    loading: state.loading || state.signature !== signature,
    retry: () => retry((n) => n + 1),
  };
}
