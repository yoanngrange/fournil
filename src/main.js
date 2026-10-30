import t from './i18n/fr.js';
import { BIN_COLOURS, WEIGHTS, bin, category, passesFilters, score, visibleRanges } from './lib/scoring.js';
import { fmtInt, tr } from './lib/format.js';
import { readState, writeState } from './lib/url.js';
import { depPath, siteRoot } from './lib/slug.js';
import { COUNT, RADIUS, bestByDistance, contiguousBlock, reach, withinDistance } from './lib/delivery.js';
import { DEP_SCALE, createMap } from './map.js';
import { createSidebar } from './sidebar.js';
import { createCard } from './card.js';
import { createSearch } from './search.js';

const TOP_N = 8;
const MAX_RANKED = 1500; // above this many communes on screen, delivery spots are not ranked

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
  const [meta, index, departements] = await Promise.all([
    getJSON('meta.json'),
    getJSON('communes-index.json'),
    getJSON('departements.geojson'),
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
  const sharedPosition = location.hash.includes('carte='); // read before MapLibre writes its own
  const view = new Map(); // code -> {score, cat, ok, fill}
  const depView = new Map(); // dep -> {go, nob, n, q}
  const adjacency = new Map(); // code -> [neighbour codes], loaded per département
  const adjLoading = new Map();
  const dlv = state.delivery;
  let area = null; // delivery: Set of communes served by the bakehouse (null: no bakehouse yet)

  /** Neighbour lists of a département (and, for a bakehouse near a border, of the next ones). */
  function loadAdj(dep) {
    if (!exported.has(dep)) return Promise.resolve();
    if (!adjLoading.has(dep)) {
      adjLoading.set(
        dep,
        getJSON(`adj/${dep}.json`).then((adj) => {
          for (const [code, list] of Object.entries(adj)) adjacency.set(code, list);
        }),
      );
    }
    return adjLoading.get(dep);
  }

  const card = createCard(document.getElementById('card'), { meta, onClose: () => select(null) });
  const tooltip = document.getElementById('tooltip');

  const mapApi = createMap({
    container: 'map',
    communes,
    departements,
    france: FRANCE,
    loadGeo: (dep) =>
      exported.has(dep)
        ? Promise.all([getJSON(`geo/${dep}.geojson`), loadAdj(dep)]).then(([geo]) => geo)
        : Promise.reject(new Error(dep)),
    locale: {
      'NavigationControl.ZoomIn': t['map.zoomIn'],
      'NavigationControl.ZoomOut': t['map.zoomOut'],
      'NavigationControl.ResetBearing': t['map.resetBearing'],
    },
    on: {
      hoverCommune: showTooltip,
      hoverDep: showDepTooltip,
      clickCommune: (code) => {
        if (dlv.on) {
          setBase(code);
          select(code);
        } else select(code === state.sel ? null : code);
      },
      geoLoaded: () => {
        if (dlv.on) {
          // New neighbour lists may extend contiguous blocks: recompute reach and the ranking too.
          updateArea();
          renderReach();
          refreshPanel();
        }
        paintCommunes();
        mapApi.select(state.sel);
      },
      move: refreshPanel,
      busy: (on) => {
        document.getElementById('map-busy').hidden = !on;
      },
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
    pick(id) {
      if (!byCode.has(id)) return mapApi.fitDep(id);
      if (dlv.on) setBase(id);
      select(id, { fly: true, focus: true });
    },
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

  // ---------- delivery mode ----------
  const dlvSwitch = document.getElementById('delivery');
  const dlvBody = document.getElementById('delivery-body');
  const coverKm = document.getElementById('cover-km');
  const coverN = document.getElementById('cover-n');
  const slider = document.getElementById('cover-slider');

  function syncDeliveryControls() {
    dlvSwitch.checked = dlv.on;
    dlvBody.hidden = !dlv.on;
    document.querySelector('.filters').hidden = dlv.on;
    document.getElementById('filters-off').hidden = !dlv.on;
    coverKm.setAttribute('aria-pressed', String(dlv.cover === 'km'));
    coverN.setAttribute('aria-pressed', String(dlv.cover === 'n'));
    const byKm = dlv.cover === 'km';
    const range = byKm ? RADIUS : COUNT;
    slider.min = range.min;
    slider.max = range.max;
    slider.step = 1;
    slider.value = byKm ? dlv.radius : dlv.count;
    document.getElementById('cover-label').textContent = t[byKm ? 'delivery.radius' : 'delivery.count'];
    document.getElementById('cover-value').textContent = tr(byKm ? 'delivery.radiusValue' : 'delivery.countValue', { n: slider.value });
    document.getElementById('cover-help').textContent = t[byKm ? 'delivery.helpKm' : 'delivery.helpN'];
  }

  function setBase(code) {
    dlv.base = code;
    const dep = code?.slice(0, 2);
    if (dep && dlv.cover === 'n') {
      // A block of up to 40 communes can cross into the next départements: load their neighbour lists too.
      loadAdj(dep).then(() => {
        const nearDeps = new Set((adjacency.get(code) || []).map((x) => x.slice(0, 2)));
        for (const c of [...(adjacency.get(code) || [])].flatMap((x) => adjacency.get(x) || [])) nearDeps.add(c.slice(0, 2));
        return Promise.all([...nearDeps].map(loadAdj));
      }).then(recompute);
    }
    recompute();
  }

  /** Communes served by the bakehouse with the current settings. */
  function updateArea() {
    const base = dlv.base && byCode.get(dlv.base);
    if (!dlv.on || !base) {
      area = null;
      mapApi.setDelivery(dlv.on ? base : null, null);
      return;
    }
    area =
      dlv.cover === 'km'
        ? new Set(withinDistance(base, communes, dlv.radius).map((c) => c.code))
        : contiguousBlock(base.code, dlv.count, byCode, adjacency);
    mapApi.setDelivery(base, dlv.cover === 'km' ? dlv.radius : null);
  }

  function renderReach() {
    const el = document.getElementById('reach');
    if (!area) {
      el.innerHTML = `<p>${t['delivery.pickBase']}</p>`;
      return;
    }
    const r = reach(area, byCode, dlv.base);
    const cell = (label, value, cls = '') => `<div><span>${label}</span><b class="${cls}">${value}</b></div>`;
    el.innerHTML = [
      cell(t['delivery.reach.n'], fmtInt(r.n)),
      cell(t['delivery.reach.noBakery'], fmtInt(r.noBakery), 'is-opportunity'),
      cell(t['delivery.reach.pop'], fmtInt(r.pop)),
      cell(t['delivery.reach.popNoBakery'], fmtInt(r.popNoBakery), 'is-opportunity'),
      `<p>${tr('delivery.base', { name: byCode.get(dlv.base).name.replace(/[<&]/g, '') })} ${tr('delivery.reach.far', { km: fmtInt(r.furthestKm) })}</p>`,
    ].join('');
  }

  dlvSwitch.addEventListener('change', () => {
    dlv.on = dlvSwitch.checked;
    syncDeliveryControls();
    recompute();
  });
  for (const [btn, cover] of [[coverKm, 'km'], [coverN, 'n']]) {
    btn.addEventListener('click', () => {
      dlv.cover = cover;
      syncDeliveryControls();
      if (dlv.base) setBase(dlv.base);
      else recompute();
    });
  }
  slider.addEventListener('input', () => {
    if (dlv.cover === 'km') dlv.radius = +slider.value;
    else dlv.count = +slider.value;
    syncDeliveryControls();
    recompute();
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
    const line = dlv.on
      ? c.bakeries ? tr('tip.bakeries', { n: fmtInt(c.bakeries) }) : t['tip.noBakery']
      : !v.ok ? t['cat.out'] : v.score == null ? t['cat.unknown'] : tr('tip.score', { s: v.score, cat: t[`cat.${v.cat}`] });
    const fill = dlv.on ? BIN_COLOURS[deliveryBin(c)] : v.fill;
    tooltip.innerHTML = `<div class="tip-name"></div>
      <div class="tip-line"><span class="swatch ${!dlv.on && v.ok && v.cat === 'avoid' ? 'is-hatched' : ''}" style="background:${fill}"></span><span>${line}</span></div>
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
      <div class="tip-line"><span class="swatch" style="background:${DEP_SCALE[d.q]}"></span><span>${tr(dlv.on ? 'tip.depNob' : 'tip.depGo', { n: fmtInt(dlv.on ? d.nob : d.go) })}</span></div>
      <div class="tip-pop">${tr('tip.depTotal', { n: fmtInt(d.n) })}</div>`;
    tooltip.querySelector('.tip-name').textContent = `${depNames[dep]} (${dep})`;
    placeTooltip(point);
  }

  /** Delivery colours: the bakehouse, then in range without / with a bakery, then outside the range. */
  function deliveryBin(c) {
    if (c.code === dlv.base) return 'd_base';
    if (area && !area.has(c.code)) return 'd_out';
    return c.bakeries ? 'd_has' : 'd_open';
  }

  function paintCommunes() {
    const states = [];
    for (const c of communes) {
      const v = view.get(c.code);
      if (dlv.on) states.push([c.code, { bin: deliveryBin(c), hatch: false }]);
      else states.push([c.code, { bin: v.ok ? bin(v.score) : 'out', hatch: v.ok && v.cat === 'avoid' }]);
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
    updateArea();
    renderReach();
    paintCommunes();

    // Départements: number of Go communes (passing the filters), or of communes without a bakery in
    // delivery mode, coloured by quintile across départements.
    for (const [dep, list] of byDep) {
      const go = list.filter((c) => view.get(c.code).ok && view.get(c.code).cat === 'go').length;
      const nob = list.filter((c) => c.bakeries === 0 && c.pop > 0).length;
      depView.set(dep, { go, nob, n: list.length, q: 0, value: dlv.on ? nob : go });
    }
    const sorted = [...depView.values()].map((d) => d.value).sort((a, b) => a - b);
    const cuts = [0.2, 0.4, 0.6, 0.8].map((p) => sorted[Math.floor(p * (sorted.length - 1))]);
    const depStates = [];
    for (const [dep, d] of depView) {
      d.q = cuts.filter((c) => d.value > c).length;
      depStates.push([dep, { q: d.q }]);
    }
    mapApi.paintDeps(depStates);
    renderLegend(cuts);

    refreshPanel();
    if (state.sel) card.show(byCode.get(state.sel), cardView(byCode.get(state.sel)));
    writeState(state);
  }

  function renderLegend(cuts) {
    const max = Math.max(...[...depView.values()].map((d) => d.value));
    const bounds = [0, ...cuts.map((c) => c + 1)];
    document.getElementById('legend-deps').innerHTML =
      `<div class="legend-title">${t[dlv.on ? 'legend.depNoBakery' : 'legend.depTitle']}</div>` +
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
    document.getElementById('legend-communes').hidden = national || dlv.on;
    document.getElementById('legend-delivery').hidden = national || !dlv.on;

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
    const nobVisible = visible.filter((c) => c.bakeries === 0 && c.pop > 0);
    document.getElementById('counts').innerHTML = dlv.on
      ? tr('delivery.counts', {
          n: fmtInt(visible.length),
          nob: fmtInt(nobVisible.length),
          pop: fmtInt(nobVisible.reduce((a, c) => a + c.pop, 0)),
        })
      : [
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

    // The address follows the view: /<département>/ when zoomed in, the site root when zoomed out.
    const path = siteRoot() + (centreDep ? depPath(depNames[centreDep]) : '');
    if (location.pathname !== path) history.replaceState(null, '', path + location.search + location.hash);

    let topTitle;
    let topItems;
    if (national) {
      topTitle = t[dlv.on ? 'delivery.depTitle' : 'top.depTitle'];
      topItems = [...depView.entries()]
        .sort((a, b) => b[1].value - a[1].value)
        .slice(0, TOP_N)
        .map(([dep, d]) => ({ id: dep, name: `${depNames[dep]} (${dep})`, value: fmtInt(d.value), colour: DEP_SCALE[d.q] }));
    } else if (dlv.on) {
      topTitle = t['delivery.topTitle'];
      topItems = visible.length > MAX_RANKED ? [] : bestSpots(visible);
    } else {
      topTitle = t['top.title'];
      passing.sort((a, b) => b.value - a.value || a.name.localeCompare(b.name, 'fr'));
      topItems = passing.slice(0, TOP_N);
    }
    const topEmpty = dlv.on && !national && visible.length > MAX_RANKED ? t['delivery.zoomToRank'] : t['top.empty'];
    sidebar.update({ ranges: visibleRanges(visible), inView: visible.length, topTitle, topItems, topEmpty });
  }

  /** Communes on screen ranked by inhabitants without a bakery that a bakehouse there would serve. */
  function bestSpots(visible) {
    const candidates = visible.filter((c) => c.pop > 0);
    let scored;
    if (dlv.cover === 'km') scored = bestByDistance(candidates, communes, dlv.radius);
    else {
      scored = candidates.map((c) => {
        let popNoBakery = 0;
        for (const code of contiguousBlock(c.code, dlv.count, byCode, adjacency)) {
          const x = byCode.get(code);
          if (x.bakeries === 0) popNoBakery += x.pop;
        }
        return { c, popNoBakery };
      });
    }
    return scored
      .filter((s) => s.popNoBakery > 0)
      .sort((a, b) => b.popNoBakery - a.popNoBakery)
      .slice(0, TOP_N)
      .map(({ c, popNoBakery }) => ({
        id: c.code,
        name: c.name,
        value: tr('delivery.topValue', { n: fmtInt(popNoBakery) }),
        colour: BIN_COLOURS.d_open,
      }));
  }

  syncDeliveryControls();
  await mapApi.whenReady;
  // Département page (/loire-atlantique/): open on it unless the address already holds a map position.
  const preset = document.querySelector('meta[name="fournil-dep"]')?.content;
  if (preset && !sharedPosition) mapApi.fitDep(preset);
  if (dlv.on && dlv.base) setBase(dlv.base); // also loads the neighbour lists a contiguous block needs
  else recompute();
  if (state.sel) select(state.sel, { fly: !sharedPosition });
  status.textContent = '';
}

start().catch((err) => {
  console.error(err);
  status.textContent = t['app.loadError'];
});
