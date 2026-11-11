"""Generate the static pages behind human-readable URLs (docs/SPEC.md §3.6).

    /                                   France (index.html)
    /loire-atlantique/                  département: the map, centred on it
    /loire-atlantique/clisson-44043/    commune page (rendered by src/commune.js from data/commune/44043.json)

Pages are written into the assembled site (`_site/` by scripts/build_site.sh), never into git.
The development server renders the same pages on the fly (scripts/serve.py).

    uv run python -m pipeline.pages _site
"""

import html
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from pipeline.config import ANALYTICS_TOKEN, OUT, ROOT, SITE_URL

TEMPLATE = Path(__file__).parent / "templates" / "commune.html"
FR = ROOT / "src" / "i18n" / "fr.js"


def slugify(name: str) -> str:
    """'L'Abergement-Clémenciat' -> 'l-abergement-clemenciat'. Mirror of src/lib/slug.js."""
    s = name.lower().replace("œ", "oe").replace("æ", "ae")
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def dep_path(dep_name: str) -> str:
    return f"{slugify(dep_name)}/"


def commune_path(dep_name: str, name: str, code: str) -> str:
    return f"{slugify(dep_name)}/{slugify(name)}-{code.lower()}/"


def strings() -> dict:
    """Single-line entries of src/i18n/fr.js (UI copy lives there, for pages too)."""
    out = {}
    for m in re.finditer(r"^\s*'([\w.]+)':\s*'((?:[^'\\]|\\.)*)',\s*$", FR.read_text(encoding="utf-8"), re.M):
        out[m.group(1)] = m.group(2).replace("\\'", "'")
    return out


def analytics_tag(token: str | None = None) -> str:
    """Cloudflare Web Analytics beacon (cookieless), or nothing when no token is configured."""
    token = ANALYTICS_TOKEN if token is None else token
    if not token:
        return ""
    return (
        "<script defer src='https://static.cloudflareinsights.com/beacon.min.js' "
        f"data-cf-beacon='{{\"token\": \"{html.escape(token)}\"}}'></script>"
    )


# Text pages copied from public/ that carry the <!-- analytics --> marker.
STATIC_PAGES = ["index.html", "sources/index.html", "infos-legales/index.html", "ma-selection/index.html"]
# Footer links (mirror of LINKS in src/lib/chrome.js): href, fr.js key.
FOOTER_LINKS = [("ma-selection/", "sel.link"), ("sources/", "sources.link"), ("infos-legales/#donnees", "updates.link"), ("infos-legales/", "legal.link")]


def _fill(template: str, **params) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(params.get(m.group(1), m.group(0))), template)


def _int(n) -> str:
    return f"{int(round(n)):,}".replace(",", " ")


def at_place(name: str) -> str:
    """French 'à' + commune name: 'à Clisson', 'au Mans', 'aux Sables-d'Olonne', 'à La Baule'."""
    if name.startswith("Le "):
        return "au " + name[3:]
    if name.startswith("Les "):
        return "aux " + name[4:]
    return "à " + name


# Scoring recipe: mirror of CRITERIA in src/lib/scoring.js (percentiles 0..1000, missing values skipped).
WEIGHTS = {"per_bakery": 3, "income": 2, "growth": 2, "crime": 1}


def default_score(pct: dict) -> int | None:
    num = den = 0
    for key, w in WEIGHTS.items():
        p = pct.get(key)
        if p is None:
            continue
        num += w * p / 1000
        den += w
    return math.floor(100 * num / den + 0.5) if den else None  # Math.round, not banker's rounding


def json_ld(data: dict) -> str:
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{text}</script>'


def breadcrumb(items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": url} for i, (name, url) in enumerate(items)
        ],
    }


