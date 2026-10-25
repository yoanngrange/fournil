// Human-readable URLs (docs/SPEC.md §3.6). Mirror of slugify/dep_path/commune_path in pipeline/pages.py.

/** "L'Abergement-Clémenciat" -> "l-abergement-clemenciat" */
export function slugify(name) {
  return name
    .toLowerCase()
    .replace(/œ/g, 'oe')
    .replace(/æ/g, 'ae')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export const depPath = (depName) => `${slugify(depName)}/`;

export const communePath = (depName, name, code) => `${slugify(depName)}/${slugify(name)}-${code.toLowerCase()}/`;

/** Site root (e.g. "/fournil/"), whatever page we are on: every page sets <base href> to it. */
export const siteRoot = () => new URL('./', document.baseURI).pathname;
