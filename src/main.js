import t from './i18n/fr.js';
import { BIN_COLOURS, WEIGHTS, bin, category, passesFilters, score, visibleRanges } from './lib/scoring.js';
import { fmtInt, tr } from './lib/format.js';
import { readState, writeState } from './lib/url.js';
import { createMap } from './map.js';
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

async function start() {
  const meta = await getJSON('meta.json');
  const dep = meta.departements[0];
  const [index, departements, geo, fonds] = await Promise.all([
    getJSON('communes-index.json'),
    getJSON('departements.geojson'),
    getJSON(`geo/${dep}.geojson`),
    getJSON('fonds.json'),
  ]);
  const communes = rows(index);
  const byCode = new Map(communes.map((c) => [c.code, c]));
  const depNames = Object.fromEntries(departements.features.map((f) => [f.properties.code, f.properties.name]));
  document.getElementById('dep-name').textContent = depNames[dep];

  const lons = communes.map((c) => c.lon);
  const lats = communes.map((c) => c.lat);
  const bounds = [[Math.min(...lons) - 0.05, Math.min(...lats) - 0.05], [Math.max(...lons) + 0.05, Math.max(...lats) + 0.05]];

  const state = readState();
  const view = new Map(); // code -> {score, cat, ok, fill}

  const card = createCard(document.getElementById('card'), { meta, fonds, onClose: () => select(null) });
  const tooltip = document.getElementById('tooltip');

  const mapApi = createMap({
    container: 'map',
    communes,
    geo,
    departements,
    bounds,
    locale: {
      'NavigationControl.ZoomIn': t['map.zoomIn'],
      'NavigationControl.ZoomOut': t['map.zoomOut'],
      'NavigationControl.ResetBearing': t['map.resetBearing'],
    },
    onHover: showTooltip,
    onClick: (code) => select(code === state.sel ? null : code),
    onMove: refreshPanel,
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
    pick: (code) => select(code, { fly: true, focus: true }),
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

  const toggle = document.getElementById('sheet-toggle');
  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    toggle.setAttribute('aria-expanded', String(open));
    document.getElementById('sidebar').classList.toggle('is-open', open);
  });

  function cardView(c) {
    const v = view.get(c.code);
    return {
      score: v.score,
      cat: v.cat,
      fill: v.fill,
      filteredOut: !v.ok,
      weights: WEIGHTS,
      depName: depNames[c.dep],
    };
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

  function showTooltip(code, point) {
    if (!code || code === state.sel) {
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
    tooltip.hidden = false;
    const wrap = tooltip.parentElement.getBoundingClientRect();
    const w = tooltip.offsetWidth;
    const h = tooltip.offsetHeight;
    const left = point.x + 16 + w > wrap.width ? point.x - w - 12 : point.x + 16;
    tooltip.style.left = `${Math.max(8, left)}px`;
    tooltip.style.top = `${Math.min(Math.max(70, point.y - h / 2), wrap.height - h - 8)}px`;
  }

  /** Scores and colours for every commune (filters changed). */
  function recompute() {
    const states = [];
    for (const c of communes) {
      const s = score(c.pct, WEIGHTS);
      const ok = passesFilters(c, state.filters);
      const b = ok ? bin(s) : 'out';
      const v = { score: s, cat: category(s), ok, fill: BIN_COLOURS[b] };
      view.set(c.code, v);
      states.push([c.code, { bin: b, hatch: ok && v.cat === 'avoid' }]);
    }
    mapApi.paint(states);
    refreshPanel();
    if (state.sel) card.show(byCode.get(state.sel), cardView(byCode.get(state.sel)));
    writeState(state);
  }

  /** Counts, slider bounds and top list for the communes on screen (map moved or state changed). */
  function refreshPanel() {
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
        if (v.score != null) passing.push({ code: c.code, name: c.name, score: v.score });
      }
    }
    document.getElementById('counts').innerHTML = [
      tr('counts.inView', { n: fmtInt(visible.length) }),
      `<b class="c-go">${tr(go === 1 ? 'counts.go.one' : 'counts.go', { n: fmtInt(go) })}</b>`,
      `<b class="c-avoid">${tr(avoid === 1 ? 'counts.avoid.one' : 'counts.avoid', { n: fmtInt(avoid) })}</b>`,
      tr('counts.out', { n: fmtInt(out) }),
    ].join(' · ');
    passing.sort((a, b) => b.score - a.score || a.name.localeCompare(b.name, 'fr'));
    sidebar.update({ ranges: visibleRanges(visible), inView: visible.length, topCommunes: passing.slice(0, TOP_N) });
  }

  await mapApi.whenReady;
  recompute();
  if (state.sel) select(state.sel);
  status.textContent = '';
}

start().catch((err) => {
  console.error(err);
  status.textContent = t['app.loadError'];
});
