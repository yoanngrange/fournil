// Fournil — reference logic extracted from the mockups (design/Zoom.dc.html).
// Plain functions, no dependencies. Port them into src/; keep behaviour identical.

/** Criteria shown in the sidebar. `dir: -1` means lower is better. */
export const CRITERIA = [
  { key: 'pop',        label: 'Population',                         dir: 1,  weighted: false },
  { key: 'per_bakery', label: 'Habitants par boulangerie',          dir: 1,  weighted: true, defaultWeight: 3 },
  { key: 'income',     label: 'Revenu médian',                      dir: 1,  weighted: true, defaultWeight: 2 },
  { key: 'growth',     label: 'Évolution de la population',         dir: 1,  weighted: true, defaultWeight: 2 },
  { key: 'crime',      label: 'Taux de délinquance',                dir: -1, weighted: true, defaultWeight: 1 },
  { key: 'sell_soon',  label: 'Boulangeries à reprendre bientôt',   dir: 1,  weighted: true, defaultWeight: 1 },
];

/**
 * Percentile rank of v within a sorted array (ties get the mid-rank), 0..1.
 * In production this runs in the pipeline over ALL French communes; the client
 * receives pct as ints 0..1000 already inverted for dir = -1.
 */
export function percentile(sortedValues, v) {
  const a = sortedValues;
  let lo = 0, hi = a.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (a[mid] < v) lo = mid + 1; else hi = mid; }
  let eq = lo; while (eq < a.length && a[eq] === v) eq++;
  return a.length > 1 ? (lo + (eq - lo) / 2) / (a.length - 1) : 0.5;
}

/**
 * Score 0..100 from national percentiles and user weights.
 * pct: { per_bakery: 0..1000 | null, ... }, weights: { per_bakery: 0..3, ... }
 * Criteria with a null value are skipped and the remaining weights re-normalised.
 */
export function score(pct, weights) {
  let num = 0, den = 0;
  for (const c of CRITERIA) {
    if (!c.weighted) continue;
    const w = weights[c.key] || 0, p = pct[c.key];
    if (!w || p == null) continue;
    num += w * (p / 1000); den += w;
  }
  return den ? Math.round(100 * num / den) : null;
}

export const category = (s) => (s == null ? 'unknown' : s >= 60 ? 'go' : s >= 40 ? 'maybe' : 'avoid');

export const FILL = (s) =>
  s == null ? '#D9D2C5' : s >= 75 ? '#4D9221' : s >= 60 ? '#7FBC41' : s >= 40 ? '#ECEAE1' : s >= 25 ? '#DE77AE' : '#C51B7D';

/** Slider bounds = min/max of the raw values of communes currently on screen. */
export function visibleRanges(visibleCommunes) {
  const out = {};
  for (const c of CRITERIA) {
    const vals = visibleCommunes.map((x) => x.v[c.key]).filter((v) => v != null);
    out[c.key] = vals.length ? { min: Math.min(...vals), max: Math.max(...vals) } : null;
  }
  return out;
}

/** filters: { key: {lo, hi} } in real units. A commune passes if every active filter contains its value. */
export const passesFilters = (commune, filters) =>
  Object.entries(filters).every(([k, f]) => commune.v[k] == null || (commune.v[k] >= f.lo && commune.v[k] <= f.hi));

/** Haversine distance in km between {lat, lon} points. */
export function km(a, b) {
  const R = 6371, rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad, dLon = (b.lon - a.lon) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** Delivery mode "Distance": every commune whose centroid is within radiusKm of the bakehouse. */
export const withinDistance = (base, communes, radiusKm) => communes.filter((c) => km(base, c) <= radiusKm);

/**
 * Delivery mode "Communes voisines": grow ONE connected block of touching communes,
 * starting at the bakehouse and always adding the bordering commune nearest to it.
 * byCode: { code: commune }, adjacency: { code: [neighbour codes] }
 */
export function contiguousBlock(baseCode, n, byCode, adjacency) {
  const base = byCode[baseCode];
  const area = new Set([baseCode]);
  while (area.size < n) {
    let best = null, bestD = Infinity;
    for (const code of area) {
      for (const nb of adjacency[code] || []) {
        if (area.has(nb) || !byCode[nb]) continue;
        const d = km(base, byCode[nb]);
        if (d < bestD) { bestD = d; best = nb; }
      }
    }
    if (!best) break; // island or end of data
    area.add(best);
  }
  return area;
}

/** Reach stats shown in the sidebar for a set of communes. */
export function reach(codes, byCode, baseCode) {
  const base = byCode[baseCode];
  let n = 0, noBakery = 0, pop = 0, popNoBakery = 0, furthestKm = 0;
  for (const code of codes) {
    const c = byCode[code]; n++; pop += c.pop;
    if (c.bakeries === 0) { noBakery++; popNoBakery += c.pop; }
    furthestKm = Math.max(furthestKm, km(base, c));
  }
  return { n, noBakery, pop, popNoBakery, furthestKm };
}
