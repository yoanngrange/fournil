"""Download every source into pipeline/raw/ (cached) and record what was fetched in raw/manifest.json."""

import hashlib
import json
import shutil
import urllib.request
from datetime import datetime, timezone

from pipeline.config import RAW, SOURCES

MANIFEST = RAW / "manifest.json"
USER_AGENT = "Mozilla/5.0 (fournil data pipeline)"


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=600)


def resolve_datagouv(spec: dict) -> dict:
    """Latest resource of a data.gouv.fr dataset matching a title prefix and format."""
    with _get(f"https://www.data.gouv.fr/api/1/datasets/{spec['dataset']}/") as r:
        dataset = json.load(r)
    matches = [
        res
        for res in dataset["resources"]
        if res["title"].startswith(spec["title_startswith"]) and res["format"] == spec["format"]
    ]
    if not matches:
        raise RuntimeError(f"No resource matching {spec} on data.gouv.fr")
    res = max(matches, key=lambda r: r["last_modified"])
    return {"url": res["url"], "published": res["last_modified"][:10], "title": res["title"]}


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def fetch(source_id: str, refresh: bool = False) -> dict:
    """Download one source if missing (or if refresh) and return its manifest entry."""
    spec = SOURCES[source_id]
    manifest = load_manifest()
    entry = manifest.get(source_id)
    if entry and (RAW / entry["file"]).exists() and not refresh:
        return entry

    resolved = resolve_datagouv(spec["datagouv"]) if "datagouv" in spec else {"url": spec["url"]}
    url = resolved["url"]
    suffix = ".parquet" if url.endswith(".parquet") else ".csv" if url.endswith(".csv") else ".zip"
    target = RAW / f"{source_id}{suffix}"
    RAW.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    print(f"  downloading {source_id} …", flush=True)
    with _get(url) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)
    tmp.replace(target)

    entry = {
        "file": target.name,
        "url": url,
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "bytes": target.stat().st_size,
        "sha256": _sha256(target),
        **({"published": resolved["published"]} if "published" in resolved else {}),
    }
    manifest = load_manifest()
    manifest[source_id] = entry
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return entry


def fetch_all(refresh: bool = False) -> dict:
    return {sid: fetch(sid, refresh) for sid in SOURCES}


def path(source_id: str):
    return RAW / fetch(source_id)["file"]


if __name__ == "__main__":
    for sid, e in fetch_all().items():
        print(f"{sid:28} {e['bytes'] / 1e6:8.1f} MB  {e['url']}")
