// Pinned commune card: score, demography, bakeries, social, age pyramid, local economy, bakery market, politics.
import t from './i18n/fr.js';
import { fmtCriterion, fmtEuro, fmtInt, fmtPct, tr } from './lib/format.js';

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

export function createCard(root, { onClose, meta, fonds }) {
  let current = null;
  const shortlist = readShortlist();

  root.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') onClose();
  });

  const sireneMonth = (() => {
    const d = meta.sources.find((x) => x.id === 'sirene')?.published;
    return d ? new Date(d).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' }) : '';
  })();

  function kpi(label, value, sub = '') {
    return `<div class="kpi"><span>${label}</span><b>${value}</b>${sub ? `<small>${sub}</small>` : ''}</div>`;
  }

  /** A card section; `source` (producer and year) sits under the title so every figure carries it. */
  function section(id, title, source, body) {
    return `<section aria-labelledby="${id}"><h3 id="${id}">${title}</h3><p class="card-source">${source}</p>${body}</section>`;
  }

  const line = (label, value, hint = '') =>
    `<div class="eco-row"><span>${label}${hint ? ` <small>${hint}</small>` : ''}</span><b>${value}</b></div>`;

  function pyramidBlock(page) {
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
    return `<div class="pyr-head" aria-hidden="true"><span>${t['card.men']}</span><span>${t['card.women']}</span></div>
      <div role="list">${rows}</div>`;
  }

  function economyBlock(page) {
    const a = page.amenities;
    const b = page.businesses;
    const food = a.small_grocers + a.butchers + a.fishmongers;
    const sizes = Object.entries(b.by_size)
      .map(([k, n]) => line(t[`card.size.${k}`], fmtInt(n)))
      .join('');
    const employers = b.main_employers.length
      ? b.main_employers.map((e) => line(esc(e.name), tr('card.employees', { n: e.employees }))).join('')
      : `<p class="card-muted small">${t['card.noMainEmployer']}</p>`;
    return [
      line(t['card.establishments'], fmtInt(b.total)),
      line(t['card.foodShops'], fmtInt(food), t['card.foodShops.hint']),
      line(t['card.supermarkets'], fmtInt(a.supermarkets)),
      line(t['card.cafesRestaurants'], fmtInt(b.cafes + a.restaurants)),
      line(t['card.secondHomes'], fmtPct(page.housing.second_homes_pct)),
      `<h4>${t['card.bySize']}</h4>`,
      sizes,
      `<h4>${t['card.mainEmployers']}</h4>`,
      employers,
    ].join('');
  }

  function marketBlock(c, view, page) {
    const h = page.bakery_history;
    const dep = fonds.departements[c.dep];
    const prices = dep || fonds.france;
    const since = new Date(fonds.since).getFullYear();
    const priceHint = dep
      ? tr('card.fondsDep', { dep: esc(view.depName), n: fmtInt(dep.n), since, q1: fmtEuro(dep.q1), q3: fmtEuro(dep.q3) })
      : tr('card.fondsFrance', { n: fmtInt(prices.n), since, q1: fmtEuro(prices.q1), q3: fmtEuro(prices.q3) });
    return [
      `<p class="card-muted small">${tr('card.history', { since: h.since })}</p>`,
      line(t['card.takeovers'], fmtInt(h.takeovers)),
      line(t['card.openings'], fmtInt(h.openings)),
      line(t['card.closures'], fmtInt(h.closures)),
      `<div class="eco-row eco-price"><span>${t['card.fonds']}<small>${priceHint}</small></span><b>${fmtEuro(prices.median)}</b></div>`,
    ].join('');
  }

  const nuance = (code) => (code ? t[`nuance.${code}`] || code : t['card.noNuance']);
  const pct1 = (x) => (x == null ? '—' : `${x.toFixed(1).replace('.', ',')} %`);

  function politicsBlock(pol) {
    if (!pol || (!pol.mayor && !pol.rounds.length)) return `<p class="card-muted small">${t['card.noPolitics']}</p>`;
    const head = [
      pol.mayor ? line(t['card.mayor'], esc(pol.mayor)) : '',
      pol.list ? line(t['card.mayorList'], esc(pol.list)) : '',
      pol.list ? line(t['card.nuance'], nuance(pol.nuance)) : '',
    ].join('');
    const rounds = pol.rounds
      .map((r) => {
        const lists = r.lists
          .slice(0, 4)
          .map((l) => line(esc(l.name), pct1(l.pct), nuance(l.nuance)))
          .join('');
        const more = r.lists.length > 4 ? `<p class="card-muted small">${tr('card.moreLists', { n: r.lists.length - 4 })}</p>` : '';
        return `<h4>${tr('card.round', { n: r.round === 1 ? '1er' : '2nd', turnout: pct1(r.turnout) })}</h4>${lists}${more}`;
      })
      .join('');
    return head + rounds;
  }

  function render(c, view, page) {
    const scoreText =
      view.score == null
        ? t['cat.unknown']
        : tr(view.filteredOut ? 'card.outOfFiltered' : 'card.outOf', { cat: t[`cat.${view.cat}`] });
    const starred = shortlist.has(c.code);
    const y = meta.years;
    const loading = `<p class="card-muted">${t['card.loading']}</p>`;
    const perBakery = c.bakeries ? fmtInt(c.pop / c.bakeries) : t['card.noBakery'];

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
      ${section('demo-title', t['card.demography'], tr('card.src.census', { year: y.census }),
        `<div class="kpis">${kpi(t['card.inhabitants'], fmtInt(c.pop), tr('card.inYear', { year: y.census }))}
          ${kpi(t['card.growthYearly'], fmtCriterion('growth', c.v.growth), tr('card.fromTo', { from: y.growth_from, to: y.census }))}</div>`)}
      ${section('bak-title', t['card.bakerySection'], tr('card.src.bpe', { year: y.bpe }),
        `<div class="kpis">${kpi(t['card.bakeries'], c.bakeries ? fmtInt(c.bakeries) : t['card.none'])}
          ${kpi(t['card.perBakery'], perBakery, c.bakeries ? t['card.perBakery.sub'] : '')}</div>`)}
      ${section('soc-title', t['card.social'], tr('card.src.social', { income: y.income, crime: y.crime }),
        `<div class="kpis">${kpi(t['card.income'], fmtCriterion('income', c.v.income), t['card.income.sub'])}
          ${kpi(t['card.crime'], c.v.crime == null ? t['card.notPublished'] : `${fmtCriterion('crime', c.v.crime)} ‰`, t['card.crime.sub'])}</div>`)}
      ${section('pyr-title', t['card.pyramid'], tr('card.src.census', { year: y.census }), page ? pyramidBlock(page) : loading)}
      ${section('eco-title', t['card.economy'], tr('card.src.economy', { sirene: sireneMonth, bpe: y.bpe, census: y.census }), page ? economyBlock(page) : loading)}
      ${section('mkt-title', t['card.market'], tr('card.src.market', { sirene: sireneMonth }), page ? marketBlock(c, view, page) : loading)}
      ${section('pol-title', t['card.politics'], tr('card.src.politics', { year: y.election }), page ? politicsBlock(page.politics) : loading)}
      <div class="card-actions">
        <button type="button" class="card-page" disabled>${t['card.page']}</button>
        <button type="button" class="card-star" aria-pressed="${starred}" aria-label="${starred ? t['card.shortlistRemove'] : t['card.shortlistAdd']}">${starred ? '★' : '☆'}</button>
      </div>`;

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
