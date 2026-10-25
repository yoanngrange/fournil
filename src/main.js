import t from './i18n/fr.js';
import { BIN_COLOURS, WEIGHTS, bin, category, passesFilters, score, visibleRanges } from './lib/scoring.js';
import { fmtInt, tr } from './lib/format.js';
import { readState, writeState } from './lib/url.js';
import { DEP_SCALE, createMap } from './map.js';
import { createSidebar } from './sidebar.js';
import { createCard } from './card.js';
import { createSearch } from './search.js';

const TOP_N = 8;

// Static UI copy from src/i18n/fr.js.
for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = t[el.dataset.i18n];
for (const el of document.querySelectorAll('[data-i18n-html]')) el.innerHTML = t[el.dataset.i18nHtml];
for (const el of document.querySelectorAll('[data-i18n-aria-label]')) el.setAttribute('aria-label', t[el.dataset.i18nAriaLabel]);
for (const el of document.querySelectorAll('[data-i18n-placeholder]')) el.placeholder = t[el.dataset.i18nPlaceholder];

const status = document.getElementById('status');
status.textContent = t['app.loading'];

const getJSON = (path) => fetch(`data/${path}`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(path))));

/** Columnar index -> one object per commune. */
function rows(index) {
  return index.code.map((code, i) => {
    const v = { pop: index.pop[i] };
    const pct = {};
    for (const k of Object.keys(index.v)) {
      v[k] = index.v[k][i];
      pct[k] = index.pct[k][i];
    }
    return { code, name: index.name[i], dep: index.dep[i], lat: index.lat[i], lon: index.lon[i], pop: index.pop[i], bakeries: index.bakeries[i], v, pct };
  });
}

// Metropolitan France + Corsica.
const FRANCE = [[-5.3, 41.3], [9.7, 51.2]];

