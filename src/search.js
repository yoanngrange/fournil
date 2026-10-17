// Commune search: accessible combobox, accent-insensitive, "St" = "Saint".
import t from './i18n/fr.js';
import { normalise, tr } from './lib/format.js';

const MAX_RESULTS = 8;

export function createSearch(input, listbox, status, communes, onPick) {
  const items = communes.map((c) => ({ c, key: normalise(c.name) }));
  let results = [];
  let active = -1;

  function close() {
    listbox.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    active = -1;
  }

  function show() {
    listbox.replaceChildren();
    results.forEach(({ c }, i) => {
      const li = document.createElement('li');
      li.id = `opt-${c.code}`;
      li.setAttribute('role', 'option');
      li.setAttribute('aria-selected', String(i === active));
      li.innerHTML = '<span></span><small></small>';
      li.firstChild.textContent = c.name;
      li.lastChild.textContent = c.code;
      li.addEventListener('mousedown', (e) => {
        e.preventDefault();
        choose(i);
      });
      listbox.append(li);
    });
    if (input.value.trim() && !results.length) {
      const li = document.createElement('li');
      li.className = 'search-none';
      li.textContent = t['search.none'];
      listbox.append(li);
    }
    listbox.hidden = !input.value.trim();
    input.setAttribute('aria-expanded', String(!listbox.hidden));
    if (active >= 0) input.setAttribute('aria-activedescendant', `opt-${results[active].c.code}`);
    else input.removeAttribute('aria-activedescendant');
    status.textContent = input.value.trim() ? tr('search.results', { n: results.length }) : '';
  }

  function choose(i) {
    const r = results[i];
    if (!r) return;
    input.value = r.c.name;
    close();
    onPick(r.c.code);
  }

  input.addEventListener('input', () => {
    const q = normalise(input.value);
    active = -1;
    if (!q) {
      results = [];
      close();
      status.textContent = '';
      return;
    }
    const starts = [];
    const contains = [];
    for (const it of items) {
      if (it.key.startsWith(q)) starts.push(it);
      else if (it.key.includes(q)) contains.push(it);
    }
    const byPop = (a, b) => b.c.pop - a.c.pop;
    results = [...starts.sort(byPop), ...contains.sort(byPop)].slice(0, MAX_RESULTS);
    show();
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' && results.length) {
      active = (active + 1) % results.length;
      show();
      e.preventDefault();
    } else if (e.key === 'ArrowUp' && results.length) {
      active = (active - 1 + results.length) % results.length;
      show();
      e.preventDefault();
    } else if (e.key === 'Enter') {
      choose(active >= 0 ? active : 0);
      e.preventDefault();
    } else if (e.key === 'Escape') {
      close();
    }
  });
  input.addEventListener('blur', () => setTimeout(close, 100));
}
