"""chat Skill HTTP routes.

Hull-managed mode: start(hull_api, skill) registers routes; messages are delivered via skill.receive().
Standalone mode: python server.py --data-dir <path> runs independently.
"""
import argparse
import http.server
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


# ── Hull-managed mode ──

_hull_api = None
_skill = None  # Chat skill instance reference
_index_html: bytes | None = None
_static_cache: dict[str, "StaticResponse"] = {}


def _make_static_handler(filename: str):
    """Create a route handler for the given static file (closure, reads from cache)."""
    def handler(_body):
        cached = _static_cache.get(filename)
        if cached is not None:
            return 200, cached
        return 404, {"error": f"{filename} not found"}
    return handler


def start(hull_api, skill=None) -> None:
    """Hull-managed entry point. Registers routes with Hull.

    Args:
        hull_api: ScopedHullApi instance.
        skill: Chat skill instance, used to call receive() directly.
    """
    global _hull_api, _skill, _index_html

    _hull_api = hull_api
    _skill = skill

    index_path = Path(__file__).parent / "index.html"
    if index_path.exists():
        _index_html = index_path.read_bytes()

    from vessal.ark.shell.hull.hull_api import StaticResponse
    for static_file in ("style.css", "app.js", "render.js"):
        file_path = Path(__file__).parent / static_file
        if file_path.exists():
            _static_cache[static_file] = StaticResponse.from_file(file_path)
        hull_api.register_route("GET", f"/{static_file}", _make_static_handler(static_file))

    hull_api.register_route("GET", "/", _handle_index)
    hull_api.register_route("POST", "/inbox", _handle_inbox)
    hull_api.register_route("GET", "/outbox", _handle_outbox)
    hull_api.register_route("GET", "/history", _handle_history)


def stop() -> None:
    """Hull-managed shutdown. Unregisters routes."""
    global _hull_api, _skill
    if _hull_api is not None:
        _hull_api.unregister_route("/")
        _hull_api.unregister_route("/inbox")
        _hull_api.unregister_route("/outbox")
        _hull_api.unregister_route("/history")
        for static_file in ("style.css", "app.js", "render.js"):
            _hull_api.unregister_route(f"/{static_file}")
        _static_cache.clear()
        _hull_api = None
        _skill = None


def _handle_index(_body):
    """GET / — chat UI page."""
    from vessal.ark.shell.hull.hull_api import StaticResponse
    if _index_html is not None:
        return 200, StaticResponse(_index_html, "text/html; charset=utf-8")
    return 404, {"error": "index.html not found"}


def _handle_inbox(body):
    """POST /inbox — human sends a message. Calls skill.receive() directly, no file intermediary."""
    body = body or {}
    content = body.get("content", "")
    sender = body.get("sender", "user")

    if _skill is not None:
        # Hull-managed mode: deliver directly to skill memory
        _skill.receive(content, sender)
    else:
        # Standalone fallback: write to file (should not occur in normal Hull mode)
        _write_to_file(content, sender)

    if _hull_api is not None:
        _hull_api.wake("user_message")
    return 200, {"status": "ok"}


def _handle_outbox(body):
    """GET /outbox — read agent replies. Reads from chat.jsonl (persistent data source)."""
    body = body or {}
    after_ts = 0.0
    if "after" in body:
        try:
            after_ts = float(body["after"])
        except (TypeError, ValueError):
            pass

    # Read from the skill instance's data_dir
    data_dir = _skill._data_dir if _skill else None
    if data_dir is None:
        return 200, {"messages": []}

    chat_file = data_dir / "chat.jsonl"
    if not chat_file.exists():
        return 200, {"messages": []}

    results = []
    try:
        with open(chat_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("role") == "agent" and entry.get("ts", 0) > after_ts:
                    results.append(entry)
    except OSError:
        pass
    return 200, {"messages": results}


def _handle_history(_body: dict) -> tuple[int, dict]:
    """GET /history — return full conversation (user + agent).

    Args:
        _body: Request body (unused).

    Returns:
        HTTP status code and a dict containing the messages list.
    """
    data_dir = _skill._data_dir if _skill else None
    if data_dir is None:
        return 200, {"messages": []}

    chat_file = data_dir / "chat.jsonl"
    if not chat_file.exists():
        return 200, {"messages": []}

    results = []
    try:
        for line in chat_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                results.append(entry)
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return 200, {"messages": results}


def _write_to_file(content: str, sender: str) -> None:
    """Standalone fallback: write to chat.jsonl."""
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    chat_file = data_dir / "chat.jsonl"
    ts = time.time()
    entry = {"ts": ts, "role": "user", "content": content, "sender": sender}
    with open(chat_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Standalone mode ──

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            self._json({"status": "ok"})
        elif path == "/outbox":
            self._handle_outbox()
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/inbox":
            self._handle_inbox()
        else:
            self._json({"error": "not found"}, 404)

    def _handle_inbox(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._json({"error": "invalid json"}, 400)
            return
        content = data.get("content", "")
        sender = data.get("sender", "user")
        ts = time.time()
        chat_file = self.server.data_dir / "chat.jsonl"
        entry = {"ts": ts, "role": "user", "content": content, "sender": sender}
        with open(chat_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._wake_agent()
        self._json({"status": "ok"})

    def _handle_outbox(self):
        after_ts = 0.0
        if "?" in self.path:
            qs = self.path.split("?", 1)[1]
            for part in qs.split("&"):
                if part.startswith("after="):
                    try:
                        after_ts = float(part[6:])
                    except ValueError:
                        pass
        chat_file = self.server.data_dir / "chat.jsonl"
        if not chat_file.exists():
            self._json({"messages": []})
            return
        results = []
        try:
            with open(chat_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("role") == "agent" and entry.get("ts", 0) > after_ts:
                        results.append(entry)
        except OSError:
            pass
        self._json({"messages": results})

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _wake_agent(self):
        hull_api = getattr(self.server, "hull_api", None)
        if hull_api is not None:
            try:
                hull_api.wake("user_message")
            except Exception:
                pass
            return
        shell_url = getattr(self.server, "shell_url", None)
        if not shell_url:
            return
        try:
            body = json.dumps({"reason": "user_message"}).encode()
            req = urllib.request.Request(
                f"{shell_url}/wake", data=body,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            urllib.request.urlopen(req, timeout=2)
        except Exception:
            pass

    def log_message(self, fmt, *args):
        pass


class _ReusableHTTPServer(http.server.HTTPServer):
    allow_reuse_address = True


def create_server(data_dir: Path, host: str = "127.0.0.1", port: int = 8421, shell_url: str | None = None):
    server = _ReusableHTTPServer((host, port), Handler)
    server.data_dir = data_dir
    server.shell_url = shell_url
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chat Skill standalone HTTP server")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--port", type=int, default=8421)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--shell-url", default="http://127.0.0.1:8420")
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    server = create_server(data_dir, args.host, args.port, shell_url=args.shell_url)
    print(f"Chat Skill server on {args.host}:{args.port}")
    server.serve_forever()
