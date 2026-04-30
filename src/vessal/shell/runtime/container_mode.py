"""container_mode.py — Hull container carrier entry point (Docker ENTRYPOINT).

In container mode, the Docker container itself is the Shell.
This module is the startup sequence for Hull inside the container shell.

Responsibilities:
- Create Hull instance
- Start HTTP server (bind 0.0.0.0)
- Forward HTTP requests to hull.handle()
- /healthz health check (bypasses Hull)
- Handle SIGTERM for graceful shutdown

Usage:
    python -m vessal.ark.shell.runtime.container_mode [--dir /app/agent] [--port 8420]

Differences from subprocess_mode:
- Binds 0.0.0.0 (container port), not 127.0.0.1 (internal port)
- Handles SIGTERM (container shutdown signal), not READY signal
- Provides /healthz (Docker HEALTHCHECK), no need to notify Shell
- Logs to stdout (docker logs), not piped to Shell
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import shutil
import signal
import sys
import threading
from pathlib import Path

from vessal.ark.shell.http_server import SafeHTTPServer
from vessal.ark.shell.runtime.hull_adapter import HullHttpHandlerBase

logger = logging.getLogger("vessal.container")


class ContainerHullHandler(HullHttpHandlerBase):
    """Adds /healthz bypass; forwards HTTP logs to vessal.container logger."""

    def do_GET(self) -> None:
        path, _body = self._parse_get()
        if path == "/healthz":
            self._respond({"status": "ok"}, 200)
            return
        super().do_GET()

    def log_message(self, fmt: str, *args: object) -> None:
        logger.debug(fmt, *args)


# Initialization sentinel files: used to determine if the volume has completed first-boot sync.
# Only having runtime directories (data/logs/snapshots) does not count as initialized.
_INIT_SENTINEL_FILES = ("SOUL.md", "hull.toml")

# Runtime data directories: skipped on image update, created on first boot.
_RUNTIME_DIRS = ("data", "logs", "snapshots")


def sync_image_to_volume(image_src: Path, volume_dst: Path) -> None:
    """Sync agent definition from image into volume.

    First boot (volume is empty): full copy + create runtime directories.
    Image update (volume non-empty): overwrite definition files, preserve runtime data.

    Args:
        image_src: Agent file directory in the image (/opt/agent-image/).
        volume_dst: Volume mount point (/app/agent/).
    """
    if not image_src.exists():
        logger.debug("image_src %s not found, skipping sync", image_src)
        return

    # Volume initialization check: look for top-level definition files (not just whether the directory is empty).
    # Only having runtime directories (data/logs/snapshots) does not count as initialized.
    is_initialized = volume_dst.exists() and any(
        (volume_dst / f).exists() for f in _INIT_SENTINEL_FILES
    )
    if not is_initialized:
        # First boot (or volume has only runtime directories): full copy
        if volume_dst.exists():
            shutil.copytree(image_src, volume_dst, dirs_exist_ok=True)
        else:
            shutil.copytree(image_src, volume_dst)
        for d in _RUNTIME_DIRS:
            (volume_dst / d).mkdir(exist_ok=True)
        logger.info("First boot: copied image to volume")
        return

    # Volume has definition files: image update path
    _sync_definitions(image_src, volume_dst)


def _sync_definitions(image_src: Path, volume_dst: Path) -> None:
    """Selective sync: overwrite definition files, preserve runtime data.

    Overwrite rules:
    - Top-level files (SOUL.md, hull.toml, requirements.txt, etc.) -> all overwritten
    - Top-level non-runtime directories (not data/logs/snapshots/skills) -> fully overwritten
    - Each skill directory under skills/ -> overwrite code/doc files, skip data/ subdirectory
    - data/, logs/, snapshots/ -> left untouched

    Does not delete files that exist in the volume but not in the image
    (agent-created skills, runtime-generated files).
    """
    # Top-level items: overwrite all files; overwrite non-runtime, non-skills directories fully
    _skip_dirs = {*_RUNTIME_DIRS, "skills"}
    for item in image_src.iterdir():
        if item.is_file():
            shutil.copy2(item, volume_dst / item.name)
        elif item.is_dir() and item.name not in _skip_dirs:
            shutil.copytree(item, volume_dst / item.name, dirs_exist_ok=True)

    # skills/ sync
    image_skills = image_src / "skills"
    if not image_skills.is_dir():
        return

    volume_skills = volume_dst / "skills"
    volume_skills.mkdir(exist_ok=True)

    for skill_src in image_skills.iterdir():
        if not skill_src.is_dir():
            continue
        skill_dst = volume_skills / skill_src.name
        skill_dst.mkdir(exist_ok=True)
        for item in skill_src.iterdir():
            if item.is_file():
                shutil.copy2(item, skill_dst / item.name)
            elif item.is_dir() and item.name != "data":
                # Recursively overwrite subdirectories (e.g. tests/), skip data/.
                # Use dirs_exist_ok=True to avoid non-atomic delete-then-copy.
                shutil.copytree(item, skill_dst / item.name, dirs_exist_ok=True)

    logger.info("Image update: synced definitions to volume")


def main() -> None:
    """Container entry point. Parse args, create Hull, start HTTP, run event loop."""
    parser = argparse.ArgumentParser(description="Vessal container entry point")
    parser.add_argument("--dir", default="/app/agent", help="Agent project directory")
    parser.add_argument("--port", type=int, default=8420, help="HTTP port")
    args = parser.parse_args()

    # Log to stdout (collected by docker logs)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )

    project_dir = Path(args.dir).resolve()
    logger.info("Starting Hull from %s on port %d", project_dir, args.port)

    # Image -> volume sync (container mode only)
    image_src = Path("/opt/agent-image")
    if image_src.exists():
        sync_image_to_volume(image_src, project_dir)

    from vessal.ark.shell.hull.hull import Hull

    hull = Hull(str(project_dir))

    # HTTP server — bind 0.0.0.0 (container port)
    http_server = SafeHTTPServer(("0.0.0.0", args.port), ContainerHullHandler)
    http_server.hull = hull
    http_thread = threading.Thread(
        target=http_server.serve_forever, daemon=True, name="container-http",
    )
    http_thread.start()
    logger.info("HTTP server listening on 0.0.0.0:%d", args.port)

    # SIGTERM -> graceful shutdown
    def on_sigterm(*_: object) -> None:
        logger.info("SIGTERM received, shutting down")
        hull.stop()

    signal.signal(signal.SIGTERM, on_sigterm)

    # Run Hull event loop (blocks until stop)
    try:
        asyncio.run(hull.run())
    except KeyboardInterrupt:
        pass
    finally:
        http_server.shutdown()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
