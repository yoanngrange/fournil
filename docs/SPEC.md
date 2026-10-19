# Fournil — product spec (v0.1, October 2026)

## 1. Problem and users

A baker who wants to open or take over a bakery has to guess where demand is strong,
competition is weak and the area is pleasant to live in. The data exists (INSEE, SIRENE, etc.)
but is scattered and hard to read. Fournil turns it into one map and one page per commune.

**Primary user:** a baker (newly qualified or experienced) choosing a location, often willing to move.
**Three bakery models:**
1. **New opening** — wants many inhabitants per bakery, growing population, decent income.
2. **Takeover** — same, plus bakeries whose owners are near retirement.
3. **Mobile / delivery** — one bakehouse serving several villages without a bakery.

**Later users (paid / B2B, not in MVP):** flour millers, franchises, business brokers, communes
looking for a baker, training centres (CAP, INBP, Chambres de métiers).

## 2. MVP scope

In: national map, commune map with filters and weights, delivery mode, commune page, search,
shareable URL state, local shortlist, all of metropolitan France + Corsica.

Out (later): accounts, payments, PDF market study, broker contact, bakeries-for-sale alerts,
van-tour route planning, overseas départements, market days, shop rents, foot traffic.

## 3. Screens

Mockups in `design/` (see `design/README.md`). Layout: left sidebar 380 px, map fills the rest.

### 3.1 National view (`design/Main.dc.html`)
- Département boundaries, coloured on a 5-step green sequential scale by the **number of communes
  scored Go** (not an average score — an average hides strong towns next to weak ones).
- With the delivery switch on, the metric becomes **number of communes without a bakery**.
- Hover tooltip: département name, metric value, number of communes.
- Click a département → zoom to it and switch to commune view.
- Sidebar: intro, delivery switch, top 6 départements for the current metric, legend.

### 3.2 Commune view (`design/Zoom.dc.html`)
- Real commune boundaries. Pan (drag), zoom (wheel, + / − / reset buttons).
- **Colour = national score** (see §4), so a commune never changes colour when panning.
  Bins: ≥75 dark green `#4D9221`, 60–74 green `#7FBC41` (Go) · 40–59 neutral `#ECEAE1` (Maybe) ·
  25–39 pink `#DE77AE`, <25 magenta `#C51B7D` (Avoid, **plus diagonal hatching**) · filtered out `#D9D2C5`.
- Top bar: breadcrumb, counts in view (go / avoid / filtered out), search, zoom buttons.
- Hover: small tooltip (name, score + label, population).
- Click: pinned dark card on the right — score, 6 key figures, age pyramid, local economy,
  score breakdown, "Open commune page →", shortlist star.
- Floating legend bottom-left (changes in delivery mode).

**Sidebar — filters & priorities.** One row per criterion:
- A **two-handle range slider in real units**. Its min and max are the min and max of the
  communes currently **on screen**, recomputed live on pan/zoom. The user's chosen range is kept
  in real units and clamped to the visible bounds for display.
- ~~An importance select~~ **Decided (Oct 2026): no user weights.** Weights are part of our scoring recipe,
  fixed and the same for everyone (per_bakery 3, income 2, growth 2, crime 1), explained on the sources page.
  Users only filter. The current value of each handle is shown in a bubble above it; the min and max of the
  communes on screen stay visible below the track.
- "Reset filters" link.
- Communes outside any active range are shown as "filtered out" and excluded from counts.
- *Implemented (M2):* a handle left at the end of its slider is **open** (no bound on that side), so panning
  to bigger or smaller communes does not silently filter them out. Population and inhabitants per bakery
  use a **logarithmic** slider (a city and villages share one range). A missing value never filters out.
- *French labels:* Go / Maybe / Avoid are shown as **Favorable / À étudier / Défavorable**.

Criteria (MVP):

| key | label (FR UI) | unit | better | weight (our recipe) |
|---|---|---|---|---|
| `pop` | Population | inhabitants | — (filter only) | — |
| `per_bakery` | Habitants par boulangerie | inhabitants | higher | High (3) |
| `income` | Revenu médian | €/year/UC | higher | Medium (2) |
| `growth` | Évolution de la population | %/year | higher | Medium (2) |
| `crime` | Taux de délinquance | offences /1,000 | lower | Low (1), on by default |
| `sell_soon` | Boulangeries à reprendre bientôt | count | higher | Low (1) — High in takeover preset |

### 3.3 Delivery mode (switch "Boulangerie mobile ou livraison")
- User clicks a commune to place the **bakehouse** (marked with a dark pin).
- Segmented control **Distance | Communes voisines**:
  - Distance: slider 5–30 km; all communes whose centroid is within that distance (dashed circle drawn).
  - Contiguous: slider 2–40 communes; grows **one connected block of touching communes**, starting from the
    bakehouse and always adding the bordering commune nearest to it (algorithm in `design/logic-reference.js`).
- Map colours in range: **no bakery = green (opportunity)**, has a bakery = neutral, outside range = faded.
- Sidebar shows: communes in range, communes without a bakery, inhabitants reached, inhabitants with no bakery,
  and (contiguous mode) distance to the furthest commune.

