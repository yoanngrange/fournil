# Fournil — data guide

All sources below are French public open data. Most are under the **Licence Ouverte / Open Licence 2.0**
(Etalab), which requires attribution (source + date) — the UI footer and `meta.json` handle that.
Items marked **VERIFY** were not confirmed when this guide was written; check them first.

## 1. Join key and geography

- Key: **INSEE commune code** (`code_insee`, 5 chars). Corsica uses `2A…` / `2B…`.
- Communes merge every year ("communes nouvelles"). Freeze one **COG** vintage per run and map any
  older codes with INSEE's *table de passage* (COG history). Log every unmapped code; fail the build if > 0.1 %.
- Paris, Lyon and Marseille: keep the whole commune for the MVP (arrondissements later).
- **Boundaries:** IGN **ADMIN EXPRESS COG CARTO** (generalised, made for maps; matches the COG vintage).
  Simplify further per zoom need (e.g. `mapshaper -simplify 10% keep-shapes`). The mockup used a community
  GeoJSON derived from IGN data (github.com/gregoiredavid/france-geojson); fine for prototyping only.
- **Adjacency** (for the contiguous delivery mode): computed in the pipeline with geopandas —
  two communes are neighbours if their boundaries share a line (not just a point). Store as a list of codes.
- **Centroids:** use a point guaranteed inside the polygon (`representative_point()`), or the town-hall
  coordinates if available. Distances = haversine in km.

## 2. Sources by criterion

| Need | Source | Notes |
|---|---|---|
| Population (current) | INSEE *Populations légales* (yearly) | Official population per commune. |
| Age pyramid | INSEE census (RP), population by sex and 5-year age band, commune level | Group into 0–14, 15–29, 30–44, 45–59, 60–74, 75+ for the card; keep 5-year bands for the page. |
| Population history | INSEE census *séries historiques* (1968 → latest) | For the "population over time" chart and the yearly growth rate (last two censuses). |
| Households, housing, second homes, vacant | INSEE census (RP) housing tables | Second-home share matters: tourist communes have strong seasonal demand. |
| Commuting | INSEE census *mobilités professionnelles* (home → work flows) | "% of residents working outside the commune" and main destination. |
| Income, poverty | INSEE **Filosofi**, commune level | Statistical secrecy: **nothing is published under 50 fiscal households and 100 people**; the median is available from that threshold; the full set (incl. detailed breakdowns) generally from 1,000 households or 2,000 people. Expect gaps for small villages. |
| Existing bakeries (count) | **SIRENE** stock of establishments (`StockEtablissement`), active (`etatAdministratifEtablissement = A`), `activitePrincipaleEtablissement` in **10.71C** (boulangerie et boulangerie-pâtisserie). Also count 10.71D (pâtisserie) and 47.24Z (retail of bread/pastry) separately. | Location by `codeCommuneEtablissement`. Cross-check with BPE. |
| Bakeries, shops, services (count) | INSEE **BPE** (Base permanente des équipements) | Codes in the 2020 list: **B203 Boulangerie**, B101 Hypermarché, B102 Supermarché, B202 Épicerie, B204 Boucherie charcuterie, B206 Poissonnerie. **VERIFY** codes in the vintage you download (nomenclature changes). Also schools, pharmacy, doctors, post office, station from BPE. |
| Businesses by sector | SIRENE establishments, grouped by NAF section | For "local economy" bars. |
| Crime | **SSMSI** — *Bases statistiques communale, départementale et régionale de la délinquance enregistrée par la police et la gendarmerie nationales* (data.gouv.fr) | Rates per 1,000 inhabitants by indicator. Small counts are suppressed for small communes → treat as missing. Choose a few indicators (burglary, violence, theft) and document the choice. |
| Property prices | **DVF** (Demandes de valeurs foncières), Etalab "géo-DVF" | Median €/m² per commune over the last 3 years, houses and flats separately. Terms forbid re-identifying people or letting search engines index individual sales — **publish aggregates only**. |
| Likely to sell soon | **RNE** (Registre national des entreprises, INPI API): directors of bakery companies with birth month/year | Requires a free INPI account. **VERIFY** INPI reuse terms. Count bakeries whose youngest director is ≥ 60 (configurable). Fallback without RNE: SIRENE company age (`dateCreationUniteLegale` ≥ 25 years) as a weaker signal. **Aggregate per commune only.** |
| Tourism (optional) | INSEE tourist accommodation capacity by commune | Beds in hotels/campsites; later. |
| Not available nationally | market days, foot traffic, commercial rents | Keep in the backlog. |

## 3. Pipeline (`pipeline/`)

```
pipeline/
  fetch.py        # download each source into raw/ (cached, with checksums + source dates)
  cog.py          # load COG, build code mapping for merged communes
  build_geo.py    # boundaries → simplified per-département GeoJSON, centroids, adjacency
  build_stats.py  # join all sources on code_insee, compute indicators
  score.py        # national percentile ranks per criterion
  export.py       # write public/data/*
  tests/          # row counts, uniqueness, value ranges, sample commune snapshot (44043 Clisson)
```

Run locally: `python -m pipeline.run --dep 44` (one département) or `--all`.
CI: GitHub Action monthly (SIRENE changes monthly; other sources yearly) → build → deploy Pages.

## 4. Output files (`public/data/`)

```
meta.json                    { cog_year, built_at, sources: [{id, name, vintage, url, licence}] }
departements.geojson         simplified boundaries + {code, name, n_communes}
communes-index.json          one row per commune, compact columnar JSON (~35k rows):
                               code, name, dep, lat, lon, pop, bakeries,
                               v:   {per_bakery, income, growth, crime, sell_soon}   // raw values, null if missing
                               pct: {per_bakery, income, growth, crime, sell_soon}   // 0..1000 ints, already inverted where lower is better
geo/{dep}.geojson            commune polygons for one département (loaded on zoom)
adj/{dep}.json               { code: [neighbour codes] }   // may include codes from adjacent départements
commune/{code}.json          everything for the commune page (pyramid, history, sectors, amenities,
                               comparisons with département and France, nearby communes)
```

`communes-index.json` drives search, the national counts per département and the scores, so keep it lean
(target ≤ 1.5 MB raw, ≤ 400 kB gzipped). Use short keys and integers.

## 5. Quality checks (fail the build)
- Every commune in the COG appears exactly once in `communes-index.json`.
- Population total within 0.5 % of the official national total.
- Bakery count from SIRENE vs BPE differs by < 15 % nationally (log the per-département gap).
- Percentiles: min 0, max 1000 for every criterion that has values.
- Snapshot test: commune 44043 values change only when sources change.
