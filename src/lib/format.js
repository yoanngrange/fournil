// French number formatting and string templates.
import t from '../i18n/fr.js';

const int = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 });
const dec1 = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** Fill {placeholders} of a translated string. */
export const tr = (key, params = {}) =>
  (t[key] ?? key).replace(/\{(\w+)\}/g, (_, k) => (params[k] ?? `{${k}}`));

export const fmtInt = (n) => (n == null ? t['card.notPublished'] : int.format(Math.round(n)));

export const fmtPct = (n) => (n == null ? t['card.notPublished'] : `${dec1.format(n)} %`);

export const fmtSigned = (n) =>
  n == null ? t['card.notPublished'] : `${n > 0 ? '+' : n < 0 ? '−' : ''}${dec1.format(Math.abs(n))} %`;

export const fmtEuro = (n) => (n == null ? t['card.notPublished'] : `${int.format(Math.round(n))} €`);

/** Value of a criterion in its own unit, for slider labels and the card. */
export function fmtCriterion(key, v) {
  if (v == null) return t['card.notPublished'];
  switch (key) {
    case 'income':
      return fmtEuro(v);
    case 'growth':
      return fmtSigned(v);
    case 'crime':
      return dec1.format(v);
    default:
      return fmtInt(v);
  }
}

/** Lower-case, accent-free, "st" → "saint", punctuation as spaces: for search. */
export function normalise(s) {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[''\-]/g, ' ')
    .replace(/\bste\b/g, 'sainte')
    .replace(/\bst\b/g, 'saint')
    .replace(/\s+/g, ' ')
    .trim();
}
