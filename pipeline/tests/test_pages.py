"""Generated pages and human-readable URLs (pipeline/pages.py, src/lib/slug.js)."""

import json
import shutil
import subprocess

import pytest

from pipeline.config import OUT, ROOT
from pipeline.pages import Site, commune_path, slugify

CASES = {
    "L'Abergement-Clémenciat": "l-abergement-clemenciat",
    "Saint-Étienne-de-Montluc": "saint-etienne-de-montluc",
    "Œuilly": "oeuilly",
    "Côtes-d'Armor": "cotes-d-armor",
    "Bourg-Saint-Andéol": "bourg-saint-andeol",
}


def test_slugify():
    for name, slug in CASES.items():
        assert slugify(name) == slug


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_slug_js_matches_python():
    script = (
        f"import('{(ROOT / 'src/lib/slug.js').as_uri()}').then(m => "
        f"console.log(JSON.stringify({json.dumps(list(CASES))}.map(m.slugify))))"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout) == list(CASES.values())


@pytest.fixture(scope="module")
def site():
    if not (OUT / "communes-index.json").exists():
        pytest.skip("public/data not built")
    return Site()


def test_every_commune_has_a_unique_path(site):
    paths = {commune_path(site.dep_names[c["dep"]], c["name"], code) for code, c in site.communes.items()}
    assert len(paths) == len(site.communes)


def test_routes(site):
    clisson = site.route("loire-atlantique/clisson-44043/")
    assert clisson and "<title>Clisson (44)" in clisson and 'content="44043"' in clisson
    assert 'rel="canonical" href="https://yoanngrange.github.io/fournil/loire-atlantique/clisson-44043/"' in clisson
    assert site.route("loire-atlantique/") is not None
    assert site.route("loire-atlantique/clison-44043/") is None  # misspelt: 404 page redirects
    assert site.route("nowhere/") is None
