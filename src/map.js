// MapLibre map: départements (national view) and commune polygons loaded per département on demand.
import * as maplibregl from '../vendor/maplibre-gl-6.11.2/maplibre-gl.mjs';
import { BIN_COLOURS } from './lib/scoring.js';

const MAX_LABELS = 14;
const LABEL_SPACING_PX = 90;
export const COMMUNE_ZOOM = 7; // below: départements; from here: communes
export const DEP_SCALE = ['#F1F4E8', '#D3E8B5', '#A9D27E', '#6FAE45', '#3F7F1F']; // design/README.md

/** Diagonal hatch (2 px lines every ~7 px, #6E0140 at 55 %), drawn at 2× for sharp screens. */
function hatchImage() {
  const size = 20;
  const data = new Uint8ClampedArray(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      if ((x + y) % size < 6) data.set([110, 1, 64, Math.round(0.55 * 255)], (y * size + x) * 4);
    }
  }
  return { width: size, height: size, data };
}

/** [[west, south], [east, north]] of a GeoJSON geometry. */
function bboxOf(geometry) {
  let w = Infinity;
  let s = Infinity;
  let e = -Infinity;
  let n = -Infinity;
  const walk = (c) => {
    if (typeof c[0] === 'number') {
      w = Math.min(w, c[0]);
      e = Math.max(e, c[0]);
      s = Math.min(s, c[1]);
      n = Math.max(n, c[1]);
    } else c.forEach(walk);
  };
  walk(geometry.coordinates);
  return [[w, s], [e, n]];
}

