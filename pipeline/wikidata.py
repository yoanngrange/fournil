"""Photo (Wikimedia Commons) and French Wikipedia article of each commune, from Wikidata.

Primary: QLever (qlever.dev, University of Freiburg), a fast public mirror of Wikidata that answers the
national query in seconds. Fallback: the official Wikidata endpoint, one query per département (a single
national query exceeds its 60 s limit, and it is sometimes rate-limited to 1 request per minute).
Only file names and article URLs are stored; the page asks Commons for the thumbnail, author and licence,
so the credit shown is always the current one.
"""

import csv
import io
import json
import time
import urllib.parse
from pathlib import Path

from pipeline import fetch

QLEVER = "https://qlever.dev/api/wikidata"
WDQS = "https://query.wikidata.org/sparql"
PREFIXES = (
    "PREFIX wd: <http://www.wikidata.org/entity/> PREFIX wdt: <http://www.wikidata.org/prop/direct/> "
    "PREFIX schema: <http://schema.org/> "
)
QUERY = """SELECT ?insee ?image ?article WHERE {
  ?item wdt:P374 ?insee %s.
  %s
  OPTIONAL { ?item wdt:P18 ?image }
  OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://fr.wikipedia.org/> }
}"""
FILE_PATH = "/Special:FilePath/"


def _query(endpoint: str, sparql: str) -> list[dict]:
    url = f"{endpoint}?{urllib.parse.urlencode({'query': sparql})}"
    with fetch._get(url, {"Accept": "text/csv"}) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8"))))


COMMUNE = "; wdt:P31 wd:Q484170 "  # instance of "commune of France" (Paris, Lyon… are typed otherwise)


def _rows(deps: list[str]) -> list[dict]:
    """Rows for items typed as communes first, then any item carrying an INSEE code (used only for codes
    the first pass missed: an old merged commune can share its code with the commune nouvelle)."""
    try:
        rows = _query(QLEVER, PREFIXES + QUERY % (COMMUNE, ""))
        if len(rows) > 30_000:  # sanity check: about 35,000 communes
            return rows + _query(QLEVER, PREFIXES + QUERY % ("", ""))
        print(f"    qlever returned only {len(rows)} rows, falling back to query.wikidata.org", flush=True)
    except OSError as err:
        print(f"    qlever: {err}; falling back to query.wikidata.org", flush=True)
    rows = []
    for dep in deps:
        for attempt in range(4):
            try:
                rows += _query(WDQS, QUERY % (COMMUNE, f'FILTER(STRSTARTS(?insee, "{dep}"))'))
                break
            except OSError as err:
                print(f"    wikidata {dep}: {err}", flush=True)
                time.sleep(15 * (attempt + 1))
        else:
            raise RuntimeError(f"Wikidata query failed for département {dep}")
        time.sleep(1)
    return rows


def download(target: Path, deps: list[str]) -> None:
    """Write {insee: {"file": …, "article": …}} for every commune of the given départements."""
    out = {}
    for row in _rows(deps):
        entry = out.setdefault(row["insee"], {"file": None, "article": None})
        if row.get("image") and not entry["file"]:
            entry["file"] = urllib.parse.unquote(row["image"].split(FILE_PATH, 1)[-1])
        if row.get("article") and not entry["article"]:
            entry["article"] = row["article"]
    target.write_text(json.dumps(out, ensure_ascii=False))


def photos(codes: set[str]) -> dict:
    data = json.loads(fetch.path("wikidata").read_text(encoding="utf-8"))
    return {c: v for c, v in data.items() if c in codes and (v["file"] or v["article"])}
