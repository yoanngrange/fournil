// Fournyl service worker: the app shell works offline, data and pages already seen stay available.
// Strategy: shell = cache first (versioned at build time), data and pages = network first, cache fallback.
// Data files are cached as they are viewed only (all of France is ~250 MB), capped at MAX_DATA entries.
const VERSION = '__BUILD__'; // replaced by scripts/build_site.sh with the build timestamp
const SHELL = `shell-${VERSION}`;
const RUNTIME = 'runtime-v1';
const MAX_DATA = 120;

const SHELL_FILES = [
  './',
  'manifest.webmanifest',
  'src/styles.css',
  'src/main.js',
  'src/map.js',
  'src/sidebar.js',
  'src/card.js',
  'src/search.js',
  'src/commune.js',
  'src/sources.js',
  'src/legal.js',
  'src/selection.js',
  'src/notfound.js',
  'src/i18n/fr.js',
  'src/lib/chrome.js',
  'src/lib/delivery.js',
  'src/lib/format.js',
  'src/lib/scoring.js',
  'src/lib/shortlist.js',
  'src/lib/slug.js',
  'src/lib/url.js',
  'vendor/maplibre-gl-6.11.2/maplibre-gl.css',
  'vendor/maplibre-gl-6.11.2/maplibre-gl.mjs',
  'img/mark.svg',
  'img/icon.svg',
  'fonts/atkinson-hyperlegible-latin-400-normal.woff2',
  'fonts/atkinson-hyperlegible-latin-700-normal.woff2',
  'fonts/big-shoulders-display-latin-800-normal.woff2',
  'fonts/coustard-latin-900-normal.woff2',
  'fonts/courier-prime-latin-400-normal.woff2',
  'fonts/courier-prime-latin-700-normal.woff2',
  'data/meta.json',
  'data/communes-index.json',
  'data/departements.geojson',
  'data/fonds.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL).then((cache) => cache.addAll(SHELL_FILES.map((f) => new URL(f, self.registration.scope))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('shell-') && k !== SHELL).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

async function trim(cache) {
  const keys = await cache.keys();
  for (const k of keys.slice(0, Math.max(0, keys.length - MAX_DATA))) await cache.delete(k);
}

async function networkFirst(request) {
  const cache = await caches.open(RUNTIME);
  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone()).then(() => trim(cache));
    }
    return response;
  } catch (err) {
    const hit = (await caches.match(request, { ignoreSearch: request.mode === 'navigate' }))
      || (request.mode === 'navigate' ? await caches.match(new URL('./', self.registration.scope)) : null);
    if (hit) return hit;
    throw err;
  }
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return; // Wikimedia, IGN, analytics: browser default
  const path = url.pathname.slice(new URL(self.registration.scope).pathname.length);
  if (request.mode === 'navigate' || path.startsWith('data/')) {
    event.respondWith(networkFirst(request));
    return;
  }
  event.respondWith(caches.match(request).then((hit) => hit || fetch(request)));
});
