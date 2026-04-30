"""subprocess_mode.py — Hull subprocess carrier entry point.

Spawned by ShellServer via:
    python -m vessal.ark.shell.runtime.subprocess_mode --dir PROJECT_DIR --port INTERNAL_PORT

Boot sequence:
    1. Create Hull
    2. Start HTTP server on INTERNAL_PORT (SubprocessHullHandler forwards to hull.handle())
    3. Print "READY:{port}" so ShellServer knows the child is up
    4. Run asyncio event loop (hull.run())
    5. Shut down HTTP server on exit
"""
from __future__ import annotations

import argparse
import asyncio
import threading
from pathlib import Path

from vessal.ark.shell.http_server import SafeHTTPServer
from vessal.ark.shell.runtime.hull_adapter import HullHttpHandlerBase


class SubprocessHullHandler(HullHttpHandlerBase):
    """Silent logging. All carrier-specific behavior is in main()."""


def main() -> None:
    parser = argparse.ArgumentParser(description="Vessal Hull subprocess carrier")
    parser.add_argument("--dir", required=True, help="Agent project directory")
    parser.add_argument("--port", type=int, required=True, help="Internal HTTP port")
    args = parser.parse_args()

    project_dir = Path(args.dir).resolve()

    from vessal.ark.shell.hull.hull import Hull

    hull = Hull(str(project_dir))

    http_server = SafeHTTPServer(("127.0.0.1", args.port), SubprocessHullHandler)
    http_server.hull = hull
    threading.Thread(target=http_server.serve_forever, daemon=True, name="hull-http").start()

    print(f"READY:{args.port}", flush=True)

    try:
        asyncio.run(hull.run())
    except KeyboardInterrupt:
        pass
    finally:
        http_server.shutdown()


if __name__ == "__main__":
    main()
