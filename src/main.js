import * as maplibregl from '../vendor/maplibre-gl-6.11.2/maplibre-gl.mjs';
import t from './i18n/fr.js';

// Fill static UI copy from src/i18n/fr.js.
for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = t[el.dataset.i18n];
for (const el of document.querySelectorAll('[data-i18n-aria-label]')) {
  el.setAttribute('aria-label', t[el.dataset.i18nAriaLabel]);
}

// Metropolitan France + Corsica.
const FRANCE_BOUNDS = [[-5.5, 41.2], [9.8, 51.2]];

const map = new maplibregl.Map({
  container: 'map',
  style: {
    version: 8,
    sources: {},
    layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#E9E3D7' } }],
  },
  bounds: FRANCE_BOUNDS,
  fitBoundsOptions: { padding: 24 },
  attributionControl: false,
  dragRotate: false,
  pitchWithRotate: false,
  locale: {
    'NavigationControl.ZoomIn': t['map.zoomIn'],
    'NavigationControl.ZoomOut': t['map.zoomOut'],
    'NavigationControl.ResetBearing': t['map.resetBearing'],
  },
});
map.touchZoomRotate.disableRotation();
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