export function createMap({ container, communes, departements, france, loadGeo, locale, on }) {
  const depBounds = new Map(departements.features.map((f) => [f.properties.code, bboxOf(f.geometry)]));
  const loaded = new Map(); // dep -> features
  const loading = new Set();

  const map = new maplibregl.Map({
    container,
    style: {
      version: 8,
      sources: {
        deps: { type: 'geojson', data: departements, promoteId: 'code' },
        communes: { type: 'geojson', data: { type: 'FeatureCollection', features: [] }, promoteId: 'code' },
        range: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      },
      layers: [
        { id: 'background', type: 'background', paint: { 'background-color': '#E9E3D7' } },
        {
          id: 'deps-fill',
          type: 'fill',
          source: 'deps',
          paint: {
            'fill-color': ['match', ['coalesce', ['feature-state', 'q'], -1], ...DEP_SCALE.flatMap((c, i) => [i, c]), '#EFEAE0'],
            // Simplified département shapes do not follow the coast closely: hide them under the communes,
            // but only once that département's communes are drawn (otherwise the map goes blank while loading).
            'fill-opacity': [
              'interpolate', ['linear'], ['zoom'],
              COMMUNE_ZOOM - 0.5, 1,
              COMMUNE_ZOOM + 0.5, ['case', ['boolean', ['feature-state', 'loaded'], false], 0, 1],
            ],
          },
        },
        {
          id: 'communes-fill',
          type: 'fill',
          source: 'communes',
          minzoom: COMMUNE_ZOOM - 0.5,
          paint: {
            'fill-color': [
              'match',
              ['coalesce', ['feature-state', 'bin'], 'unknown'],
              ...Object.entries(BIN_COLOURS).flat(),
              BIN_COLOURS.unknown,
            ],
            'fill-opacity': ['interpolate', ['linear'], ['zoom'], COMMUNE_ZOOM - 0.5, 0, COMMUNE_ZOOM, 1],
          },
        },
        {
          id: 'communes-hatch',
          type: 'fill',
          source: 'communes',
          minzoom: COMMUNE_ZOOM - 0.5,
          paint: {
            'fill-pattern': 'hatch',
            'fill-opacity': ['case', ['boolean', ['feature-state', 'hatch'], false], 1, 0],
          },
        },
        {
          id: 'communes-line',
          type: 'line',
          source: 'communes',
          minzoom: COMMUNE_ZOOM - 0.5,
          paint: { 'line-color': '#FFFDF8', 'line-width': ['interpolate', ['linear'], ['zoom'], 7, 0.4, 11, 1.2] },
        },
        {
          id: 'deps-line',
          type: 'line',
          source: 'deps',
          paint: {
            'line-opacity': ['interpolate', ['linear'], ['zoom'], COMMUNE_ZOOM, 1, COMMUNE_ZOOM + 0.8, 0],
            'line-color': ['case', ['boolean', ['feature-state', 'hover'], false], '#1F1B16', '#A89E8E'],
            // `zoom` must be the input of the top-level interpolate, so the hover case goes inside.
            'line-width': [
              'interpolate', ['linear'], ['zoom'],
              5, ['case', ['boolean', ['feature-state', 'hover'], false], 2.2, 0.6],
              9, ['case', ['boolean', ['feature-state', 'hover'], false], 2.6, 1.6],
            ],
          },
        },
        {
          id: 'range-line',
          type: 'line',
          source: 'range',
          paint: { 'line-color': '#1F1B16', 'line-width': 1.6, 'line-dasharray': [4, 3] },
        },
        {
          id: 'communes-highlight',
          type: 'line',
          source: 'communes',
          paint: {
            'line-color': '#1F1B16',
            'line-width': [
              'case',
              ['boolean', ['feature-state', 'selected'], false], 3,
              ['boolean', ['feature-state', 'hover'], false], 2,
              0,
            ],
          },
        },
      ],
    },
    bounds: france,
    fitBoundsOptions: { padding: 24 },
    hash: 'carte',
    attributionControl: false,
    dragRotate: false,
    pitchWithRotate: false,
    renderWorldCopies: false,
    minZoom: 4,
    maxZoom: 14,
    locale,
  });
  map.touchZoomRotate.disableRotation();
  // MapLibre 6 asks this resolver for images referenced by the style before rendering them.
  map.setMissingStyleImageResolver(async (id) => {
    if (id === 'hatch' && !map.hasImage('hatch')) map.addImage('hatch', hatchImage(), { pixelRatio: 2 });
  });

  const national = () => map.getZoom() < COMMUNE_ZOOM;

  // Hover: communes when zoomed in, départements when zoomed out.
  const hovered = { communes: null, deps: null };
  const setHover = (source, id) => {
    if (hovered[source] === id) return;
    if (hovered[source]) map.setFeatureState({ source, id: hovered[source] }, { hover: false });
    hovered[source] = id;
    if (id) map.setFeatureState({ source, id }, { hover: true });
  };
  map.on('mousemove', (e) => {
    if (national()) {
      setHover('communes', null);
      const f = map.queryRenderedFeatures(e.point, { layers: ['deps-fill'] })[0];
      setHover('deps', f?.properties.code ?? null);
      map.getCanvas().style.cursor = f ? 'pointer' : '';
      on.hoverDep(f?.properties.code ?? null, e.point);
    } else {
      setHover('deps', null);
      const f = map.queryRenderedFeatures(e.point, { layers: ['communes-fill'] })[0];
      setHover('communes', f?.properties.code ?? null);
      map.getCanvas().style.cursor = f ? 'pointer' : '';
      on.hoverCommune(f?.properties.code ?? null, e.point);
    }
  });
  map.on('mouseout', () => {
    setHover('deps', null);
    setHover('communes', null);
    on.hoverCommune(null);
    on.hoverDep(null);
  });
  map.on('click', (e) => {
    if (national()) {
      const f = map.queryRenderedFeatures(e.point, { layers: ['deps-fill'] })[0];
      if (f) fitDep(f.properties.code);
    } else {
      const f = map.queryRenderedFeatures(e.point, { layers: ['communes-fill'] })[0];
      if (f) on.clickCommune(f.properties.code);
    }
  });
  map.on('moveend', () => {
    updateLabels();
    loadVisible();
    on.move();
  });
  // Start downloading while the map is still zooming or panning, not only once it stops.
  let moveTimer = null;
  map.on('move', () => {
    if (moveTimer) return;
    moveTimer = setTimeout(() => {
      moveTimer = null;
      loadVisible();
    }, 250);
  });

  // Busy while a département is downloading or new polygons are still being drawn: the UI shows a spinner
  // so a slow connection does not look like a bug.
  let drawing = false;
  const drawnSoon = new Set(); // départements whose communes were handed to MapLibre but may not be drawn yet
  const notifyBusy = () => on.busy?.(loading.size > 0 || drawing);
  map.on('idle', () => {
    // Communes are on screen now: the département fill underneath can fade out.
    for (const dep of drawnSoon) map.setFeatureState({ source: 'deps', id: dep }, { loaded: true });
    drawnSoon.clear();
    drawing = false;
    notifyBusy();
  });

  /** Load the commune polygons of every département intersecting the view (zoomed in only). */
  function loadVisible() {
    if (map.getZoom() < COMMUNE_ZOOM - 0.5) return;
    const b = map.getBounds();
    for (const [dep, [[w, s], [e, n]]] of depBounds) {
      if (loaded.has(dep) || loading.has(dep)) continue;
      if (e < b.getWest() || w > b.getEast() || n < b.getSouth() || s > b.getNorth()) continue;
      loading.add(dep);
      notifyBusy();
      loadGeo(dep)
        .then((fc) => {
          loaded.set(dep, fc.features);
          drawnSoon.add(dep);
          drawing = true;
          map.getSource('communes').setData({ type: 'FeatureCollection', features: [...loaded.values()].flat() });
          on.geoLoaded(dep);
        })
        .catch(() => {})
        .finally(() => {
          loading.delete(dep);
          notifyBusy();
        });
    }
  }

  // City labels as HTML markers (no glyph server needed): biggest communes first, spaced out.
  const byPop = [...communes].sort((a, b) => b.pop - a.pop);
  const markers = new Map();
  function updateLabels() {
    const b = map.getBounds();
    const placed = [];
    const keep = new Set();
    const max = national() ? 8 : MAX_LABELS;
    // Zoomed out, only big cities qualify: otherwise an isolated village fills the space a city could not take.
    const candidates = national() ? byPop.slice(0, 40) : byPop;
    for (const c of candidates) {
      if (placed.length >= max) break;
      if (!b.contains([c.lon, c.lat])) continue;
      const p = map.project([c.lon, c.lat]);
      if (placed.some((q) => Math.hypot(q.x - p.x, q.y - p.y) < LABEL_SPACING_PX)) continue;
      placed.push(p);
      keep.add(c.code);
      if (!markers.has(c.code)) {
        const el = document.createElement('div');
        el.className = 'map-label';
        el.textContent = c.name;
        el.setAttribute('aria-hidden', 'true');
        markers.set(c.code, new maplibregl.Marker({ element: el }).setLngLat([c.lon, c.lat]).addTo(map));
      }
    }
    for (const [code, m] of markers) {
      if (!keep.has(code)) {
        m.remove();
        markers.delete(code);
      }
    }
  }

  function fitDep(dep) {
    const b = depBounds.get(dep);
    if (!b) return;
    // Always land at commune level, even if the whole département does not fit (phones).
    const cam = map.cameraForBounds(b, { padding: 40 });
    map.easeTo({ center: cam.center, zoom: Math.max(cam.zoom, COMMUNE_ZOOM + 0.1) });
  }

  map.once('load', () => {
    updateLabels();
    loadVisible();
  });

  let selected = null;
  let pin = null;
  return {
    /** Delivery mode: bakehouse pin and, in distance mode, the dashed range circle. */
    setDelivery(base, radiusKm) {
      pin?.remove();
      pin = null;
      if (base) {
        const el = document.createElement('div');
        el.className = 'bakehouse-pin';
        el.setAttribute('aria-hidden', 'true');
        pin = new maplibregl.Marker({ element: el }).setLngLat([base.lon, base.lat]).addTo(map);
      }
      const features = [];
      if (base && radiusKm) {
        const ring = [];
        for (let i = 0; i <= 64; i++) {
          const a = (2 * Math.PI * i) / 64;
          ring.push([
            base.lon + (radiusKm / (111.32 * Math.cos((base.lat * Math.PI) / 180))) * Math.cos(a),
            base.lat + (radiusKm / 110.57) * Math.sin(a),
          ]);
        }
        features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: ring } });
      }
      map.getSource('range')?.setData({ type: 'FeatureCollection', features });
    },
    map,
    whenReady: new Promise((resolve) => map.once('load', resolve)),
    national,
    paintCommunes(states) {
      for (const [code, s] of states) map.setFeatureState({ source: 'communes', id: code }, s);
    },
    paintDeps(states) {
      for (const [code, s] of states) map.setFeatureState({ source: 'deps', id: code }, s);
    },
    select(code) {
      if (selected) map.setFeatureState({ source: 'communes', id: selected }, { selected: false });
      selected = code;
      if (code) map.setFeatureState({ source: 'communes', id: code }, { selected: true });
    },
    inView(c) {
      return map.getBounds().contains([c.lon, c.lat]);
    },
    centre() {
      const c = map.getCenter();
      return { lat: c.lat, lon: c.lng };
    },
    focus(c) {
      map.easeTo({ center: [c.lon, c.lat], zoom: Math.max(map.getZoom(), 10.5) });
    },
    fitDep,
    zoomIn: () => map.zoomIn(),
    zoomOut: () => map.zoomOut(),
    reset: () => map.fitBounds(france, { padding: 24 }),
  };
}
