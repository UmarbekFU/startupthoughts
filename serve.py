#!/usr/bin/env python3
"""Dev server for the generated site.

Serves site/ with clean URLs: /t/12 finds site/t/12/index.html, and anything
missing falls through to 404.html — the same behaviour as a static host.
"""
import os, sys, posixpath, urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def translate_path(self, path):
        path = urllib.parse.urlparse(path).path
        path = urllib.parse.unquote(path)
        parts = [p for p in posixpath.normpath(path).split("/") if p and p not in (".", "..")]
        full = os.path.join(ROOT, *parts)
        if os.path.isdir(full):
            return os.path.join(full, "index.html")
        return full

    def send_error(self, code, message=None, explain=None):
        page = os.path.join(ROOT, "404.html")
        if code == 404 and os.path.exists(page):
            body = open(page, "rb").read()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return
        super().send_error(code, message, explain)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4173
    print("StartupThoughts on http://localhost:%d" % port, flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
