// Sidebar: one row per criterion (dual range slider in real units), reset, top list.
import t from './i18n/fr.js';
import { CRITERIA } from './lib/scoring.js';
import { fmtCriterion, tr } from './lib/format.js';

const STEPS = 1000; // slider positions; values are mapped through a linear or log scale
const LOG = new Set(['pop', 'per_bakery']); // wide, skewed ranges (a city next to villages)

function scale(key, { min, max }) {
  if (LOG.has(key)) {
    const a = Math.log1p(Math.max(0, min));
    const b = Math.log1p(Math.max(0, max));
    return {
      toValue: (pos) => Math.expm1(a + ((b - a) * pos) / STEPS),
      toPos: (v) => (b === a ? 0 : (STEPS * (Math.log1p(Math.max(0, v)) - a)) / (b - a)),
    };
  }
  return {
    toValue: (pos) => min + ((max - min) * pos) / STEPS,
    toPos: (v) => (max === min ? 0 : (STEPS * (v - min)) / (max - min)),
  };
}

const roundValue = (key, v) =>
  key === 'growth' || key === 'crime' ? Math.round(v * 10) / 10 : key === 'income' ? Math.round(v / 10) * 10 : Math.round(v);

const THUMB_PX = 20;

/** Value bubbles above the two handles; merged into one "lo – hi" bubble when they would overlap. */
function placeBubbles(r, a, b, loText, hiText) {
  const width = r.row.querySelector('.dual').clientWidth;
  const centre = (pos) => (pos / STEPS) * (width - THUMB_PX) + THUMB_PX / 2;
  const [bLo, bHi] = r.bubbles;
  const put = (el, x) => {
    const half = el.offsetWidth / 2;
    el.style.left = `${Math.min(Math.max(x, half), width - half)}px`;
  };
  bLo.hidden = bHi.hidden = false;
  bLo.textContent = loText;
  bHi.textContent = hiText;
  const xLo = centre(a);
  const xHi = centre(b);
  if (xHi - xLo < (bLo.offsetWidth + bHi.offsetWidth) / 2 + 6) {
    bLo.textContent = loText === hiText ? loText : `${loText} – ${hiText}`;
    bHi.hidden = true;
    put(bLo, (xLo + xHi) / 2);
  } else {
    put(bLo, xLo);
    put(bHi, xHi);
  }
}

export function createSidebar(root, { getState, setFilter, resetFilters, pick }) {
  const rows = new Map();
  const list = root.querySelector('#criteria');

  for (const c of CRITERIA) {
    const label = t[`crit.${c.key}`];
    const row = document.createElement('div');
    row.className = 'crit';
    row.innerHTML = `
      <div class="crit-head">
        <span class="crit-label" id="l-${c.key}">${label} <span class="crit-unit">${t[`crit.${c.key}.unit`]}</span></span>
      </div>
      <div class="dual">
        <output class="bubble" aria-hidden="true"></output><output class="bubble" aria-hidden="true"></output>
        <div class="track"></div><div class="track-sel"></div>
        <input type="range" min="0" max="${STEPS}" step="1" aria-label="${tr('filters.min', { label })}">
        <input type="range" min="0" max="${STEPS}" step="1" aria-label="${tr('filters.max', { label })}">
      </div>
      <div class="crit-vals"><span></span><span></span></div>`;
    list.append(row);

    const [lo, hi] = row.querySelectorAll('input');
    const r = {
      row,
      lo,
      hi,
      sel: row.querySelector('.track-sel'),
      bubbles: row.querySelectorAll('.bubble'),
      vals: row.querySelectorAll('.crit-vals span'),
      sc: null,
    };
    rows.set(c.key, r);

    const onSlide = (which) => () => {
      if (!r.sc) return;
      let a = +lo.value;
      let b = +hi.value;
      if (a > b) {
        if (which === 'lo') a = b;
        else b = a;
      }
      setFilter(c.key, {
        lo: a <= 0 ? null : roundValue(c.key, r.sc.toValue(a)),
        hi: b >= STEPS ? null : roundValue(c.key, r.sc.toValue(b)),
      });
    };
    lo.addEventListener('input', onSlide('lo'));
    hi.addEventListener('input', onSlide('hi'));
  }
  root.querySelector('#reset').addEventListener('click', resetFilters);

  const help = root.querySelector('#filters-help');
  const top = root.querySelector('#top-list');
  const topTitleEl = root.querySelector('#top-title');

  return {
    /** ranges: visible min/max per criterion; topItems: [{id, name, value, colour}] (communes or départements) */
    update({ ranges, inView, topTitle, topItems }) {
      const { filters } = getState();
      help.textContent = tr('filters.help', { n: inView.toLocaleString('fr-FR') });
      for (const c of CRITERIA) {
        const r = rows.get(c.key);
        const range = ranges[c.key];
        r.row.classList.toggle('is-empty', !range);
        r.lo.disabled = r.hi.disabled = !range;
        if (!range) {
          r.sc = null;
          r.vals[0].textContent = t['filters.noData'];
          r.vals[1].textContent = '';
          r.bubbles.forEach((b) => (b.hidden = true));
          continue;
        }
        r.sc = scale(c.key, range);
        const f = filters[c.key] || {};
        const loV = f.lo == null ? range.min : Math.min(Math.max(f.lo, range.min), range.max);
        const hiV = f.hi == null ? range.max : Math.min(Math.max(f.hi, range.min), range.max);
        const a = f.lo == null ? 0 : Math.round(r.sc.toPos(loV));
        const b = f.hi == null ? STEPS : Math.round(r.sc.toPos(hiV));
        if (document.activeElement !== r.lo) r.lo.value = a;
        if (document.activeElement !== r.hi) r.hi.value = b;
        r.sel.style.left = `${(a / STEPS) * 100}%`;
        r.sel.style.width = `${((b - a) / STEPS) * 100}%`;
        r.lo.setAttribute('aria-valuetext', fmtCriterion(c.key, loV));
        r.hi.setAttribute('aria-valuetext', fmtCriterion(c.key, hiV));
        // Below the track: the bounds of the communes on screen. Above the handles: the chosen values.
        r.vals[0].textContent = fmtCriterion(c.key, range.min);
        r.vals[1].textContent = fmtCriterion(c.key, range.max);
        placeBubbles(r, a, b, fmtCriterion(c.key, loV), fmtCriterion(c.key, hiV));
      }

      topTitleEl.textContent = topTitle;
      top.replaceChildren();
      if (!topItems.length) {
        const li = document.createElement('li');
        li.className = 'top-empty';
        li.textContent = t['top.empty'];
        top.append(li);
      }
      topItems.forEach((item) => {
        const li = document.createElement('li');
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'top-item';
        btn.innerHTML = `<span class="swatch" style="background:${item.colour}"></span>
          <span class="top-name"></span><span class="top-score">${item.value}</span>`;
        btn.querySelector('.top-name').textContent = item.name;
        btn.addEventListener('click', () => pick(item.id));
        li.append(btn);
        top.append(li);
      });
    },
  };
}
