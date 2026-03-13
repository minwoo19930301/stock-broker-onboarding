#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class AppHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        cleaned = path.split("?", 1)[0].split("#", 1)[0]
        if cleaned in {"", "/"}:
            return str(ROOT / "index.html")

        candidate = (ROOT / cleaned.lstrip("/")).resolve()
        try:
            candidate.relative_to(ROOT)
        except ValueError:
            return str(ROOT / "index.html")

        if candidate.is_dir():
            return str(candidate / "index.html")
        return str(candidate)

    def _write_json(self, status: HTTPStatus, payload: dict[str, str], include_body: bool) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def _write_file(self, include_body: bool) -> None:
        target = Path(self.translate_path(self.path))
        if not target.exists():
            target = ROOT / "index.html"

        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def _handle_request(self, include_body: bool) -> None:
        if self.path.startswith("/healthz"):
            self._write_json(
                HTTPStatus.OK,
                {"status": "ok", "service": "stock-broker-onboarding-static"},
                include_body,
            )
            return

        if self.path.startswith("/api/"):
            self._write_json(
                HTTPStatus.NOT_IMPLEMENTED,
                {"error": "backend_not_enabled_yet"},
                include_body,
            )
            return

        self._write_file(include_body)

    def do_GET(self) -> None:
        self._handle_request(include_body=True)

    def do_HEAD(self) -> None:
        self._handle_request(include_body=False)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 80), AppHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
