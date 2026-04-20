"""hull_adapter.py — HullHttpHandlerBase: shared HTTP→Hull.handle() bridge.

Subclasses override only:
- do_GET (for carrier-specific bypasses like /healthz)
- log_message (optional)
Do NOT override do_POST, _read_json, or _respond in subclasses.
"""
from __future__ import annotations

import http.server
import json


class HullHttpHandlerBase(http.server.BaseHTTPRequestHandler):
    """Bridge external HTTP requests to self.server.hull.handle(method, path, body)."""

    def do_GET(self) -> None:
        path, body = self._parse_get()
        status, data = self.server.hull.handle("GET", path, body)
        self._respond(data, status)

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        body = self._read_json()
        status, data = self.server.hull.handle("POST", path, body)
        self._respond(data, status)

    def _parse_get(self) -> tuple[str, dict | None]:
        """Split self.path into (path, query_params_dict_or_None)."""
        if "?" not in self.path:
            return self.path, None
        path, qs = self.path.split("?", 1)
        params: dict = {}
        for part in qs.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                try:
                    params[k] = int(v)
                except ValueError:
                    params[k] = v
        return path, (params or None)

    def _read_json(self) -> dict | None:
        """Read body; return parsed dict, or None if empty/malformed."""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            return None

    def _respond(self, data: object, status: int = 200) -> None:
        """Write data to the socket. data is either a dict (→ JSON) or a StaticResponse."""
        from vessal.ark.shell.hull.hull_api import StaticResponse

        if isinstance(data, StaticResponse):
            body = data.content
            content_type = data.content_type
        else:
            body = json.dumps(data, ensure_ascii=False).encode()
            content_type = "application/json"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        """Silent by default; container_mode overrides to forward to its logger."""
