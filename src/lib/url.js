// Shareable state in the query string: filters, selected commune and delivery mode.
// The map position lives in the hash (MapLibre `hash` option).
import { CRITERIA } from './scoring.js';
import { COUNT, RADIUS } from './delivery.js';

const KEYS = CRITERIA.map((c) => c.key);

export function readState() {
  const q = new URLSearchParams(location.search);
  const filters = {};
  for (const part of (q.get('f') || '').split(',')) {
    const [k, lo, hi] = part.split(':');
    const num = (s) => (s === '' || s == null || !Number.isFinite(+s) ? null : +s);
    if (KEYS.includes(k) && (num(lo) != null || num(hi) != null)) {
      filters[k] = { lo: num(lo), hi: num(hi) };
    }
  }
  const c = q.get('c');
  const code = (v) => (v && /^[0-9AB]{5}$/.test(v) ? v : null);
  const clamp = (v, { min, max, default: d }) => (Number.isFinite(+v) && v !== null ? Math.min(max, Math.max(min, +v)) : d);
  return {
    filters,
    sel: code(c),
    delivery: {
      on: q.get('d') === '1',
      cover: q.get('cv') === 'n' ? 'n' : 'km',
      radius: clamp(q.get('r'), RADIUS),
      count: clamp(q.get('nb'), COUNT),
      base: code(q.get('b')),
    },
  };
}

export function writeState({ filters, sel, delivery }) {
  const q = new URLSearchParams();
  const f = Object.entries(filters)
    .map(([k, { lo, hi }]) => `${k}:${lo == null ? '' : +lo.toFixed(2)}:${hi == null ? '' : +hi.toFixed(2)}`)
    .join(',');
  if (f) q.set('f', f);
  if (sel) q.set('c', sel);
  if (delivery?.on) {
    q.set('d', '1');
    q.set('cv', delivery.cover);
    q.set(delivery.cover === 'n' ? 'nb' : 'r', String(delivery.cover === 'n' ? delivery.count : delivery.radius));
    if (delivery.base) q.set('b', delivery.base);
  }
  const s = q.toString();
  history.replaceState(null, '', `${location.pathname}${s ? `?${s.replace(/%3A/g, ':').replace(/%2C/g, ',')}` : ''}${location.hash}`);
}