### 3.4 Commune page (`design/Commune.dc.html`, route `/commune/{code_insee}`)
Header: breadcrumb, shortlist, "Export market study (PDF)" (locked, Pro, later).
Hero: name, INSEE code, département, region, distance to nearest big city; score tile + label;
one-sentence summary generated from the data; 6 KPI tiles; locator map (commune + 2 rings of neighbours,
neighbours shaded by "has a bakery").
Sections: Why this score (national percentile per criterion + weight) · Who lives here (age pyramid,
under-15 and 75+ shares) · Population over time (census series since 1968, hover per point) ·
Competition (bakeries here, within 10 km, villages with none, likely to sell soon within 10 km, supermarkets,
table of nearest communes) · Local economy (SIRENE establishments by sector, food shops, cafés, jobs) ·
Income & housing (median vs département vs France, poverty rate, second homes, vacant housing, price €/m²) ·
Safety & services (crime vs département vs France, schools, pharmacy, doctors, post office, station; market day "not in open data yet") ·
Next steps (Pro teasers: bank study, bakeries for sale; opt-in "put me in touch with a broker") · Sources footer.

Pre-render commune pages as static HTML at build time: they are valuable for SEO
("boulangerie à reprendre {commune}"). GitHub Pages has no URL rewriting, so `/commune/{code}/index.html`
must exist as a file. One build command generates all ~35k pages (≈ 10 kB each, ≈ 350 MB, under the
1 GB Pages limit); it runs the same way locally and in the GitHub Action. The pages are deployed as the
Pages artifact and **never committed** to git (a monthly refresh would otherwise add ~35k files to history).

### 3.5 Sources & method page (route `/sources/`)
One page, linked from the sidebar, every card and the commune page footer. In French, plain language.
- **Sources:** for each dataset, name, producer, vintage, licence, link, what we use it for (from `meta.json`).
- **Choices:** every scoring rule and why — national percentiles, weights, the no-bakery rule, the bakery count
  source (BPE), the growth definition, the crime indicators, the "likely to sell" signal and its privacy rule.
- **Potential biases and limits:** statistical secrecy on small communes (missing ≠ 0, criterion dropped),
  BPE vs SIRENE gaps, supermarket in-store bakeries not counted as bakeries, crime recorded where reported
  (tourist and commuter communes look worse), census lag (population is 3 years old), commune mergers,
  seasonal population not captured, Paris/Lyon/Marseille kept whole.
Kept up to date with every milestone that adds or changes a criterion.

## 4. Scoring (decided)

- **National, absolute.** For each criterion, precompute each commune's **percentile rank among all French
  communes** in the pipeline (`0..1`, ties = mid-rank). Invert for "lower is better" criteria.
- Client computes `score = round(100 × Σ(wᵢ × pᵢ) / Σ(wᵢ))` over criteria with weight > 0 **and a value**.
- Weights are fixed by us (see §3.2), not set by users; percentiles never change with the view.
  Future presets (takeover, mobile) would be alternative recipes chosen by us, not free weights.
- **Inhabitants per bakery** (revised Oct 19, 2026): `per_bakery = population / bakeries`, the real figure the
  user expects; communes with no bakery have no value (shown "aucune boulangerie", ignored by that slider).
  *(An Oct 17 version used `population / (bakeries + 1)`, "yours included"; dropped because the displayed figure
  no longer matched what users read.)*
- **No-bakery boost:** for ranking, a commune with **0 bakeries** counts as `population × NO_BAKERY_BOOST`
  (pipeline constant, **3**), so it ranks 3× above a commune of the same size with one bakery. The boost scales
  with population, so a 60-inhabitant hamlet stays low.
- Category: Go ≥ 60, Maybe 40–59, Avoid < 40.
- Presets (open question, §7): New opening, Takeover (sell_soon = High), Mobile.

## 5. Other MVP features
- **Search:** commune name autocomplete (accent-insensitive, handles "Saint" / "St"), jumps map + opens card.
- **URL state:** view, filters, weights, mode, selected commune encoded in the query string → shareable links.
- **Shortlist:** star from card or page, stored in `localStorage`, simple list + compare up to 3 (stretch).
- **Responsive:** on phones, sidebar becomes a bottom sheet; card becomes a full-screen sheet.

## 6. Non-functional
- First load < 2 s on 4G for the national view (national file ≤ 300 kB gzipped).
- Commune geometry loaded per département on demand.
- Works offline-ish after first load is a nice-to-have, not required.

## 7. Open questions (ask Yoann before building these)
1. Product name and domain (Fournil is a working name).
2. Start with 3 onboarding questions (model, where, type of place) or go straight to the map with presets?
   *For the prototype: straight to the map with the "New opening" preset.*
3. Takeover and new opening as presets of one score, or two separate scores?
4. Which reference city to show as "distance to …" on the commune page (nearest city > 50k?).
5. ~~Is the crime criterion on by default?~~ **Decided:** yes, weight Low (1).
