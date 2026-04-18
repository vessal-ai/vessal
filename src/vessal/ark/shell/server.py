"""server.py — Shell HTTP gateway: manages Hull subprocess + HTTP reverse proxy."""
from __future__ import annotations

import http.server
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

from vessal.ark.shell.events import EventBus
from vessal.ark.shell.hot_reload import HotReloader

_logger = logging.getLogger(__name__)


class _ProxyHandler(http.server.BaseHTTPRequestHandler):
    """Reverse proxy handler: forwards requests to the Hull subprocess's internal HTTP port.

    The server instance must have:
        server.internal_port: int — Hull subprocess's internal port
        server.hull_alive: bool — whether the Hull subprocess is alive

    Attributes:
        server: HTTPServer instance with internal_port and hull_alive attributes.
    """

    def do_GET(self) -> None:
        """Handle GET requests: intercept /events for SSE, /console/* static, forward rest to Hull."""
        path = self.path.split("?")[0]
        if path == "/events":
            self._stream_events()
            return
        if path == "/console" or path.startswith("/console/"):
            self._serve_console_static(path)
            return
        self._proxy("GET")

    def _serve_console_static(self, path: str) -> None:
        import mimetypes
        from pathlib import Path as _Path
        import vessal

        root = _Path(vessal.__file__).resolve().parent / "console_spa"
        if path in ("/console", "/console/"):
            rel = "index.html"
        else:
            rel = path[len("/console/"):]
        target = (root / rel).resolve()
        if root not in target.parents and target != root:
            self.send_response(403); self.end_headers(); return
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            self.send_response(404); self.end_headers(); return
        mime, _ = mimetypes.guess_type(str(target))
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _stream_events(self) -> None:
        """SSE streaming endpoint; iterates EventBus subscription until client disconnects."""
        import json

        bus = getattr(self.server, "_event_bus", None)
        if bus is None:
            self.send_response(503)
            self.end_headers()
            return

        # Register subscription BEFORE flushing headers to eliminate the race
        # condition where a publisher fires between urlopen() returning and
        # the subscription being registered.
        stop = threading.Event()
        q = bus.open_queue()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            for event in bus.drain_queue(q, stop):
                payload = f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")
                try:
                    self.wfile.write(payload)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
        finally:
            stop.set()
            bus.close_queue(q)

    def do_POST(self) -> None:
        """Handle POST requests: forward to Hull's internal port. For /stop, mark stop intent before forwarding."""
        path = self.path.split("?")[0]
        if path == "/stop" and hasattr(self.server, "_shell_server"):
            shell = self.server._shell_server
            shell._stop_requested = True  # prevent monitor from restarting
            shell._stop_event.set()  # set early to prevent restart race between crash detection and /stop
        self._proxy("POST")

    def _proxy(self, method: str) -> None:
        """Forward request to Hull's internal port, return 503 on failure.

        Args:
            method: HTTP method ("GET" or "POST").
        """
        import urllib.error
        import urllib.request

        if not self.server.hull_alive:
            self._respond_unavailable()
            return

        # Read request body
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else None

        url = f"http://127.0.0.1:{self.server.internal_port}{self.path}"
        req = urllib.request.Request(url, data=body, method=method)
        # Forward Content-Type
        ct = self.headers.get("Content-Type")
        if ct:
            req.add_header("Content-Type", ct)

        try:
            resp = urllib.request.urlopen(req, timeout=30)
            resp_body = resp.read()
            self.send_response(resp.status)
            for key in ("Content-Type", "Content-Length"):
                val = resp.headers.get(key)
                if val:
                    self.send_header(key, val)
            self.end_headers()
            self.wfile.write(resp_body)
        except urllib.error.HTTPError as e:
            # Forward Hull subprocess's real error status code
            resp_body = e.read()
            self.send_response(e.code)
            for key in ("Content-Type", "Content-Length"):
                val = e.headers.get(key)
                if val:
                    self.send_header(key, val)
            self.end_headers()
            self.wfile.write(resp_body)
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            self._respond_unavailable()

    def _respond_unavailable(self) -> None:
        """Return 503 JSON response when Hull is unavailable."""
        import json as _json

        body = _json.dumps(
            {"status": "restarting", "message": "Agent restarting, please wait"},
            ensure_ascii=False,
        ).encode()
        self.send_response(503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        """Suppress default request logging."""


class ShellServer:
    """Shell HTTP gateway + Hull subprocess supervisor.

    Main process runs an HTTP reverse proxy, forwarding requests to Hull subprocess.
    Automatically restarts Hull subprocess on crash.

    Attributes:
        _project_dir: Agent project directory path.
        _host: HTTP listen address.
        _port: HTTP listen port (user-specified, externally exposed).
        _internal_port: Hull subprocess internal HTTP port.
        _hull_proc: Hull subprocess Popen object.
        _hull_alive: Whether the Hull subprocess is alive.
        _stop_requested: Set to True when /stop is triggered, prevents monitor from restarting.
    """

    def __init__(
        self,
        project_dir: str,
        host: str = "127.0.0.1",
        port: int = 8420,
    ) -> None:
        """Initialize ShellServer.

        Args:
            project_dir: Agent project directory path.
            host: HTTP listen address, defaults to 127.0.0.1.
            port: HTTP listen port, 0 for dynamic allocation.
        """
        self._project_dir = project_dir
        self._host = host
        self._port = port
        self._internal_port: int | None = None
        self._hull_proc: subprocess.Popen | None = None
        self._hull_alive = False
        self._stop_requested = False
        self._stop_event = threading.Event()
        self._http_server: http.server.ThreadingHTTPServer | None = None
        self._monitor_thread: threading.Thread | None = None
        self._event_bus = EventBus()
        self._hot_reloader: HotReloader | None = None
        self._frame_publisher: FramePublisher | None = None

    @property
    def port(self) -> int:
        """Actual listen port (dynamically allocated port when port=0)."""
        if self._http_server:
            return self._http_server.server_address[1]
        return self._port

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    def start(self) -> None:
        """Start Shell: launch Hull subprocess + HTTP reverse proxy + monitor thread.

        Raises:
            RuntimeError: Hull subprocess failed to start or timed out, or no free port
                found in 20 retries.
        """
        self._spawn_hull()

        requested = self._port
        last_err: OSError | None = None
        for offset in range(20):
            try:
                self._http_server = http.server.ThreadingHTTPServer(
                    (self._host, requested + offset), _ProxyHandler
                )
                self._port = requested + offset
                break
            except OSError as e:
                last_err = e
                continue
        else:
            raise RuntimeError(
                f"No free port in range {requested}..{requested + 19}: {last_err}"
            )

        self._http_server.internal_port = self._internal_port
        self._http_server.hull_alive = self._hull_alive
        self._http_server._shell_server = self
        self._http_server._event_bus = self._event_bus

        http_thread = threading.Thread(
            target=self._http_server.serve_forever,
            daemon=True,
            name="shell-proxy",
        )
        http_thread.start()

        self._monitor_thread = threading.Thread(
            target=self._monitor_hull,
            daemon=True,
            name="hull-monitor",
        )
        self._monitor_thread.start()

        self._hot_reloader = HotReloader(
            project_dir=Path(self._project_dir),
            internal_port_getter=lambda: self._internal_port,
            publish=self._event_bus.publish,
        )
        self._hot_reloader.start()

        self._frame_publisher = FramePublisher(
            port_getter=lambda: self._internal_port,
            publish=self._event_bus.publish,
        )
        self._frame_publisher.start()

        try:
            from vessal.ark.shell.tui.recent import RecentProjects
            RecentProjects().add(self._project_dir)
        except Exception:
            pass  # recent tracking is best-effort; never block startup

        try:
            import json as _json
            runtime_dir = Path(self._project_dir) / "data"
            runtime_dir.mkdir(exist_ok=True)
            (runtime_dir / "runtime.json").write_text(
                _json.dumps({"port": self._port, "host": self._host}),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _spawn_hull(self) -> None:
        """Start Hull subprocess and wait for READY signal to confirm successful startup.

        stdout and stderr are merged (stderr=STDOUT); a dedicated drain thread continuously
        reads output to prevent pipe buffer from filling and blocking the subprocess.

        Raises:
            RuntimeError: Subprocess failed to start or timed out (30s).
        """
        import queue as _queue

        internal_port = self._find_available_port()
        data_dir = Path(self._project_dir) / "data"
        data_dir.mkdir(exist_ok=True)
        log_path = data_dir / "hull.log"

        cmd = [
            sys.executable,
            "-m",
            "vessal.ark.shell.hull_runner",
            "--dir",
            self._project_dir,
            "--port",
            str(internal_port),
        ]
        self._hull_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        ready_queue: _queue.Queue[str] = _queue.Queue()

        def _drain_stdout() -> None:
            with open(log_path, "a", encoding="utf-8") as log:
                for raw_line in self._hull_proc.stdout:
                    line = raw_line.decode("utf-8", errors="replace").rstrip()
                    if line.startswith("READY:"):
                        ready_queue.put(line)
                    else:
                        log.write(line + "\n")
                        log.flush()

        threading.Thread(
            target=_drain_stdout, daemon=True, name="hull-drain"
        ).start()

        try:
            line = ready_queue.get(timeout=30)
            self._internal_port = int(line.split(":")[1])
            self._set_hull_alive(True)
            if self._http_server:
                self._http_server.internal_port = self._internal_port
        except _queue.Empty:
            exit_code = self._hull_proc.poll()
            self._hull_proc.kill()
            self._hull_proc.wait()
            if exit_code is not None:
                raise RuntimeError(
                    f"Hull subprocess failed to start (exit code {exit_code}), see {log_path}"
                )
            raise RuntimeError(f"Hull subprocess startup timed out (30s), see {log_path}")

    def _monitor_hull(self) -> None:
        """Background thread: monitors Hull subprocess, automatically restarts on crash."""
        while not self._stop_event.is_set():
            if self._hull_proc and self._hull_proc.poll() is not None:
                # Mark as unavailable first (regardless of restart), then decide whether to restart
                exit_code = self._hull_proc.returncode
                self._set_hull_alive(False)
                if self._stop_requested or self._stop_event.is_set():
                    break
                _logger.warning("Hull subprocess exited (code %d), restarting...", exit_code)
                self._event_bus.publish({
                    "type": "agent_crash",
                    "ts": time.time(),
                    "payload": {"exit_code": exit_code},
                })
                try:
                    self._spawn_hull()
                    _logger.info("Hull subprocess restarted")
                except RuntimeError as e:
                    _logger.error("Hull restart failed: %s", e)
            self._stop_event.wait(1)

    def serve_forever(self) -> None:
        """Block until shutdown() is called."""
        self._stop_event.wait()

    def shutdown(self) -> None:
        """Stop Hull subprocess and HTTP server.

        Sets stop flag first, then terminates subprocess (prevents monitor from restarting),
        then shuts down HTTP server.
        """
        self._stop_event.set()
        self._stop_requested = True
        if self._hull_proc and self._hull_proc.poll() is None:
            self._hull_proc.terminate()
            try:
                self._hull_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._hull_proc.kill()
                self._hull_proc.wait()
        if self._hot_reloader is not None:
            self._hot_reloader.stop()
        if getattr(self, "_frame_publisher", None) is not None:
            self._frame_publisher.stop()
        if self._http_server:
            self._http_server.shutdown()

    def _set_hull_alive(self, value: bool) -> None:
        """Update hull alive state on both self and HTTP server atomically.

        Args:
            value: New alive state.
        """
        self._hull_alive = value
        if self._http_server:
            self._http_server.hull_alive = value

    def request_shutdown(self) -> None:
        """Called by /stop route to trigger serve_forever() exit."""
        self._stop_event.set()

    @staticmethod
    def _find_available_port() -> int:
        """Find an available TCP port.

        Returns:
            Available port number.
        """
        import socket as _socket

        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


class FramePublisher:
    """Polls Hull /frames?after=N and publishes new frames onto an EventBus."""

    def __init__(
        self,
        port_getter,
        publish,
        fetch_frames=None,
        interval: float = 0.5,
    ) -> None:
        self._get_port = port_getter
        self._publish = publish
        self._fetch = fetch_frames or self._default_fetch
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_number = 0

    @staticmethod
    def _default_fetch(port: int, after: int) -> list:
        import json
        import urllib.error
        import urllib.request
        url = f"http://127.0.0.1:{port}/frames?after={after}"
        try:
            resp = urllib.request.urlopen(url, timeout=2)
            body = json.loads(resp.read())
            return body.get("frames", [])
        except urllib.error.URLError:
            return []

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="frame-publisher")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            port = self._get_port()
            if port is not None:
                frames = self._fetch(port, self._last_number)
                for f in frames:
                    n = f.get("number", 0)
                    if n <= self._last_number:
                        continue
                    self._last_number = n
                    self._publish({"type": "frame", "ts": time.time(), "payload": f})
