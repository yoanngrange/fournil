# Design reference

These mockups were made on a Claude design canvas (link held by Yoann). The `.dc.html` files need that
canvas runtime (`support.js`) to run, so **read them as reference, don't serve them**:
layout, copy, inline styles and the logic in their `<script type="text/x-dc">` blocks are all readable.
**All numbers in them are samples.** Commune boundaries in `Zoom.dc.html` are real (Loire-Atlantique).

| File | Screen |
|---|---|
| `Main.dc.html` | National view: départements coloured by number of Go communes |
| `Zoom.dc.html` | Commune view: pan/zoom, live filter ranges, weights, delivery mode, hover tooltip, pinned card |
| `Commune.dc.html` | Commune page (Clisson, 44043) — long scrolling page |
| `logic-reference.js` | Clean versions of the scoring, filter and delivery algorithms |

## Tokens

**Fonts:** Fraunces (display, 500/700) · Public Sans (UI, 400–700). Both on Google Fonts; self-host in production.

**Neutrals:** page `#F4EFE6` · sidebar `#FBF8F2` · surface `#FFFDF8` · map background `#E9E3D7` ·
border `#E3DACB` / `#D8CDBB` · text `#1F1B16` · secondary `#5A5247` · muted `#6E655A` ·
dark card `#1F1B16` with text `#F4EFE6` · accent link `#7A4B12` · action green `#3D6B1E`.

**Score bins (diverging, colour-blind tested):** `#4D9221` ≥75 · `#7FBC41` 60–74 · `#ECEAE1` 40–59 ·
`#DE77AE` 25–39 · `#C51B7D` <25 · filtered out `#D9D2C5`. Avoid bins also get a 45° hatch
(`#6E0140` at 55 % opacity, 2 px lines every 7 px).

**National sequential scale:** `#F1F4E8` `#D3E8B5` `#A9D27E` `#6FAE45` `#3F7F1F` (quintiles).

**Age pyramid:** men `#3A78B8`, women `#C47A3A` (passed CVD and contrast checks on light surfaces).

**Shape:** radius 10 px (controls), 12–16 px (cards); touch targets ≥ 44 px; sidebar 380 px.
