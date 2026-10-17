// MapLibre map: commune polygons coloured through feature-state, hatching, hover, labels.
import * as maplibregl from '../vendor/maplibre-gl-6.11.2/maplibre-gl.mjs';
import { BIN_COLOURS } from './lib/scoring.js';

const MAX_LABELS = 14;
const LABEL_SPACING_PX = 90;

/** Diagonal hatch (2 px lines every ~7 px, #6E0140 at 55 %), drawn at 2× for sharp screens. */
function hatchImage() {
  const size = 20;
  const data = new Uint8ClampedArray(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      if ((x + y) % size < 6) {
        const i = (y * size + x) * 4;
        data.set([110, 1, 64, Math.round(0.55 * 255)], i);
      }
    }
  }
  return { width: size, height: size, data };
}

export function createMap({ container, communes, geo, departements, bounds, locale, onHover, onClick, onMove }) {
  const map = new maplibregl.Map({
    container,
    style: {
      version: 8,
      sources: {
        deps: { type: 'geojson', data: departements },
        communes: { type: 'geojson', data: geo, promoteId: 'code' },
      },
      layers: [
        { id: 'background', type: 'background', paint: { 'background-color': '#E9E3D7' } },
        { id: 'deps-fill', type: 'fill', source: 'deps', paint: { 'fill-color': '#EFEAE0' } },
        {
          id: 'communes-fill',
          type: 'fill',
          source: 'communes',
          paint: {
            'fill-color': [
              'match',
              ['coalesce', ['feature-state', 'bin'], 'unknown'],
              ...Object.entries(BIN_COLOURS).flat(),
              BIN_COLOURS.unknown,
            ],
          },
        },
        {
          id: 'communes-hatch',
          type: 'fill',
          source: 'communes',
          paint: {
            'fill-pattern': 'hatch',
            'fill-opacity': ['case', ['boolean', ['feature-state', 'hatch'], false], 1, 0],
          },
        },
        {
          id: 'communes-line',
          type: 'line',
          source: 'communes',
          paint: { 'line-color': '#FFFDF8', 'line-width': ['interpolate', ['linear'], ['zoom'], 7, 0.4, 11, 1.2] },
        },
        { id: 'deps-line', type: 'line', source: 'deps', paint: { 'line-color': '#A89E8E', 'line-width': 1.2 } },
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
    bounds,
    fitBoundsOptions: { padding: 40 },
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

  // Hover and click.
  let hovered = null;
  const setHover = (code) => {
    if (hovered === code) return;
    if (hovered) map.setFeatureState({ source: 'communes', id: hovered }, { hover: false });
    hovered = code;
    if (code) map.setFeatureState({ source: 'communes', id: code }, { hover: true });
  };
  map.on('mousemove', 'communes-fill', (e) => {
    const code = e.features[0]?.properties.code;
    map.getCanvas().style.cursor = 'pointer';
    setHover(code);
    onHover(code, e.point);
  });
  map.on('mouseleave', 'communes-fill', () => {
    map.getCanvas().style.cursor = '';
    setHover(null);
    onHover(null);
  });
  map.on('click', 'communes-fill', (e) => onClick(e.features[0]?.properties.code));
  map.on('moveend', () => {
    updateLabels();
    onMove();
  });

  // City labels as HTML markers (no glyph server needed): biggest communes first, spaced out.
  const byPop = [...communes].sort((a, b) => b.pop - a.pop);
  const markers = new Map();
  function updateLabels() {
    const b = map.getBounds();
    const placed = [];
    const keep = new Set();
    for (const c of byPop) {
      if (placed.length >= MAX_LABELS) break;
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
  map.once('load', updateLabels);

  let selected = null;
  return {
    map,
    whenReady: new Promise((resolve) => map.once('load', resolve)),
    paint(states) {
      for (const [code, s] of states) map.setFeatureState({ source: 'communes', id: code }, s);
    },
    select(code) {
      if (selected) map.setFeatureState({ source: 'communes', id: selected }, { selected: false });
      selected = code;
      if (code) map.setFeatureState({ source: 'communes', id: code }, { selected: true });
    },
    inView(c) {
      return map.getBounds().contains([c.lon, c.lat]);
    },
    project(c) {
      return map.project([c.lon, c.lat]);
    },
    focus(c) {
      map.easeTo({ center: [c.lon, c.lat], zoom: Math.max(map.getZoom(), 10.5) });
    },
    zoomIn: () => map.zoomIn(),
    zoomOut: () => map.zoomOut(),
    reset: () => map.fitBounds(bounds, { padding: 40 }),
  };
}
