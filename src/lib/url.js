// Shareable state in the query string: weights, filters and selected commune.
// The map position lives in the hash (MapLibre `hash` option).
import { CRITERIA, DEFAULT_WEIGHTS } from './scoring.js';

const WEIGHTED = CRITERIA.filter((c) => c.weighted).map((c) => c.key);
const KEYS = CRITERIA.map((c) => c.key);

export function readState() {
  const q = new URLSearchParams(location.search);
  const weights = { ...DEFAULT_WEIGHTS };
  const w = q.get('p');
  if (w && /^[0-3](\.[0-3])*$/.test(w)) {
    w.split('.').forEach((v, i) => {
      if (WEIGHTED[i]) weights[WEIGHTED[i]] = Number(v);
    });
  }
  const filters = {};
  for (const part of (q.get('f') || '').split(',')) {
    const [k, lo, hi] = part.split(':');
    const num = (s) => (s === '' || s == null || !Number.isFinite(+s) ? null : +s);
    if (KEYS.includes(k) && (num(lo) != null || num(hi) != null)) {
      filters[k] = { lo: num(lo), hi: num(hi) };
    }
  }
  const c = q.get('c');
  return { weights, filters, sel: c && /^[0-9AB]{5}$/.test(c) ? c : null };
}

export function writeState({ weights, filters, sel }) {
  const q = new URLSearchParams();
  const w = WEIGHTED.map((k) => weights[k]).join('.');
  if (w !== WEIGHTED.map((k) => DEFAULT_WEIGHTS[k]).join('.')) q.set('p', w);
  const f = Object.entries(filters)
    .map(([k, { lo, hi }]) => `${k}:${lo == null ? '' : +lo.toFixed(2)}:${hi == null ? '' : +hi.toFixed(2)}`)
    .join(',');
  if (f) q.set('f', f);
  if (sel) q.set('c', sel);
  const s = q.toString();
  history.replaceState(null, '', `${location.pathname}${s ? `?${s.replace(/%3A/g, ':').replace(/%2C/g, ',')}` : ''}${location.hash}`);
}
