"""Local dev server: serves the site exactly as it is laid out on GitHub Pages.

/src/*  -> src/
/*      -> public/

Usage: python scripts/serve.py [port]   (default 8000)
"""

import http.server
import mimetypes
import sys
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
mimetypes.add_type("text/javascript", ".mjs")


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if not path.startswith("/src/"):
            return super().translate_path(path)
        public, self.directory = self.directory, str(ROOT / "src")
        try:
            return super().translate_path(path[len("/src"):])
        finally:
            self.directory = public

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = partial(Handler, directory=str(ROOT / "public"))
    print(f"Fournil on http://localhost:{port}/")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()
