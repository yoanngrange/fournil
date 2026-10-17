// Sources & method page: long-form copy from fr.js, source list and figures from data/meta.json.
import t from './i18n/fr.js';

const pct = (x) => `${(100 * x).toFixed(1).replace('.', ',')} %`;
const date = (iso) => (iso ? new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }) : '—');
const fill = (s, p) => s.replace(/\{(\w+)\}/g, (_, k) => p[k] ?? `{${k}}`);
const el = (id) => document.getElementById(id);

function list(id, items, params) {
  el(id).innerHTML = items.map((html) => `<li>${fill(html, params)}</li>`).join('');
}

async function start() {
  const meta = await fetch('../data/meta.json').then((r) => r.json());
  const params = {
    census: meta.years.census,
    growthFrom: meta.years.growth_from,
    crime: meta.years.crime,
    bakeryGap: pct(meta.checks.bakeries.gap),
    crimeMissing: pct(meta.checks.missing_share.crime),
    cog: meta.cog_year,
    built: date(meta.built_at),
  };

  el('back').textContent = t['sources.back'];
  el('title').textContent = t['sources.title'];
  el('intro').textContent = t['sources.intro'];
  for (const k of ['how', 'choices', 'bias']) {
    el(`${k}-title`).textContent = t[`sources.${k}.title`];
    list(k, t[`sources.${k}`], params);
  }
  el('list-title').textContent = t['sources.list.title'];

  const table = el('list');
  const head = ['producer', 'name', 'vintage', 'licence', 'fetched'].map((k) => `<th scope="col">${t[`sources.list.${k}`]}</th>`);
  table.innerHTML = `<thead><tr>${head.join('')}</tr></thead><tbody></tbody>`;
  const body = table.querySelector('tbody');
  for (const s of meta.sources) {
    const tr = document.createElement('tr');
    for (const v of [s.producer, null, s.vintage, s.licence, date(s.fetched)]) {
      const td = document.createElement('td');
      if (v === null) {
        const a = document.createElement('a');
        a.href = s.url;
        a.textContent = s.name;
        td.append(a);
      } else td.textContent = v;
      tr.append(td);
    }
    body.append(tr);
  }
  el('footer').textContent = fill(t['sources.footer'], params);
}

start();
