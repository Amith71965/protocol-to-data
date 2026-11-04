"""Serve rendered Archify diagrams and accept their exports back to disk.

Archify's CLI only emits standalone HTML; PNG and dual-theme SVG are export
actions inside the rendered page. The page hands each export to a download
anchor, which a sandboxed browser cannot write to disk. This server hosts the
diagrams and exposes a same-origin ``POST /save`` so the page can send the
exported Blob straight back into ``docs/diagrams/``.

Usage:
    python scripts/serve_diagrams.py [port]

Then, in the page's console (see docs/diagrams/README.md for the snippet),
call the exporter and POST the resulting Blob to /save.
"""

from __future__ import annotations

import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DIAGRAM_DIR = Path(__file__).resolve().parents[1] / "docs" / "diagrams"
ALLOWED_SUFFIXES = {".svg", ".png", ".jpeg", ".jpg", ".webp", ".webm"}
MAX_UPLOAD_BYTES = 32 * 1024 * 1024


class DiagramHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIAGRAM_DIR), **kwargs)

    def do_POST(self) -> None:  # noqa: N802  (http.server's required casing)
        if self.path != "/save":
            self.send_error(404)
            return

        name = Path(self.headers.get("X-Filename", "")).name
        if not name or Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
            self.send_error(400, "unsupported filename")
            return

        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > MAX_UPLOAD_BYTES:
            self.send_error(413, "unsupported payload size")
            return

        destination = DIAGRAM_DIR / name
        destination.write_bytes(self.rfile.read(length))

        body = f"saved {destination} ({length} bytes)".encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        """Quiet by default; the agent reads the POST response instead."""


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    DIAGRAM_DIR.mkdir(parents=True, exist_ok=True)
    print(f"serving {DIAGRAM_DIR} on http://127.0.0.1:{port} (POST /save enabled)")
    ThreadingHTTPServer(("127.0.0.1", port), DiagramHandler).serve_forever()


if __name__ == "__main__":
    main()
