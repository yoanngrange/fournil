# Fournyl — design system ("fiche de fournil")

The look of a printed bakery work sheet: almost-white flour paper, black ink rules, typewritten figures,
one red stamp. Flat, square, typographic. The opposite of the default "SaaS" look (rounded cards, soft
shadows, gradients, purple). Tokens live in `src/styles.css` (`:root`); this file explains the rules.

## Principles

1. **Ink on paper.** Content sits on paper, separated by ink rules, not by shadows or rounded boxes.
2. **One strong colour.** Red (`--rouge`) is the brand: the mark, the rule under the logo, the "Bêta" stamp,
   the shortlist star, the callout edge. It never encodes data, so the map can never be read as "red = bad".
3. **The map is calm.** Data colours are a blue ↔ kraft scale (no red/green, no "Christmas tree").
   Blue = favourable, kraft = unfavourable *and hatched*, warm grey = neutral. Colour-blind safe.
4. **Figures are typed.** Every number is set in Courier Prime (monospace, tabular), like a delivery note.
5. **Square corners.** Radius 0 everywhere. The only "depth" is a hard 4 px ink offset (`--lift`) on sheets
   that float over the map (search, breadcrumb, card, notice). Never a blurred shadow.

## Colour

| Token | Hex | Use | Contrast on `--paper` |
|---|---|---|---|
| `--paper` | `#FAF8F3` | Page background (farine) | — |
| `--paper-2` | `#FFFEFB` | Sheets: sidebar, card, panels | — |
| `--paper-3` | `#F0EBE1` | Wells, hover, segmented tracks | — |
| `--ink` | `#1C1A17` | Text, rules, borders, selected buttons | 16:1 |
| `--ink-2` | `#4A4339` | Secondary text, labels | 8.9:1 |
| `--ink-3` | `#6B6255` | Captions, sources | 5.4:1 |
| `--rule-soft` | `#DCD3C2` | Hairlines inside a sheet | decorative |
| `--rouge` | `#B42318` | Brand only (see principle 2) | 6.3:1 |
| `--bleu` | `#1E3F8A` | Links, focus ring, Go text | 9:1 |
| `--kraft` | `#D2B98E` | Avoid fill (always hatched) | decorative |

Map scale (`src/lib/scoring.js` `BIN_COLOURS`, `src/map.js` `DEP_SCALE`):

| Bin | Hex | Notes |
|---|---|---|
| ≥ 75 | `#1E3F8A` | |
| 60–74 | `#6A8BCB` | |
| 40–59 | `#EAE6DC` | |
| 25–39 | `#D2B98E` | hatched |
| < 25 | `#A9844F` | hatched |
| filtered out / no score | `#F7F5F0` | |
| Delivery: no bakery in reach | `#1E3F8A` | the opportunity |
| Delivery: has a bakery | `#D8CDB6` | |
| Départements (5 quantiles) | `#EEF1F7` → `#1E3F8A` | |

Hatch: 2 px lines of `#4A3414` at 60 %, 45°, every 6–7 px (CSS `--hatch`, MapLibre `hatchImage()`).

## Type

| Role | Font | Where |
|---|---|---|
| Display | **Big Shoulders Display** 800, uppercase, +0.02–0.04 em | Logo, page and commune titles, card name, section titles |
| Text | **Atkinson Hyperlegible** 400/700 | Everything else (designed for low-vision readers) |
| Figures and labels | **Courier Prime** 400/700 | Numbers, the "label" style (12 px caps, +0.08 em) for section labels and table heads |

All three are SIL OFL, self-hosted in `public/fonts/` (Latin subset, ~100 kB total).

## Components

- **Label** (`.label`, sidebar `h2`, table heads): Courier Prime 12 px caps, `--ink-2`.
- **Sheet**: `--paper-2`, 1.5 px ink border (`--line`), optional `--lift`.
- **Segmented control** (`.mode-switch`, `.segmented`): one ink-bordered box, ink dividers; the pressed
  option is ink with paper text. Used for *En boutique / En tournée* and *Distance / Communes voisines*.
- **Primary button** (`.btn`, `.card-page`, `.pg-button`): ink fill, paper text; hover turns blue.
  Ghost button: transparent with ink border.
- **Figures grid** (`.kpis`, `.pg-tiles`, `.facts`): a ruled table, label in Courier caps over a large figure.
- **Callout** (`.callout`): sheet with a 6 px red left edge. For warnings and disclaimers only.
- **Slider**: ink track, square paper thumbs, value tags in ink with paper text.
- **Focus**: 3 px blue outline, 2 px offset, everywhere.

## Mark

`public/img/mark.svg`: a red square, a white loaf with three red scoring cuts (*grignes*) and a white
hearth line (*la sole*). The same drawing is the favicon and the app icon (`icon-*.png`, `icon-maskable-512.png`
with a safe zone). Wordmark: "FOURNYL" in Big Shoulders Display 800.

## Layout

- Desktop (> 720 px): sidebar 380 px on the left, map on the right, floating sheets on the map.
- Phone (≤ 720 px): map full screen. Top bar = mark, search (behind an icon), "around me", then the
  *En boutique / En tournée* switch. Bottom sheet = ranking (+ delivery settings in round mode). No sliders.
  Selecting a commune shows a strip (name, score, "Voir la fiche complète") and the full details open on the
  commune's own page: a real URL that can be shared, bookmarked and reached with the back button.
