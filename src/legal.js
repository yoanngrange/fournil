// "Infos légales" (/infos-legales/): terms and data limits, legal notice, privacy, and data updates on one page,
// with an internal navigation. Copy from fr.js (`doc.terms`, `doc.legal`, `doc.privacy`, `updates.*`);
// dates and checks from data/meta.json.
import t from './i18n/fr.js';
import { addChrome, fill, longDate } from './lib/chrome.js';

const pct = (x) => `${(100 * x).toFixed(1).replace('.', ',')} %`;
const int = (n) => Math.round(n).toLocaleString('fr-FR');
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch]);
const STALE_DAYS = 40;

/** The deploy workflow runs on the 3rd of each month at 05:00 UTC (.github/workflows/deploy.yml). */
export function nextBuild(now = new Date()) {
  const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 3, 5));
  if (d <= now) d.setUTCMonth(d.getUTCMonth() + 1);
  return d;
}

function docSection(doc, params) {
  const para = (p) => (p.startsWith('<ul') ? fill(p, params) : `<p>${fill(p, params)}</p>`);
  return `<section class="legal-part" id="${doc.id}" aria-labelledby="${doc.id}-title">
    <h2 id="${doc.id}-title">${doc.title}</h2>
    ${doc.intro ? `<p class="doc-intro">${fill(doc.intro, params)}</p>` : ''}
    ${doc.callout ? `<div class="callout">${doc.callout.map(para).join('')}</div>` : ''}
    ${doc.sections.map((s) => `<h3>${s.title}</h3>${s.paras.map(para).join('')}`).join('')}
    <p class="doc-footer">${fill(t['doc.updated'], { updated: longDate(doc.updated) })}</p>
  </section>`;
}

function updatesSection(meta, index) {
  const built = new Date(meta.built_at);
  const late = (Date.now() - built) / 86400000 > STALE_DAYS;
  const fact = (label, value) => `<div><span>${label}</span><b>${value}</b></div>`;
  const rhythm = t['updates.rhythm'];
  const rows = meta.sources
    .map(
      (s) => `<tr>
        <td><a href="${esc(s.url)}">${esc(s.name)}</a><br><small>${esc(s.producer)}</small></td>
        <td>${esc(s.vintage)}</td>
        <td class="num">${s.published ? longDate(s.published) : t['updates.unknown']}</td>
        <td class="num">${longDate(s.fetched)}</td>
        <td>${rhythm[s.id] ?? t['updates.unknown']}</td>
      </tr>`,
    )
    .join('');
  const c = meta.checks;
  return `<section class="legal-part" id="donnees" aria-labelledby="donnees-title">
    <h2 id="donnees-title">${t['updates.title']}</h2>
    <p class="doc-intro">${t['updates.intro']}</p>
    ${late ? `<div class="callout" role="status"><p>${t['updates.late']}</p></div>` : ''}
    <div class="facts">
      ${fact(t['updates.built'], longDate(meta.built_at))}
      ${fact(t['updates.next'], longDate(nextBuild().toISOString()))}
      ${fact(t['updates.communes'], int(index.code.length))}
      ${fact(t['updates.oldest'], Math.min(...Object.values(meta.years)))}
    </div>
    <h3>${t['updates.table']}</h3>
    <div class="table-wrap"><table>
      <thead><tr>${['source', 'vintage', 'published', 'fetched', 'rhythm'].map((k) => `<th scope="col">${t[`updates.col.${k}`]}</th>`).join('')}</tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    <h3>${t['updates.checks']}</h3><ul>
      <li>${fill(t['updates.check.pop'], { total: int(c.population.total), official: int(c.population.official), gap: pct(c.population.gap) })}</li>
      <li>${fill(t['updates.check.bakeries'], { bpe: int(c.bakeries.bpe), sirene: int(c.bakeries.sirene_10_71_c_d), gap: pct(c.bakeries.gap) })}</li>
      <li>${fill(t['updates.check.missing'], { income: pct(c.missing_share.income), crime: pct(c.missing_share.crime) })}</li>
    </ul>
    <p class="doc-footer"><a href="sources/">${t['sources.link']}</a></p>
  </section>`;
}

async function start() {
  const [meta, index] = await Promise.all([
    fetch('data/meta.json').then((r) => r.json()),
    fetch('data/communes-index.json').then((r) => r.json()),
  ]);
  const params = { contact: t['contact.email'] };
  const docs = [t['doc.terms'], t['doc.legal'], t['doc.privacy']];
  const parts = [...docs.map((d) => [d.id, d.title]), ['donnees', t['updates.nav']]];
  const main = document.querySelector('main');
  main.innerHTML = `<h1>${t['legal.title']}</h1>
    <p class="doc-intro">${t['legal.intro']}</p>
    <nav class="legal-nav" aria-label="${t['legal.nav']}"><ol>
      ${parts.map(([id, title]) => `<li><a href="infos-legales/#${id}">${title}</a></li>`).join('')}
    </ol></nav>
    ${docs.map((d) => docSection(d, params)).join('')}
    ${updatesSection(meta, index)}`;
  // Same-page anchors: <base> points at the site root, so keep the scroll on this page.
  for (const a of main.querySelectorAll('a[href^="#"]')) a.setAttribute('href', `infos-legales/${a.getAttribute('href')}`);
  addChrome();
  if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
}

start().catch((err) => {
  console.error(err);
  document.querySelector('main').insertAdjacentHTML('beforeend', `<p role="alert">${t['app.loadError']}</p>`);
});
