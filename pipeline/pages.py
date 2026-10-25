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
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from pipeline.config import OUT, ROOT, SITE_URL

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


def _fill(template: str, **params) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(params.get(m.group(1), m.group(0))), template)


def _int(n) -> str:
    return f"{int(round(n)):,}".replace(",", " ")


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
            }
            for i, code in enumerate(index["code"])
        }
        self.t = strings()
        self.root_path = urlparse(SITE_URL).path  # "/fournil/"
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
        params = {
            "base": "../../",
            "title": _fill(t["seo.commune.title"], name=c["name"], code=c["dep"]),
            "description": _fill(
                t["seo.commune.description"], name=c["name"], dep=dep_name, pop=_int(c["pop"]), bakeries=bakeries, income=income
            ),
            "canonical": SITE_URL + commune_path(dep_name, c["name"], code),
            "code": code,
            "name": c["name"],
            "dep_name": dep_name,
            "dep_path": dep_path(dep_name),
            "t_france": t["map.france"],
            "t_breadcrumb": t["map.breadcrumb"],
        }
        return re.sub(r"\{\{(\w+)\}\}", lambda m: html.escape(str(params[m.group(1)]), quote=True), self.template)

    def dep_page(self, dep: str) -> str:
        """The map app, with relative URLs resolved from the site root and the département preselected."""
        name = self.dep_names[dep]
        n = sum(1 for c in self.communes.values() if c["dep"] == dep)
        title = html.escape(_fill(self.t["seo.dep.title"], dep=name, code=dep))
        desc = html.escape(_fill(self.t["seo.dep.description"], dep=name, n=_int(n)), quote=True)
        head = (
            f'<base href="../">\n  <meta name="fournil-dep" content="{dep}">\n'
            f'  <link rel="canonical" href="{SITE_URL}{dep_path(name)}">'
        )
        page = self.index_html.replace("<head>", f"<head>\n  {head}", 1)
        page = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", page, count=1)
        return re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{desc}">', page, count=1)

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
        urls = [SITE_URL, SITE_URL + "sources/"]
        urls += [SITE_URL + dep_path(self.dep_names[d]) for d in sorted(self.exported)]
        urls += [
            SITE_URL + commune_path(self.dep_names[c["dep"]], c["name"], code)
            for code, c in sorted(self.communes.items())
        ]
        body = "\n".join(f"  <url><loc>{html.escape(u)}</loc></url>" for u in urls)
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n'

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
        _put(site / "404.html", self.not_found_page())
        _put(site / "sitemap.xml", self.sitemap())
        _put(site / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n")
        return n


def _put(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    count = Site().write(target)
    print(f"{count} pages written to {target}/")
