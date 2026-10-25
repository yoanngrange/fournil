"""Local dev server: serves the site exactly as it is laid out on GitHub Pages.

/src/*                         -> src/
/<département>/[<commune>/]    -> pages rendered on the fly by pipeline/pages.py (generated at build time on Pages)
/*                             -> public/ (404.html for anything else)

Usage: uv run python scripts/serve.py [port]   (default 8000)
"""

import http.server
import mimetypes
import os
import sys
from functools import partial
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
mimetypes.add_type("text/javascript", ".mjs")

from pipeline.pages import Site  # noqa: E402


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if not path.startswith("/src/"):
            return super().translate_path(path)
        public, self.directory = self.directory, str(ROOT / "src")
        try:
            return super().translate_path(path[len("/src"):])
        finally:
            self.directory = public

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if os.path.exists(self.translate_path(path)):
            return super().do_GET()
        site = Site()  # reloaded per page so data and copy edits show up without a restart
        page = site.route(path)
        status = 200 if page else 404
        self._send_html(page or site.not_found_page().replace(f'href="{site.root_path}"', 'href="/"'), status)

    def _send_html(self, text: str, status: int):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = partial(Handler, directory=str(ROOT / "public"))
    print(f"Fournil on http://localhost:{port}/")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()
