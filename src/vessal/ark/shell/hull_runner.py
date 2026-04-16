"""hull_runner.py — Hull subprocess entry point: creates Hull + internal HTTP server + event loop.

Shell main process launches this module via subprocess.Popen:
    python -m vessal.ark.shell.hull_runner --dir PROJECT_DIR --port INTERNAL_PORT

Startup sequence:
    1. Create Hull instance (initialize Cell, load skills, restore snapshot)
    2. Start HTTP server on INTERNAL_PORT (_HullHandler forwards to hull.handle())
    3. Write "READY:{port}" signal to stdout to notify Shell
    4. Run asyncio event loop (hull.run())
    5. Shutdown HTTP server on exit
"""
from __future__ import annotations

import argparse
import asyncio
import http.server
import json
import sys
import threading
from pathlib import Path


class _HullHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler: forwards requests to Hull.handle(), consistent with Shell's legacy _Handler logic.

    Attributes:
        server: HTTPServer instance; server.hull attribute must be set.
    """

    def do_GET(self) -> None:
        """Handle GET requests."""
        path = self.path.split("?")[0]
        body = self._parse_query_params()
        status, data = self.server.hull.handle("GET", path, body)
        self._respond(data, status)

    def do_POST(self) -> None:
        """Handle POST requests."""
        path = self.path.split("?")[0]
        body = self._read_json()
        status, data = self.server.hull.handle("POST", path, body)
        self._respond(data, status)

    def _parse_query_params(self) -> dict | None:
        """Parse URL query string into a dict. Returns None if no params."""
        if "?" not in self.path:
            return None
        qs = self.path.split("?", 1)[1]
        params = {}
        for part in qs.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                try:
                    params[k] = int(v)
                except ValueError:
                    params[k] = v
        return params or None

    def _read_json(self) -> dict | None:
        """Read request body and parse as JSON dict. Returns None on parse failure."""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            return None

    def _respond(self, data: object, status: int = 200) -> None:
        """Serialize response and write to socket.

        Args:
            data: dict (JSON serialized) or StaticResponse (written as-is).
            status: HTTP status code.
        """
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
        """Suppress default request logging (Hull has its own logging system)."""


def main() -> None:
    """Hull subprocess entry point. Parse args, create Hull, start HTTP, run event loop."""
    parser = argparse.ArgumentParser(description="Vessal Hull subprocess")
    parser.add_argument("--dir", required=True, help="Agent project directory")
    parser.add_argument("--port", type=int, required=True, help="Internal HTTP port")
    args = parser.parse_args()

    project_dir = Path(args.dir).resolve()

    from vessal.ark.shell.hull.hull import Hull

    hull = Hull(str(project_dir))

    # Internal HTTP server
    http_server = http.server.HTTPServer(("127.0.0.1", args.port), _HullHandler)
    http_server.hull = hull
    http_thread = threading.Thread(
        target=http_server.serve_forever, daemon=True, name="hull-http"
    )
    http_thread.start()

    # Notify Shell that we are ready
    print(f"READY:{args.port}", flush=True)

    try:
        asyncio.run(hull.run())
    except KeyboardInterrupt:
        pass
    finally:
        http_server.shutdown()


if __name__ == "__main__":
    main()
