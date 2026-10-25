#!/usr/bin/env bash
# Assemble the static site into _site/ (same layout as scripts/serve.py serves locally).
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf _site
cp -R public _site
cp -R src _site/src
uv run python -m pipeline.pages _site
echo "Site assembled in _site/ ($(find _site -type f | wc -l | tr -d ' ') files)"
