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
RETRIES = 8
RETRY_WAIT_S = 10


def _get(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    return urllib.request.urlopen(req, timeout=600)


def _download(url: str, target) -> None:
    """Download url to target, resuming with HTTP Range when the server cuts the transfer.

    Insee's servers close long transfers to GitHub's runners part-way; every attempt continues
    from the bytes already received.
    """
    total = None
    for attempt in range(1, RETRIES + 1):
        have = target.stat().st_size if attempt > 1 and target.exists() else 0
        try:
            with _get(url, {"Range": f"bytes={have}-"} if have else None) as r:
                if have and r.status != 206:  # range ignored: start again
                    have = 0
                length = r.headers.get("Content-Length")
                if length and total is None:
                    total = have + int(length)
                with open(target, "ab" if have else "wb") as f:
                    shutil.copyfileobj(r, f, length=1 << 20)
        except OSError as err:  # network and HTTP errors
            print(f"    attempt {attempt}: {err}", flush=True)
        size = target.stat().st_size if target.exists() else 0
        if total is not None and size >= total:
            return
        if total is None and size:
            return  # no announced length: nothing to compare with
        print(f"    attempt {attempt}: {size} of {total} bytes, resuming", flush=True)
        time.sleep(RETRY_WAIT_S)
    raise RuntimeError(f"could not download {url}")


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
    if suffix == ".json":
        with open(path, "rb") as f:
            json.load(f)  # a cut export is not valid JSON
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

    if spec.get("custom") == "wikidata":  # many small queries rather than one file
        from pipeline import cog, wikidata

        RAW.mkdir(parents=True, exist_ok=True)
        target = RAW / "wikidata.json"
        print("  querying wikidata …", flush=True)
        wikidata.download(target, sorted(cog.communes().dep.unique()))
        return _record(source_id, target, spec["url"], {})

    resolved = resolve_datagouv(spec["datagouv"]) if "datagouv" in spec else {"url": spec["url"]}
    url = resolved["url"]
    suffix = spec.get("suffix") or (".parquet" if url.endswith(".parquet") else ".csv" if url.endswith(".csv") else ".zip")
    target = RAW / f"{source_id}{suffix}"
    RAW.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    print(f"  downloading {source_id} …", flush=True)
    _download(url, tmp)
    _check_format(tmp, suffix)  # an error page served with status 200 must not reach the cache
    tmp.replace(target)
    print(f"    {target.stat().st_size / 1e6:.1f} MB", flush=True)

    return _record(source_id, target, url, resolved)


def _record(source_id: str, target, url: str, resolved: dict) -> dict:
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
