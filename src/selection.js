// "Ma sélection" (/ma-selection/): the communes starred in this browser, side by side (up to 3).
// Everything comes from data/communes-index.json; the list lives in localStorage only.
import t from './i18n/fr.js';
import { BIN_COLOURS, WEIGHTS, bin, category, score } from './lib/scoring.js';
import { fmtCriterion, fmtInt, fmtSigned, tr } from './lib/format.js';
import { readShortlist, toggleShortlist } from './lib/shortlist.js';
import { communePath } from './lib/slug.js';
import { addChrome } from './lib/chrome.js';

const MAX_COMPARE = 3;
const esc = (s) => String(s).replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch]);

// Rows of the comparison: label, value, number used to find the best (null: no "best"), higher is better?
const ROWS = [
  ['sel.row.score', (c) => (c.score == null ? '–' : `${c.score} / 100`), (c) => c.score, true],
  ['card.inhabitants', (c) => fmtInt(c.pop), (c) => c.pop, null],
  ['card.growthYearly', (c) => fmtSigned(c.v.growth), (c) => c.v.growth, true],
  ['card.bakeries', (c) => (c.bakeries ? fmtInt(c.bakeries) : t['card.none']), () => null, null],
  ['card.perBakery', (c) => (c.bakeries ? fmtInt(c.pop / c.bakeries) : t['card.noBakery']), (c) => (c.bakeries ? c.pop / c.bakeries : null), true],
  ['card.income', (c) => fmtCriterion('income', c.v.income), (c) => c.v.income, true],
  ['card.crime', (c) => (c.v.crime == null ? t['card.notPublished'] : `${fmtCriterion('crime', c.v.crime)} ‰`), (c) => c.v.crime, false],
];

let chosen = null; // codes ticked for comparison

async function start() {
  const [index, deps] = await Promise.all([
    fetch('data/communes-index.json').then((r) => r.json()),
    fetch('data/departements.geojson').then((r) => r.json()),
  ]);
  const depNames = Object.fromEntries(deps.features.map((f) => [f.properties.code, f.properties.name]));
  const pos = new Map(index.code.map((code, i) => [code, i]));
  const commune = (code) => {
    const i = pos.get(code);
    const v = {};
    const pct = {};
    for (const k of Object.keys(index.v)) {
      v[k] = index.v[k][i];
      pct[k] = index.pct[k][i];
    }
    const s = score(pct, WEIGHTS);
    return { code, name: index.name[i], dep: index.dep[i], depName: depNames[index.dep[i]], pop: index.pop[i], bakeries: index.bakeries[i], v, score: s, cat: category(s), fill: BIN_COLOURS[bin(s)] };
  };

  const main = document.querySelector('main');
  addChrome();

  function render() {
    const list = [...readShortlist()].filter((code) => pos.has(code)).map(commune);
    list.sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
    chosen = (chosen ?? list.slice(0, MAX_COMPARE).map((c) => c.code)).filter((code) => list.some((c) => c.code === code));
    if (!list.length) {
      main.innerHTML = `<h1>${t['sel.title']}</h1><p class="doc-intro">${t['sel.intro']}</p>
        <div class="callout"><p>${t['sel.empty']}</p></div><p><a class="btn" href="./">${t['sel.toMap']}</a></p>`;
      return;
    }
    const compared = list.filter((c) => chosen.includes(c.code));
    const swatch = (c) => `<span class="swatch ${c.cat === 'avoid' ? 'is-hatched' : ''}" style="background:${c.fill}"></span>`;
    main.innerHTML = `<h1>${t['sel.title']}</h1>
      <p class="doc-intro">${t['sel.intro']}</p>
      <h2>${tr('sel.listTitle', { n: list.length })}</h2>
      <p class="help">${tr('sel.pick', { n: MAX_COMPARE })}</p>
      <ul class="sel-list">${list
        .map(
          (c) => `<li>
            <input type="checkbox" id="cmp-${c.code}" data-code="${c.code}" ${chosen.includes(c.code) ? 'checked' : ''}
              ${!chosen.includes(c.code) && chosen.length >= MAX_COMPARE ? 'disabled' : ''}>
            <label for="cmp-${c.code}" class="visually-hidden">${tr('sel.compareOne', { name: esc(c.name) })}</label>
            ${swatch(c)}
            <a href="${communePath(c.depName, c.name, c.code)}">${esc(c.name)}</a>
            <small>${esc(c.depName)}</small>
            <b class="num">${c.score ?? '–'}</b>
            <button type="button" class="sel-remove" data-code="${c.code}" aria-label="${tr('sel.remove', { name: esc(c.name) })}">×</button>
          </li>`,
        )
        .join('')}</ul>
      ${compared.length
        ? `<h2>${t['sel.compareTitle']}</h2>
      <div class="table-wrap"><table class="sel-table">
        <thead><tr><th scope="col"><span class="visually-hidden">${t['sel.criterion']}</span></th>${compared
          .map((c) => `<th scope="col"><a href="${communePath(c.depName, c.name, c.code)}">${esc(c.name)}</a><br><small>${esc(c.depName)}</small></th>`)
          .join('')}</tr></thead>
        <tbody>${ROWS.map(([key, show, num, higher]) => {
          const vals = compared.map(num);
          const known = vals.filter((x) => x != null);
          const best = higher == null || known.length < 2 ? null : higher ? Math.max(...known) : Math.min(...known);
          return `<tr><th scope="row">${t[key]}</th>${compared
            .map((c, i) => {
              const isBest = best != null && vals[i] === best && new Set(known).size > 1;
              return `<td class="num${isBest ? ' is-best' : ''}">${show(c)}${isBest ? ` <span class="best-tag">${t['sel.best']}</span>` : ''}</td>`;
            })
            .join('')}</tr>`;
        }).join('')}</tbody>
      </table></div>
      <p class="help">${t['sel.note']}</p>`
        : ''}`;

    for (const box of main.querySelectorAll('.sel-list input')) {
      box.addEventListener('change', () => {
        chosen = box.checked ? [...chosen, box.dataset.code] : chosen.filter((x) => x !== box.dataset.code);
        render();
        document.getElementById(`cmp-${box.dataset.code}`)?.focus();
      });
    }
    for (const btn of main.querySelectorAll('.sel-remove')) {
      btn.addEventListener('click', () => {
        toggleShortlist(btn.dataset.code);
        render();
        main.querySelector('h2')?.setAttribute('tabindex', '-1');
        main.querySelector('h2')?.focus();
      });
    }
  }

  render();
}

start().catch((err) => {
  console.error(err);
  document.querySelector('main').insertAdjacentHTML('beforeend', `<p role="alert">${t['app.loadError']}</p>`);
});
