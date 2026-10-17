// Pinned commune card: score, key figures, age pyramid, local economy, score breakdown.
import t from './i18n/fr.js';
import { CRITERIA, BIN_COLOURS } from './lib/scoring.js';
import { fmtCriterion, fmtInt, fmtPct, tr } from './lib/format.js';

const SHORTLIST_KEY = 'fournil.shortlist';
const cache = new Map();

function readShortlist() {
  try {
    return new Set(JSON.parse(localStorage.getItem(SHORTLIST_KEY) || '[]'));
  } catch {
    return new Set();
  }
}

function writeShortlist(set) {
  try {
    localStorage.setItem(SHORTLIST_KEY, JSON.stringify([...set]));
  } catch {
    /* private mode: the star still toggles for this visit */
  }
}

async function loadCommune(code) {
  if (!cache.has(code)) {
    cache.set(code, fetch(`data/commune/${code}.json`).then((r) => (r.ok ? r.json() : Promise.reject(r))));
  }
  return cache.get(code);
}

const esc = (s) => String(s).replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch]);

export function createCard(root, { onClose, meta }) {
  let current = null;
  const shortlist = readShortlist();

  root.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') onClose();
  });

  function kpi(label, value) {
    return `<div class="kpi"><span>${label}</span><b>${value}</b></div>`;
  }

  function render(c, view, page) {
    const perBakery = c.bakeries ? fmtInt(c.pop / c.bakeries) : t['card.none'];
    const scoreText =
      view.score == null
        ? t['cat.unknown']
        : tr(view.filteredOut ? 'card.outOfFiltered' : 'card.outOf', { cat: t[`cat.${view.cat}`] });
    const starred = shortlist.has(c.code);

    let pyramid = `<p class="card-muted">${t['card.loading']}</p>`;
    let economy = '';
    if (page) {
      const total = [...page.pyramid.m, ...page.pyramid.f].reduce((a, b) => a + (b || 0), 0) || 1;
      const max = Math.max(...page.pyramid.m, ...page.pyramid.f) || 1;
      const rows = page.pyramid.bands
        .map((band, i) => ({ band, m: page.pyramid.m[i] || 0, f: page.pyramid.f[i] || 0 }))
        .reverse()
        .map(({ band, m, f }) => {
          const mp = ((100 * m) / total).toFixed(1).replace('.', ',');
          const fp = ((100 * f) / total).toFixed(1).replace('.', ',');
          return `<div class="pyr-row" role="listitem" aria-label="${tr('card.pyramidRow', { band, m: mp, f: fp })}">
            <div class="pyr-m"><span>${mp}</span><i style="width:${(100 * m) / max}%"></i></div>
            <div class="pyr-band" aria-hidden="true">${band}</div>
            <div class="pyr-f"><i style="width:${(100 * f) / max}%"></i><span>${fp}</span></div>
          </div>`;
        })
        .join('');
      pyramid = `<div class="pyr-head" aria-hidden="true"><span>${t['card.men']}</span><span>${t['card.women']}</span></div>
        <div role="list">${rows}</div>`;

      const a = page.amenities;
      const food = a.small_grocers + a.butchers + a.fishmongers;
      const line = (label, value, hint = '') =>
        `<div class="eco-row"><span>${label}${hint ? ` <small>${hint}</small>` : ''}</span><b>${value}</b></div>`;
      economy = [
        line(t['card.establishments'], fmtInt(page.businesses.total)),
        line(t['card.foodShops'], fmtInt(food), t['card.foodShops.hint']),
        line(t['card.supermarkets'], fmtInt(a.supermarkets)),
        line(t['card.cafesRestaurants'], fmtInt(page.businesses.cafes + a.restaurants)),
        line(t['card.secondHomes'], fmtPct(page.housing.second_homes_pct)),
      ].join('');
    }

    const breakdown = CRITERIA.filter((k) => k.weighted)
      .map((k) => {
        const p = c.pct[k.key];
        const w = view.weights[k.key] || 0;
        const rank = p == null ? null : Math.round(p / 10);
        return `<div class="sub">
          <div class="sub-head"><span>${t[`crit.${k.key}`]}</span>
            <span>${rank == null ? t['card.notPublished'] : rank} · ${w ? tr('card.weight', { w: t[`weight.${w}`].toLowerCase() }) : t['card.ignored']}</span></div>
          <div class="sub-bar"><i style="width:${rank ?? 0}%"></i></div>
        </div>`;
      })
      .join('');

    root.innerHTML = `
      <div class="card-head">
        <div>
          <h2 class="card-name" id="card-title" tabindex="-1">${esc(c.name)}</h2>
          <div class="card-muted">${tr('card.meta', { code: c.code, dep: esc(view.depName) })}</div>
        </div>
        <button type="button" class="card-close" aria-label="${t['card.close']}">×</button>
      </div>
      <div class="card-score">
        <span class="swatch ${view.cat === 'avoid' && !view.filteredOut ? 'is-hatched' : ''}" style="background:${view.fill}"></span>
        <b>${view.score == null ? '–' : view.score}</b>
        <span class="card-muted">${scoreText}</span>
      </div>
      <div class="kpis">
        ${kpi(t['card.inhabitants'], fmtInt(c.pop))}
        ${kpi(t['card.bakeries'], c.bakeries ? fmtInt(c.bakeries) : t['card.none'])}
        ${kpi(t['card.perBakery'], perBakery)}
        ${kpi(t['card.income'], fmtCriterion('income', c.v.income))}
        ${kpi(t['card.growth'], fmtCriterion('growth', c.v.growth))}
        ${kpi(t['card.crime'], fmtCriterion('crime', c.v.crime))}
      </div>
      <section aria-labelledby="pyr-title"><h3 id="pyr-title">${t['card.pyramid']}</h3>${pyramid}</section>
      <section aria-labelledby="eco-title"><h3 id="eco-title">${t['card.economy']}</h3>${economy}</section>
      <section aria-labelledby="sub-title"><h3 id="sub-title">${t['card.breakdown']}</h3>
        <p class="card-muted small">${t['card.breakdown.help']}</p>${breakdown}</section>
      <div class="card-actions">
        <button type="button" class="card-page" disabled>${t['card.page']}</button>
        <button type="button" class="card-star" aria-pressed="${starred}" aria-label="${starred ? t['card.shortlistRemove'] : t['card.shortlistAdd']}">${starred ? '★' : '☆'}</button>
      </div>
      <p class="card-sources">${tr('card.sources', { census: meta.years.census, crime: meta.years.crime })}<a href="sources/">${t['card.sourcesLink']}</a></p>`;

    root.querySelector('.card-close').addEventListener('click', onClose);
    root.querySelector('.card-star').addEventListener('click', () => {
      if (shortlist.has(c.code)) shortlist.delete(c.code);
      else shortlist.add(c.code);
      writeShortlist(shortlist);
      render(c, view, page);
      root.querySelector('.card-star').focus();
    });
  }

  return {
    async show(c, view, { focus = false } = {}) {
      current = c.code;
      root.hidden = false;
      root.setAttribute('aria-label', tr('card.label', { name: c.name }));
      const cached = cache.has(c.code) ? await loadCommune(c.code).catch(() => null) : null;
      render(c, view, cached);
      if (focus) root.querySelector('#card-title').focus();
      if (!cached) {
        const page = await loadCommune(c.code).catch(() => null);
        if (current === c.code && page) {
          const hadFocus = root.contains(document.activeElement);
          render(c, view, page);
          if (hadFocus) root.querySelector('#card-title').focus();
        }
      }
    },
    hide() {
      current = null;
      root.hidden = true;
      root.replaceChildren();
    },
    get code() {
      return current;
    },
  };
}
