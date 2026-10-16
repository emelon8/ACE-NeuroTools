"""Launch the installed local application and serve its packaged assets."""

from __future__ import annotations

import argparse
import json
import mimetypes
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files

DEFAULT_PORT = 8765
STATIC = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/style.css": "style.css"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/health":
            body, mime = json.dumps({"application": "ACE Experiments"}).encode(), "application/json"
        elif self.path in STATIC:
            name = STATIC[self.path]
            body = files("aceneurotools.gui").joinpath(name).read_bytes()
            mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Open ACE-NeuroTools in your browser.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        parser.exit(1, f"Cannot start ACE: {exc}. Choose another port with --port.\n")
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Experiment application: {url}", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
