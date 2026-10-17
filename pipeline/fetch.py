"""Download every source into pipeline/raw/ (cached) and record what was fetched in raw/manifest.json."""

import hashlib
import json
import shutil
import time
import urllib.request
import zipfile
from datetime import datetime, timezone

from pipeline.config import RAW, SOURCES

MANIFEST = RAW / "manifest.json"
USER_AGENT = "Mozilla/5.0 (fournil data pipeline)"
RETRIES = 4
RETRY_WAIT_S = 20  # Insee's Melodi API limits requests per minute


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


MAGIC = {".zip": b"PK\x03\x04", ".parquet": b"PAR1"}


def _check_format(path, suffix: str) -> None:
    """Reject error pages served with a 200 status and truncated files before they reach the cache."""
    with open(path, "rb") as f:
        head = f.read(200)
        if path.stat().st_size >= 4:
            f.seek(-4, 2)
        tail = f.read(4)
    expected = MAGIC.get(suffix)
    if expected and not head.startswith(expected):
        raise ValueError(f"not a {suffix} file, starts with {head[:120]!r}")
    if suffix == ".zip" and not zipfile.is_zipfile(path):
        raise ValueError("truncated zip (no central directory)")
    if suffix == ".parquet" and tail != b"PAR1":
        raise ValueError("truncated parquet (no footer)")
    if suffix == ".csv" and (not head or head.lstrip().startswith((b"<", b"{"))):
        raise ValueError(f"not a CSV file, starts with {head[:120]!r}")


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
    for attempt in range(1, RETRIES + 1):
        print(f"  downloading {source_id} (attempt {attempt}) …", flush=True)
        try:
            with _get(url) as r, open(tmp, "wb") as f:
                expected = r.headers.get("Content-Length")
                shutil.copyfileobj(r, f, length=1 << 20)
            if expected and tmp.stat().st_size != int(expected):
                raise ValueError(f"truncated: {tmp.stat().st_size} of {expected} bytes")
            _check_format(tmp, suffix)
            break
        except (OSError, ValueError) as err:  # network errors, HTTP errors and wrong content
            print(f"    failed: {err}", flush=True)
            if attempt == RETRIES:
                raise RuntimeError(f"could not download {source_id} from {url}") from err
            time.sleep(RETRY_WAIT_S * attempt)
    tmp.replace(target)
    print(f"    {target.stat().st_size / 1e6:.1f} MB", flush=True)

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
