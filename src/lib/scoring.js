// Scoring, filters and colours. Ported from design/logic-reference.js; keep behaviour identical.

/** Criteria shown in the sidebar. `dir: -1` means lower is better. sell_soon waits for RNE data (M6). */
export const CRITERIA = [
  { key: 'pop', dir: 1, weighted: false },
  { key: 'per_bakery', dir: 1, weighted: true, defaultWeight: 3 },
  { key: 'income', dir: 1, weighted: true, defaultWeight: 2 },
  { key: 'growth', dir: 1, weighted: true, defaultWeight: 2 },
  { key: 'crime', dir: -1, weighted: true, defaultWeight: 1 },
];

export const DEFAULT_WEIGHTS = Object.fromEntries(
  CRITERIA.filter((c) => c.weighted).map((c) => [c.key, c.defaultWeight]),
);

/**
 * Score 0..100 from national percentiles (0..1000, already inverted) and user weights (0..3).
 * Criteria with a null value are skipped and the remaining weights re-normalised.
 */
export function score(pct, weights) {
  let num = 0;
  let den = 0;
  for (const c of CRITERIA) {
    if (!c.weighted) continue;
    const w = weights[c.key] || 0;
    const p = pct[c.key];
    if (!w || p == null) continue;
    num += w * (p / 1000);
    den += w;
  }
  return den ? Math.round((100 * num) / den) : null;
}

export const category = (s) => (s == null ? 'unknown' : s >= 60 ? 'go' : s >= 40 ? 'maybe' : 'avoid');

export const BIN_COLOURS = {
  top: '#4D9221', // ≥ 75
  go: '#7FBC41', // 60–74
  maybe: '#ECEAE1', // 40–59
  avoid: '#DE77AE', // 25–39
  worst: '#C51B7D', // < 25
  out: '#D9D2C5', // filtered out
  unknown: '#D9D2C5',
};

export const bin = (s) =>
  s == null ? 'unknown' : s >= 75 ? 'top' : s >= 60 ? 'go' : s >= 40 ? 'maybe' : s >= 25 ? 'avoid' : 'worst';

/** Slider bounds = min/max of the raw values of the given communes. */
export function visibleRanges(communes) {
  const out = {};
  for (const c of CRITERIA) {
    let min = Infinity;
    let max = -Infinity;
    for (const x of communes) {
      const v = x.v[c.key];
      if (v == null) continue;
      if (v < min) min = v;
      if (v > max) max = v;
    }
    out[c.key] = min <= max ? { min, max } : null;
  }
  return out;
}

/**
 * filters: { key: {lo, hi} } in real units; a null bound is open (the handle sits at the end of the
 * slider, so panning to communes beyond it does not filter them out).
 * A commune passes if every active filter contains its value; a missing value never filters out.
 */
export const passesFilters = (commune, filters) =>
  Object.entries(filters).every(([k, f]) => {
    const v = commune.v[k];
    return v == null || ((f.lo == null || v >= f.lo) && (f.hi == null || v <= f.hi));
  });

/** Haversine distance in km between {lat, lon} points. */
export function km(a, b) {
  const R = 6371;
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLon = (b.lon - a.lon) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
