// Communes starred by the user, kept in this browser only (localStorage).
const KEY = 'fournyl.shortlist';
const OLD_KEY = 'fournil.shortlist'; // before the Fournyl rename (Nov 2026): still read so nobody loses a list

export function readShortlist() {
  try {
    return new Set(JSON.parse(localStorage.getItem(KEY) || localStorage.getItem(OLD_KEY) || '[]'));
  } catch {
    return new Set();
  }
}

export function toggleShortlist(code) {
  const set = readShortlist();
  if (set.has(code)) set.delete(code);
  else set.add(code);
  try {
    localStorage.setItem(KEY, JSON.stringify([...set]));
  } catch {
    /* private mode: the star still toggles for this visit */
  }
  return set.has(code);
}
