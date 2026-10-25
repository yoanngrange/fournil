// Pinned commune card on the map: score and the four key figures, then a link to the full commune page.
import t from './i18n/fr.js';
import { fmtCriterion, fmtInt, tr } from './lib/format.js';
import { readShortlist, toggleShortlist } from './lib/shortlist.js';
import { communePath } from './lib/slug.js';

const esc = (s) => String(s).replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch]);

export function createCard(root, { onClose, meta }) {
  let current = null;

  root.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') onClose();
  });

  const kpi = (label, value, sub = '') =>
    `<div class="kpi"><span>${label}</span><b>${value}</b>${sub ? `<small>${sub}</small>` : ''}</div>`;

  function render(c, view) {
    const scoreText =
      view.score == null
        ? t['cat.unknown']
        : tr(view.filteredOut ? 'card.outOfFiltered' : 'card.outOf', { cat: t[`cat.${view.cat}`] });
    const starred = readShortlist().has(c.code);
    const y = meta.years;

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
        ${kpi(t['card.inhabitants'], fmtInt(c.pop), tr('card.inYear', { year: y.census }))}
        ${kpi(t['card.bakeries'], c.bakeries ? fmtInt(c.bakeries) : t['card.none'], tr('card.inYear', { year: y.bpe }))}
        ${kpi(t['card.perBakery'], c.bakeries ? fmtInt(c.pop / c.bakeries) : '—')}
        ${kpi(t['card.income'], fmtCriterion('income', c.v.income), tr('card.inYear', { year: y.income }))}
      </div>
      <p class="card-source">${tr('card.src.short', { census: y.census, bpe: y.bpe, income: y.income })}</p>
      <div class="card-actions">
        <a class="card-page" href="${communePath(view.depName, c.name, c.code)}">${t['card.page']}</a>
        <button type="button" class="card-star" aria-pressed="${starred}" aria-label="${starred ? t['card.shortlistRemove'] : t['card.shortlistAdd']}">${starred ? '★' : '☆'}</button>
      </div>`;

    root.querySelector('.card-close').addEventListener('click', onClose);
    root.querySelector('.card-star').addEventListener('click', () => {
      toggleShortlist(c.code);
      render(c, view);
      root.querySelector('.card-star').focus();
    });
  }

  return {
    show(c, view, { focus = false } = {}) {
      current = c.code;
      root.hidden = false;
      root.setAttribute('aria-label', tr('card.label', { name: c.name }));
      render(c, view);
      if (focus) root.querySelector('#card-title').focus();
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
