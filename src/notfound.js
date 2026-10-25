// 404 page: redirect old or misspelt addresses to the canonical one, when we can tell what was meant.
//   …/clison-44043/  or  /commune/44043  -> /loire-atlantique/clisson-44043/
//   /loire-atlantiqu/ (unknown)          -> stays here, with a link home
import { communePath, depPath, siteRoot, slugify } from './lib/slug.js';

async function start() {
  const root = siteRoot();
  const rest = location.pathname.startsWith(root) ? location.pathname.slice(root.length) : location.pathname;
  const code = rest.match(/(?:^|[/-])(\d[\dab]\d{3})\/?$/i)?.[1]?.toUpperCase();
  const [index, deps] = await Promise.all([
    fetch('data/communes-index.json').then((r) => r.json()),
    fetch('data/departements.geojson').then((r) => r.json()),
  ]);
  const depNames = Object.fromEntries(deps.features.map((f) => [f.properties.code, f.properties.name]));
  let target = null;
  const i = code ? index.code.indexOf(code) : -1;
  if (i >= 0) target = communePath(depNames[index.dep[i]], index.name[i], code);
  else {
    const first = slugify(rest.split('/')[0] || '');
    const dep = Object.entries(depNames).find(([c, n]) => slugify(n) === first || c.toLowerCase() === first);
    if (dep) target = depPath(dep[1]);
  }
  if (target) location.replace(root + target + location.search + location.hash);
  else document.getElementById('status').textContent = '';
}

start().catch(() => {
  document.getElementById('status').textContent = '';
});
