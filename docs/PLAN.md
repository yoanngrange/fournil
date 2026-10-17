# Fournil — build plan

Work milestone by milestone. Finish and demo each one before starting the next.
Start every milestone on Loire-Atlantique (44), then generalise.

## M0 — Repo skeleton (½ day)
- Folders: `src/` (app), `public/` (static + data), `pipeline/`, `docs/`, `design/`.
- MapLibre GL JS added (npm or a pinned copy in `public/vendor/`), `index.html` showing an empty map.
- GitHub Action that deploys `public/` + `src/` to GitHub Pages.
- **Done when:** the empty map is live on Pages.
- *Done (Oct 2026):* MapLibre 6.11.2 pinned in `public/vendor/` (ES modules, no build step), fonts self-hosted
  in `public/fonts/`. Local preview: `uv run python scripts/serve.py`. Site assembled by `scripts/build_site.sh`.

## M1 — Data pipeline for one département
- `fetch.py` for: COG, ADMIN EXPRESS, populations légales, RP age/sex, séries historiques, Filosofi,
  SIRENE (filtered to dep 44 for speed), BPE, SSMSI, DVF.
- Build every file of DATA.md §4 for dep 44 only (percentiles temporarily computed on 44).
- **Done when:** `python -m pipeline.run --dep 44` writes all outputs and the tests pass.

## M2 — Commune map (dep 44)
- Commune polygons coloured by score; Avoid bins hatched (MapLibre `fill-pattern`).
- Hover tooltip, click → pinned card (as in `design/Zoom.dc.html`).
- Sidebar: range sliders whose bounds follow the visible communes (`map.on('moveend')` +
  `queryRenderedFeatures` or a bbox test on centroids), importance selects, reset.
- Top bar counts, legend, URL state.
- First version of the **Sources & method page** (SPEC §3.5), linked from the sidebar and the card.
- **Done when:** behaviour matches the mockup on dep 44, at 1440 px and 390 px.

## M3 — All of France
- Pipeline `--all`; national percentiles; per-département geometry loaded on demand.
- National view: département choropleth = number of Go communes (computed client-side from
  `communes-index.json` with the current weights), top-6 list, click to zoom.
- Search with autocomplete.
- **Done when:** national view loads < 2 s on throttled 4G; scores identical to M2 for dep 44 after
  switching to national percentiles (colours may differ, that is expected and correct).

## M4 — Commune page
- Route `/commune/{code}` rendered from `commune/{code}.json`; layout as `design/Commune.dc.html`.
- Generated one-line summary (template rules, not AI).
- Pre-render static HTML for all communes at build time (SEO): one command, same locally and in CI,
  output deployed as the Pages artifact and never committed (SPEC §3.4).
- **Done when:** every section works for Clisson (44043), a tiny village with missing Filosofi data,
  and Paris.

## M5 — Delivery mode
- Switch, bakehouse pin, Distance / Contiguous modes (algorithm: `design/logic-reference.js`).
- Reach stats in the sidebar; national view metric switches to "communes without a bakery".
- Adjacency must cross département borders (load neighbour départements' adjacency when needed).
- **Done when:** a 40-commune contiguous block across a département border works.

## M6 — Takeover signal
- RNE ingestion (behind a feature flag until INPI terms are confirmed), aggregated `sell_soon` per commune.
- Takeover preset raises its weight.
- **Done when:** no individual-level data exists anywhere in `public/`.

## M7 — Polish & refresh
- Monthly scheduled pipeline, data vintage shown in the UI, shortlist + compare (up to 3),
  empty/error states, French copy review.

## Later (paid version and partners)
Accounts · Stripe · PDF market study for banks · bakeries-for-sale alerts · opt-in broker / miller leads ·
communes looking for a baker (listings) · van-tour route planning (OSRM / OpenRouteService) ·
B2B access for franchises · overseas départements.