class Site:
    """Everything needed to render pages: index of communes, département names, UI strings."""

    def __init__(self, data_dir: Path = OUT):
        self.data = data_dir
        index = json.loads((data_dir / "communes-index.json").read_text())
        deps = json.loads((data_dir / "departements.geojson").read_text())
        self.dep_names = {f["properties"]["code"]: f["properties"]["name"] for f in deps["features"]}
        self.exported = set(json.loads((data_dir / "meta.json").read_text())["departements"])
        self.communes = {
            code: {
                "name": index["name"][i],
                "dep": index["dep"][i],
                "pop": index["pop"][i],
                "bakeries": index["bakeries"][i],
                "income": index["v"]["income"][i],
                "cp": (index.get("cp") or [""] * len(index["code"]))[i].split(" ")[0],
                "score": default_score({k: index["pct"][k][i] for k in WEIGHTS if k in index["pct"]}),
            }
            for i, code in enumerate(index["code"])
        }
        self.t = strings()
        self.built_at = json.loads((data_dir / "meta.json").read_text()).get("built_at", "")
        self.root_path = urlparse(SITE_URL).path  # "/fournyl/"
        self.template = TEMPLATE.read_text(encoding="utf-8")
        self.index_html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")

    # --- pages ---

    def commune_page(self, code: str) -> str:
        c = self.communes[code]
        t = self.t
        dep_name = self.dep_names[c["dep"]]
        bakeries = (
            t["seo.bakeries.none"] if c["bakeries"] == 0
            else t["seo.bakeries.one"] if c["bakeries"] == 1
            else _fill(t["seo.bakeries.many"], n=_int(c["bakeries"]))
        )
        income = f"{_int(c['income'])} €" if c["income"] is not None else t["seo.income.none"]
        score = f"{c['score']}/100" if c["score"] is not None else t["seo.score.none"]
        title = _fill(t["seo.commune.title"], at=at_place(c["name"]), cp=c["cp"] or c["dep"])
        description = _fill(
            t["seo.commune.description"], at=at_place(c["name"]), dep=dep_name, pop=_int(c["pop"]),
            bakeries=bakeries, income=income, score=score,
        )
        canonical = SITE_URL + commune_path(dep_name, c["name"], code)
        params = {
            "base": "../../",
            "title": title,
            "description": description,
            "canonical": canonical,
            "code": code,
            "name": c["name"],
            "dep_name": dep_name,
            "dep_path": dep_path(dep_name),
            "t_france": t["map.france"],
            "t_breadcrumb": t["map.breadcrumb"],
        }
        seo = self.social(title, description, canonical) + "\n  " + json_ld(breadcrumb([
            ("France", SITE_URL),
            (dep_name, SITE_URL + dep_path(dep_name)),
            (c["name"], canonical),
        ]))
        raw = {"footer": self.footer(), "analytics": analytics_tag(), "seo": seo}
        return re.sub(
            r"\{\{(\w+)\}\}",
            lambda m: raw[m.group(1)] if m.group(1) in raw else html.escape(str(params[m.group(1)]), quote=True),
            self.template,
        )

    def social(self, title: str, description: str, url: str) -> str:
        """Open Graph and Twitter tags: the preview shown when a page is shared."""
        tags = [
            ("property", "og:type", "website"),
            ("property", "og:site_name", "Fournyl"),
            ("property", "og:locale", "fr_FR"),
            ("property", "og:title", title),
            ("property", "og:description", description),
            ("property", "og:url", url),
            ("property", "og:image", SITE_URL + "img/og.png"),
            ("property", "og:image:width", "1200"),
            ("property", "og:image:height", "630"),
            ("property", "og:image:alt", self.t["seo.og.alt"]),
            ("name", "twitter:card", "summary_large_image"),
        ]
        return "\n  ".join(f'<meta {k}="{n}" content="{html.escape(v, quote=True)}">' for k, n, v in tags)

    def places(self, title: str, links: list[tuple[str, str]]) -> str:
        """Collapsible list of links in the map sidebar: keyboard access to every place, and crawlable links."""
        items = "".join(f'<li><a href="{href}">{html.escape(name)}</a></li>' for href, name in links)
        return f'<details class="site-places"><summary>{html.escape(title)}</summary><ul>{items}</ul></details>'

    def dep_links(self) -> str:
        deps = sorted(self.exported, key=lambda d: (len(d) > 2, d))
        return self.places(self.t["seo.places.deps"], [(dep_path(self.dep_names[d]), f"{self.dep_names[d]} ({d})") for d in deps])

    def home_page(self, page: str) -> str:
        """public/index.html with the national title, description, social tags, structured data and département links."""
        t = self.t
        title = t["seo.home.title"]
        desc = _fill(t["seo.home.description"], n=_int(len(self.communes)))
        ld = json_ld({
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebSite", "@id": SITE_URL + "#site", "url": SITE_URL, "name": "Fournyl",
                    "description": desc, "inLanguage": "fr-FR", "publisher": {"@id": SITE_URL + "#publisher"},
                },
                {
                    "@type": "Organization", "@id": SITE_URL + "#publisher", "name": "Vraie Forêt",
                    "url": "https://vraieforet.com",
                    "address": {
                        "@type": "PostalAddress", "streetAddress": "4 allée Beau Rivage",
                        "postalCode": "44200", "addressLocality": "Nantes", "addressCountry": "FR",
                    },
                },
            ],
        })
        extra = f'<link rel="canonical" href="{SITE_URL}">\n  {self.social(title, desc, SITE_URL)}\n  {ld}'
        return self._head(page, title, desc, extra).replace("<!-- places -->", self.dep_links())

    def _head(self, page: str, title: str, desc: str, extra: str) -> str:
        """Set <title> and the description, drop the shell's generic social tags, add `extra` to <head>."""
        page = re.sub(r"<title>.*?</title>", lambda _: f"<title>{html.escape(title)}</title>", page, count=1)
        page = re.sub(
            r'<meta name="description" content="[^"]*">',
            lambda _: f'<meta name="description" content="{html.escape(desc, quote=True)}">', page, count=1,
        )
        page = re.sub(r'\n\s*<meta property="og:[^"]*" content="[^"]*">', "", page)
        return page.replace("</head>", f"  {extra}\n</head>", 1)

    def footer(self) -> str:
        t = self.t
        items = "".join(f'<li><a href="{href}">{html.escape(t[key])}</a></li>' for href, key in FOOTER_LINKS)
        return (
            f'<footer class="site-footer"><div class="site-footer-inner"><ul>{items}</ul>'
            f"<p>{html.escape(t['footer.text'])}</p></div></footer>"
        )

    def dep_page(self, dep: str) -> str:
        """The map app, with relative URLs resolved from the site root and the département preselected."""
        name = self.dep_names[dep]
        n = sum(1 for c in self.communes.values() if c["dep"] == dep)
        title = _fill(self.t["seo.dep.title"], dep=name, code=dep)
        desc = _fill(self.t["seo.dep.description"], dep=name, code=dep, n=_int(n))
        url = SITE_URL + dep_path(name)
        head = f'<base href="../">\n  <meta name="fournyl-dep" content="{dep}">'
        page = self.index_html.replace('<base href="./">', head, 1).replace("<!-- analytics -->", analytics_tag())
        extra = (
            f'<link rel="canonical" href="{url}">\n  {self.social(title, desc, url)}\n  '
            + json_ld(breadcrumb([("France", SITE_URL), (name, url)]))
        )
        communes = sorted(
            ((code, c) for code, c in self.communes.items() if c["dep"] == dep),
            key=lambda x: unicodedata.normalize("NFD", x[1]["name"]).encode("ascii", "ignore").decode().lower(),
        )
        links = self.places(
            _fill(self.t["seo.places.communes"], dep=name),
            [(commune_path(name, c["name"], code), c["name"]) for code, c in communes],
        )
        return self._head(page, title, desc, extra).replace("<!-- places -->", links)

    def not_found_page(self) -> str:
        """404.html: GitHub Pages serves it for any unknown path; src/notfound.js redirects old or misspelt URLs."""
        t = self.t
        return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <base href="{self.root_path}">
  <title>{html.escape(t['seo.notFound.title'])}</title>
  <meta name="robots" content="noindex">
  <link rel="stylesheet" href="src/styles.css">
  <script type="module" src="src/notfound.js"></script>
