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
| Population history | INSEE census *séries historiques* (1968 → latest) | For the "population over time" chart. **Growth (decided):** average annual rate between the two census vintages 6 years apart that INSEE itself compares (currently RP 2017 → RP 2023): `((P2023 / P2017)^(1/6) − 1) × 100`, in %/year. |
| Households, housing, second homes, vacant | INSEE census (RP) housing tables | Second-home share matters: tourist communes have strong seasonal demand. |
| Commuting | INSEE census *mobilités professionnelles* (home → work flows) | "% of residents working outside the commune" and main destination. |
| Income, poverty | INSEE **Filosofi**, commune level | Statistical secrecy: **nothing is published under 50 fiscal households and 100 people**; the median is available from that threshold; the full set (incl. detailed breakdowns) generally from 1,000 households or 2,000 people. Expect gaps for small villages. |
| Existing bakeries (count) — **reference** | INSEE **BPE** (Base permanente des équipements) 2025, code **B207 Boulangerie-pâtisserie** | **Decided (Oct 2026): BPE is the count used for scoring.** INSEE cleans it (one point of sale = one equipment), whereas SIRENE also lists head offices, industrial bakeries and dormant establishments still flagged active. |
| Existing bakeries — cross-check | **SIRENE** stock of establishments (`StockEtablissement`), active (`etatAdministratifEtablissement = A`), `activitePrincipaleEtablissement` in **10.71C** (boulangerie et boulangerie-pâtisserie). Also count 10.71D (pâtisserie) and 47.24Z (retail of bread/pastry) separately. | Location by `codeCommuneEtablissement`. Used only to log the gap with BPE and for the "local economy" figures. The quality check compares BPE B207 with SIRENE **10.71C + 10.71D** (closest definition; 46,657 vs 50,675 in Oct 2026, gap 8.6 %). No SIRENE code set reproduces BPE exactly: INSEE cleans BPE. |
| Bakeries, shops, services (count) | INSEE **BPE** | **Verified on BPE 2025:** B207 Boulangerie-pâtisserie, B104 Hypermarché, B105 Supermarché, B201 Supérette, B202 Épicerie, B204 Boucherie charcuterie, B206 Poissonnerie, A504 Restaurant, D307 Pharmacie, D265 Médecin généraliste, A206–A208 poste, E107–E109 gares, C107–C109 écoles, C201/C301–C303 collèges et lycées (full list in `pipeline/config.py`; codes change between vintages). Also schools, pharmacy, doctors, post office, station from BPE. |
| Businesses by sector | SIRENE establishments, grouped by NAF section | For "local economy" bars. |
| Crime | **SSMSI** — *Bases statistiques communale, départementale et régionale de la délinquance enregistrée par la police et la gendarmerie nationales* (data.gouv.fr) | Rates per 1,000 inhabitants by indicator. Small counts are suppressed for small communes → treat as missing. **Decided:** `crime` = burglaries of homes + physical violence outside the family + thefts (armed, violent, non-violent against people), per 1,000 inhabitants, year 2025 (excluding fraud and drug offences, which reflect police activity more than local safety). **Withheld counts:** SSMSI publishes 0 and counts ≥ 5 and withholds 1–4. A withheld indicator counts as 2.5; the commune's value is dropped when that uncertainty exceeds 5 offences per 1,000 inhabitants. Coverage: 23 % of communes nationally, 72 % in dep 44 (vs 7 % if any withheld count made the value missing). Paris, Lyon, Marseille are published per arrondissement and summed from counts. |
| Property prices | **DVF** (Demandes de valeurs foncières), Etalab "géo-DVF" | Median €/m² per commune over the last 3 years, houses and flats separately. Terms forbid re-identifying people or letting search engines index individual sales — **publish aggregates only**. |
| Likely to sell soon | **RNE** (Registre national des entreprises, INPI API): directors of bakery companies with birth month/year | Requires a free INPI account. **VERIFY** INPI reuse terms. Count bakeries whose youngest director is ≥ 60 (configurable). Fallback without RNE: SIRENE company age (`dateCreationUniteLegale` ≥ 25 years) as a weaker signal. **Aggregate per commune only.** |
| Bakery history (openings, closures, takeovers) | **SIRENE** stock, all establishments in 10.71C incl. closed ones | Since 2016. Closure date = `dateDebut` of a closed establishment. **Takeover** = a closure matched with an opening by another SIREN in the same commune within 180 days; same SIREN = a move (ignored). Not in the score. ~1,800 takeovers/year nationally, consistent with BODACC sales. Change of legal form (EI → company) counts as a takeover (documented bias). |
| Price of a bakery business | **BODACC** commercial notices (DILA, OpenDataSoft API `annonces-commerciales`, family `vente`, activity mentions "boulang") | Price parsed from `origineFonds` ("acquis par achat au prix stipulé de …"); purchases only (no contributions in kind, no leases); corrections/cancellations skipped; duplicates (same postcode, price, year) dropped; kept between 5 k€ and 3 M€. Median and quartiles over the last 5 years per département, shown only from **20 sales**, otherwise national. ~96 % of sale notices carry a price; ~1,600 bakery sales/year. Notices name people: **only aggregates leave the pipeline** (`fonds.json`). |
| Businesses by size, main employers | **SIRENE** establishments (`trancheEffectifsEtablissement`) + **StockUniteLegale** (company name, legal form) | Size groups: none / 1–9 / 10–49 / 50–249 / 250+. Main employers: up to 3 establishments with 10+ employees, **legal entities only** (never `categorieJuridique` 1000, sole traders named after a person) and only with `statutDiffusion = O` on both establishment and company. |
| Mayor | **Répertoire national des élus**, maires file (Ministère de l'Intérieur) | Only first name and surname are exported; birth date and occupation in the file are never used. |
| Municipal election 2026 | Ministère de l'Intérieur, results per commune, round 1 (15 March) and round 2 (22 March) | Turnout (% votants), each list's full name, nuance and % of valid votes. Mayor's list = the list with the most council seats in the deciding round. Nuances exist mostly above 3,500 inhabitants. Candidate names are not in the commune file and are not used. |
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

## 6. Implementation notes (M1, October 2026)

What the real files taught us; `pipeline/config.py` holds every URL, vintage and code.

- **Insee now distributes through Melodi** (`https://api.insee.fr/melodi/file/<DATASET>/<FILE>`): zipped CSV in
  long format (one row per geography × measure). Always filter `GEO_OBJECT = COM`: the same code can also be a
  bassin de vie, an aire d'attraction, etc. Datasets used: `DS_POPULATIONS_REFERENCE` (PMUN 2023),
  `DS_RP_SERIE_HISTORIQUE` (1968–2023, also dwellings by occupancy), `DS_RP_POPULATION_PRINC` (sex × age),
  `DS_FILOSOFI_CC` (2023: `MED_SL`, `PR_MD60`), `DS_BPE` (2025).
- These files are already published on the **2026 geography**: no code mapping was needed in Oct 2026.
  The mapping (COG history + arrondissements → commune) still runs and fails the build above 0.1 % unmapped.
- **Age bands** published by sex at commune level are 0–14, 15–24, 25–39, 40–54, 55–64, 65–79, 80+
  (not the 15-year bands of the mockup). The UI uses these.
- **Second homes and vacant dwellings** come from the census history file (2023), no separate housing file.
- **Boundaries:** ADMIN EXPRESS COG CARTO 2026 as GeoParquet (`data.geopf.fr`), no 7z to unpack.
  Simplified with `shapely.coverage_simplify` (40 m) on the whole country at once, so neighbouring communes
  and départements keep identical borders. Centre point = town hall (chef-lieu layer), or a point inside the
  polygon for the 6 uninhabited Meuse communes that have none.
- **SIRENE** is no longer split by département: the national stock (Parquet, 2.2 GB) is read with column and
  row filters. Paris/Lyon/Marseille establishments carry arrondissement codes and are summed into the commune.
- **Percentiles are always national**, even when only some départements are exported
  (`--dep 44` still ranks against all of France), so colours will not shift in M3.
- **Uninhabited communes** (population 0) are not scored.