async function start() {
  const [meta, index, departements, fonds] = await Promise.all([
    getJSON('meta.json'),
    getJSON('communes-index.json'),
    getJSON('departements.geojson'),
    getJSON('fonds.json'),
  ]);
  const communes = rows(index);
  const byCode = new Map(communes.map((c) => [c.code, c]));
  const depNames = Object.fromEntries(departements.features.map((f) => [f.properties.code, f.properties.name]));
  const exported = new Set(meta.departements);
  const byDep = new Map();
  for (const c of communes) {
    if (!byDep.has(c.dep)) byDep.set(c.dep, []);
    byDep.get(c.dep).push(c);
  }

  const state = readState();
  const view = new Map(); // code -> {score, cat, ok, fill}
  const depView = new Map(); // dep -> {go, n, q}

  const card = createCard(document.getElementById('card'), { meta, fonds, onClose: () => select(null) });
  const tooltip = document.getElementById('tooltip');

  const mapApi = createMap({
    container: 'map',
    communes,
    departements,
    france: FRANCE,
    loadGeo: (dep) => (exported.has(dep) ? getJSON(`geo/${dep}.geojson`) : Promise.reject(new Error(dep))),
    locale: {
      'NavigationControl.ZoomIn': t['map.zoomIn'],
      'NavigationControl.ZoomOut': t['map.zoomOut'],
      'NavigationControl.ResetBearing': t['map.resetBearing'],
    },
    on: {
      hoverCommune: showTooltip,
      hoverDep: showDepTooltip,
      clickCommune: (code) => select(code === state.sel ? null : code),
      geoLoaded: () => {
        paintCommunes();
        mapApi.select(state.sel);
      },
      move: refreshPanel,
    },
  });

  const sidebar = createSidebar(document.getElementById('sidebar'), {
    getState: () => state,
    setFilter(key, f) {
      if (f.lo == null && f.hi == null) delete state.filters[key];
      else state.filters[key] = f;
      recompute();
    },
    resetFilters() {
      state.filters = {};
      recompute();
    },
    pick: (id) => (byCode.has(id) ? select(id, { fly: true, focus: true }) : mapApi.fitDep(id)),
  });

  createSearch(
    document.getElementById('search'),
    document.getElementById('search-results'),
    document.getElementById('search-status'),
    communes,
    (code) => select(code, { fly: true, focus: true }),
  );

  document.getElementById('zoom-in').addEventListener('click', mapApi.zoomIn);
  document.getElementById('zoom-out').addEventListener('click', mapApi.zoomOut);
  document.getElementById('zoom-reset').addEventListener('click', mapApi.reset);
  document.getElementById('crumb-france').addEventListener('click', mapApi.reset);

  const toggle = document.getElementById('sheet-toggle');
  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    toggle.setAttribute('aria-expanded', String(open));
    document.getElementById('sidebar').classList.toggle('is-open', open);
  });

  function cardView(c) {
    const v = view.get(c.code);
    return { score: v.score, cat: v.cat, fill: v.fill, filteredOut: !v.ok, weights: WEIGHTS, depName: depNames[c.dep] };
  }

  function select(code, { fly = false, focus = false } = {}) {
    state.sel = code && byCode.has(code) ? code : null;
    mapApi.select(state.sel);
    if (state.sel) {
      const c = byCode.get(state.sel);
      if (fly) mapApi.focus(c);
      card.show(c, cardView(c), { focus });
    } else {
      card.hide();
    }
    writeState(state);
  }

  function placeTooltip(point) {
    tooltip.hidden = false;
    const wrap = tooltip.parentElement.getBoundingClientRect();
    const w = tooltip.offsetWidth;
    const h = tooltip.offsetHeight;
    const left = point.x + 16 + w > wrap.width ? point.x - w - 12 : point.x + 16;
    tooltip.style.left = `${Math.max(8, left)}px`;
    tooltip.style.top = `${Math.min(Math.max(70, point.y - h / 2), wrap.height - h - 8)}px`;
  }

  function showTooltip(code, point) {
    if (!code || code === state.sel || !view.has(code)) {
      tooltip.hidden = true;
      return;
    }
    const c = byCode.get(code);
    const v = view.get(code);
    const line = !v.ok ? t['cat.out'] : v.score == null ? t['cat.unknown'] : tr('tip.score', { s: v.score, cat: t[`cat.${v.cat}`] });
    tooltip.innerHTML = `<div class="tip-name"></div>
      <div class="tip-line"><span class="swatch ${v.ok && v.cat === 'avoid' ? 'is-hatched' : ''}" style="background:${v.fill}"></span><span>${line}</span></div>
      <div class="tip-pop">${tr('tip.pop', { n: fmtInt(c.pop) })}</div>`;
    tooltip.querySelector('.tip-name').textContent = c.name;
    placeTooltip(point);
  }

  function showDepTooltip(dep, point) {
    const d = depView.get(dep);
    if (!dep || !d) {
      tooltip.hidden = true;
      return;
    }
    tooltip.innerHTML = `<div class="tip-name"></div>
      <div class="tip-line"><span class="swatch" style="background:${DEP_SCALE[d.q]}"></span><span>${tr('tip.depGo', { n: fmtInt(d.go) })}</span></div>
      <div class="tip-pop">${tr('tip.depTotal', { n: fmtInt(d.n) })}</div>`;
    tooltip.querySelector('.tip-name').textContent = `${depNames[dep]} (${dep})`;
    placeTooltip(point);
  }

  function paintCommunes() {
    const states = [];
    for (const c of communes) {
      const v = view.get(c.code);
      const b = v.ok ? bin(v.score) : 'out';
      states.push([c.code, { bin: b, hatch: v.ok && v.cat === 'avoid' }]);
    }
    mapApi.paintCommunes(states);
  }

  /** Scores and colours for every commune and département (filters changed). */
  function recompute() {
    for (const c of communes) {
      const s = score(c.pct, WEIGHTS);
      const ok = passesFilters(c, state.filters);
      view.set(c.code, { score: s, cat: category(s), ok, fill: BIN_COLOURS[ok ? bin(s) : 'out'] });
    }
    paintCommunes();

    // Départements: number of Go communes (passing the filters), coloured by quintile across départements.
    for (const [dep, list] of byDep) {
      const go = list.filter((c) => view.get(c.code).ok && view.get(c.code).cat === 'go').length;
      depView.set(dep, { go, n: list.length, q: 0 });
    }
    const sorted = [...depView.values()].map((d) => d.go).sort((a, b) => a - b);
    const cuts = [0.2, 0.4, 0.6, 0.8].map((p) => sorted[Math.floor(p * (sorted.length - 1))]);
    const depStates = [];
    for (const [dep, d] of depView) {
      d.q = cuts.filter((c) => d.go > c).length;
      depStates.push([dep, { q: d.q }]);
    }
    mapApi.paintDeps(depStates);
    renderLegend(cuts);

    refreshPanel();
    if (state.sel) card.show(byCode.get(state.sel), cardView(byCode.get(state.sel)));
    writeState(state);
  }

  function renderLegend(cuts) {
    const max = Math.max(...[...depView.values()].map((d) => d.go));
    const bounds = [0, ...cuts.map((c) => c + 1)];
    document.getElementById('legend-deps').innerHTML =
      `<div class="legend-title">${t['legend.depTitle']}</div>` +
      DEP_SCALE.map((colour, i) => {
        const lo = bounds[i];
        const hi = i < 4 ? cuts[i] : max;
        const txt = lo >= hi ? fmtInt(hi) : `${fmtInt(lo)} – ${fmtInt(hi)}`;
        return `<div><span class="swatch swatch-light" style="background:${colour}"></span><span>${txt}</span></div>`;
      }).join('');
  }

  /** Counts, slider bounds, breadcrumb and top list for what is on screen. */
  function refreshPanel() {
    const national = mapApi.national();
    document.getElementById('legend-deps').hidden = !national;
    document.getElementById('legend-communes').hidden = national;

    let visible = communes.filter((c) => mapApi.inView(c));
    if (!visible.length) visible = communes;
    let go = 0;
    let avoid = 0;
    let out = 0;
    const passing = [];
    for (const c of visible) {
      const v = view.get(c.code);
      if (!v) continue;
      if (!v.ok) out++;
      else {
        if (v.cat === 'go') go++;
        if (v.cat === 'avoid') avoid++;
        if (v.score != null) passing.push({ id: c.code, name: c.name, value: v.score, colour: v.fill });
      }
    }
    document.getElementById('counts').innerHTML = [
      tr('counts.inView', { n: fmtInt(visible.length) }),
      `<b class="c-go">${tr(go === 1 ? 'counts.go.one' : 'counts.go', { n: fmtInt(go) })}</b>`,
      `<b class="c-avoid">${tr(avoid === 1 ? 'counts.avoid.one' : 'counts.avoid', { n: fmtInt(avoid) })}</b>`,
      tr('counts.out', { n: fmtInt(out) }),
    ].join(' · ');

    // Breadcrumb: France, then the département under the centre of the map once zoomed in.
    const depEl = document.getElementById('dep-name');
    let centreDep = null;
    if (!national) {
      const ctr = mapApi.centre();
      let best = Infinity;
      for (const c of visible) {
        const d = (c.lat - ctr.lat) ** 2 + (c.lon - ctr.lon) ** 2;
        if (d < best) {
          best = d;
          centreDep = c.dep;
        }
      }
    }
    depEl.textContent = centreDep ? depNames[centreDep] : '';
    depEl.previousElementSibling.hidden = !centreDep;

    let topTitle;
    let topItems;
    if (national) {
      topTitle = t['top.depTitle'];
      topItems = [...depView.entries()]
        .sort((a, b) => b[1].go - a[1].go)
        .slice(0, TOP_N)
        .map(([dep, d]) => ({ id: dep, name: `${depNames[dep]} (${dep})`, value: fmtInt(d.go), colour: DEP_SCALE[d.q] }));
    } else {
      topTitle = t['top.title'];
      passing.sort((a, b) => b.value - a.value || a.name.localeCompare(b.name, 'fr'));
      topItems = passing.slice(0, TOP_N);
    }
    sidebar.update({ ranges: visibleRanges(visible), inView: visible.length, topTitle, topItems });
  }

  await mapApi.whenReady;
  recompute();
  if (state.sel) select(state.sel, { fly: !location.hash });
  status.textContent = '';
}

start().catch((err) => {
  console.error(err);
  status.textContent = t['app.loadError'];
});