</head>
<body class="doc">
  <main class="doc-main">
    <h1>{html.escape(t['seo.notFound.text'])}</h1>
    <p id="status">{html.escape(t['seo.notFound.redirect'])}</p>
    <p><a href="./">{html.escape(t['seo.backHome'])}</a></p>
  </main>
</body>
</html>
"""

    def sitemap(self) -> str:
        urls = [SITE_URL, SITE_URL + "sources/", SITE_URL + "infos-legales/"]
        urls += [SITE_URL + dep_path(self.dep_names[d]) for d in sorted(self.exported)]
        urls += [
            SITE_URL + commune_path(self.dep_names[c["dep"]], c["name"], code)
            for code, c in sorted(self.communes.items())
        ]
        day = self.built_at[:10]
        lastmod = f"<lastmod>{day}</lastmod>" if day else ""
        body = "\n".join(f"  <url><loc>{html.escape(u)}</loc>{lastmod}</url>" for u in urls)
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n'

    def llms_txt(self) -> str:
        """llms.txt (https://llmstxt.org): what the site is, for AI assistants and answer engines."""
        deps = sorted(self.exported, key=lambda d: (len(d) > 2, d))
        dep_lines = "\n".join(f"- [{self.dep_names[d]} ({d})]({SITE_URL}{dep_path(self.dep_names[d])})" for d in deps)
        return f"""# Fournyl

> Fournyl ({SITE_URL}) is a free French website that helps bakers choose where to open (create) or take over
> a bakery in France ("créer ou reprendre une boulangerie", "étude de marché boulangerie"). Every French
> commune ({_int(len(self.communes))} communes) gets a score out of 100 computed from public open data.

The score combines four criteria, each ranked against all French communes: inhabitants per bakery
(weight 3), median income (weight 2), population growth (weight 2) and recorded crime (weight 1).
Missing values (statistical secrecy) are left out and the weights re-normalised; small communes are pulled
towards the middle for income and growth. 60 and above is "favourable", below 40 "unfavourable".
Data comes from Insee (census, BPE, Filosofi, Sirene), the Ministry of the Interior, La Poste, IGN and
BODACC, and is rebuilt every month. The site is in French, free, with no account and no ads. It is
published by the association Vraie Forêt (Nantes, France).

## Main pages

- [Map of France]({SITE_URL}): every commune coloured by score, filters, and an "En tournée" mode for a
  bakehouse delivering several villages.
- [Sources and method]({SITE_URL}sources/): data sources, years, how the score is computed, limits.
- [Legal information]({SITE_URL}infos-legales/): publisher, data licences, privacy, update schedule.
- [Sitemap]({SITE_URL}sitemap.xml): one page per commune, for example
  {SITE_URL}loire-atlantique/clisson-44043/ (population, bakeries and competition within 5 and 10 km,
  takeovers, price of bakery businesses, demography, local economy).

## Départements

{dep_lines}
"""

    # --- routing (development server) ---

    def route(self, path: str) -> str | None:
        """HTML for a site-relative path like 'loire-atlantique/clisson-44043/', or None."""
        parts = [p for p in path.strip("/").split("/") if p]
        deps_by_slug = {slugify(n): d for d, n in self.dep_names.items() if d in self.exported}
        if len(parts) == 1 and parts[0] in deps_by_slug:
            return self.dep_page(deps_by_slug[parts[0]])
        if len(parts) == 2:
            code = parts[1].rsplit("-", 1)[-1].upper()
            if code in self.communes and path.strip("/") == commune_path(
                self.dep_names[self.communes[code]["dep"]], self.communes[code]["name"], code
            ).strip("/"):
                return self.commune_page(code)
        return None

    # --- build ---

    def write(self, site: Path) -> int:
        n = 0
        for dep in sorted(self.exported):
            _put(site / dep_path(self.dep_names[dep]) / "index.html", self.dep_page(dep))
            n += 1
        for code, c in self.communes.items():
            _put(site / commune_path(self.dep_names[c["dep"]], c["name"], code) / "index.html", self.commune_page(code))
            n += 1
        for rel in STATIC_PAGES:
            f = site / rel
            if f.exists():
                page = f.read_text(encoding="utf-8").replace("<!-- analytics -->", analytics_tag())
                if rel == "index.html":
                    page = self.home_page(page)
                elif rel in ("sources/index.html", "infos-legales/index.html"):
                    url = SITE_URL + rel.removesuffix("index.html")
                    page = page.replace("</head>", f'  <link rel="canonical" href="{url}">\n</head>', 1)
                f.write_text(page, encoding="utf-8")
        _put(site / "404.html", self.not_found_page())
        _put(site / "sitemap.xml", self.sitemap())
        _put(site / "robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n")
        _put(site / "llms.txt", self.llms_txt())
        return n


def _put(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    count = Site().write(target)
    print(f"{count} pages written to {target}/")
