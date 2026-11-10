#!/usr/bin/env python3
"""Daily check of the live site: pages answer, data is fresh. Emails Yoann (Resend) only when something is wrong.

    SITE_URL=https://fournyl.com/ RESEND_API_KEY=… python3 scripts/monitor.py
    python3 scripts/monitor.py --dry-run      # print the report, send nothing

Checks: home, a département page, a commune page, the Infos légales page, sw.js and data/meta.json
answer 200 with the expected content; the last data build is less than STALE_DAYS old.
Standard library only (runs on a bare GitHub runner).
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

SITE_URL = os.environ.get("SITE_URL", "https://fournyl.com/").rstrip("/") + "/"
STALE_DAYS = int(os.environ.get("STALE_DAYS", "40"))
UA = "fournyl-monitor/1.0"

# path -> text that must appear in the response
PAGES = {
    "": "communes-index.json",
    "loire-atlantique/": 'name="fournil-dep" content="44"',
    "loire-atlantique/clisson-44043/": 'content="44043"',
    "infos-legales/": "src/legal.js",
    "sources/": "src/sources.js",
    "ma-selection/": "src/selection.js",
    "sw.js": "SHELL_FILES",
}


def get(path):
    req = urllib.request.Request(SITE_URL + path, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def run_checks():
    problems, notes = [], []
    for path, needle in PAGES.items():
        try:
            status, body = get(path)
            if status != 200 or needle not in body:
                problems.append(f"/{path}: HTTP {status}, expected text {needle!r} {'found' if needle in body else 'missing'}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            problems.append(f"/{path}: {exc}")
    try:
        _, body = get("data/meta.json")
        meta = json.loads(body)
        built = datetime.fromisoformat(meta["built_at"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - built).days
        notes.append(f"Last data build: {built:%Y-%m-%d %H:%M} UTC ({age} days ago).")
        if age > STALE_DAYS:
            problems.append(f"Data is {age} days old (limit {STALE_DAYS}): the monthly build has probably failed.")
        if len(meta.get("departements", [])) < 96:
            problems.append(f"meta.json lists {len(meta.get('departements', []))} départements, expected 96.")
    except Exception as exc:  # noqa: BLE001 - any failure here is worth reporting
        problems.append(f"data/meta.json: {exc}")
    return problems, notes


def send_email(subject, text):
    body = json.dumps({
        "from": os.environ.get("REPORT_EMAIL_FROM", "fournyl.com Monitoring <fournyl-reports@yoanngrange.com>"),
        "to": [os.environ.get("REPORT_EMAIL_TO", "yoann.grange@gmail.com")],
        "subject": subject,
        "text": text,
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=body,
        headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}", "Content-Type": "application/json", "User-Agent": UA},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    dry = "--dry-run" in sys.argv
    problems, notes = run_checks()
    report = "\n".join([f"Site: {SITE_URL}", *notes, "", *(f"- {p}" for p in problems)] if problems else [f"Site: {SITE_URL}", *notes, "All checks passed."])
    print(report)
    if problems and not dry:
        send_email(f"[fournyl.com] {len(problems)} problem(s) detected", report + "\n\nRun log: " + os.environ.get("RUN_URL", "(local run)"))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
