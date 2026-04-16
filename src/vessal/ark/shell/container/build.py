"""build.py — Core logic for vessal build + vessal run.

vessal build: assemble Docker build context + call docker build.
vessal run: create named volume + call docker run.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


def _find_vessal_root() -> Path:
    """Locate the vessal project root (containing pyproject.toml and src/vessal/).

    Note: vessal build requires a source install (uv run / editable install) so that
    vessal source code can be bundled into the Docker image. wheel install mode is not supported.
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists() and (parent / "src" / "vessal").is_dir():
            return parent
    raise RuntimeError(
        "Cannot locate vessal project root. vessal build requires a source install (uv run), wheel install mode is not supported."
    )


def _find_dockerfile() -> Path:
    """Locate the default Dockerfile template."""
    return Path(__file__).resolve().parent / "Dockerfile"


def assemble_build_context(agent_dir: Path, context_dir: Path) -> None:
    """Assemble Docker build context into context_dir.

    Args:
        agent_dir: Agent project directory (containing hull.toml).
        context_dir: Output build context directory.

    Raises:
        FileNotFoundError: hull.toml not found in agent_dir.
    """
    agent_dir = Path(agent_dir).resolve()
    if not (agent_dir / "hull.toml").exists():
        raise FileNotFoundError(f"hull.toml not found in {agent_dir}")

    context_dir = Path(context_dir)
    context_dir.mkdir(parents=True, exist_ok=True)

    # vessal runtime (entire project root, including pyproject.toml + src/)
    vessal_root = _find_vessal_root()
    shutil.copytree(
        vessal_root,
        context_dir / "vessal",
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", ".git", ".venv", "node_modules",
            "data", "*.egg-info", ".worktrees", "worktrees",
        ),
    )

    # Agent definition (excluding sensitive files like .env and runtime data)
    # context_dir may be nested inside agent_dir (test scenario), must exclude to prevent recursion.
    agent_dest = context_dir / "agent"
    _base_ignore = shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".venv", "data", ".env",
    )

    def _agent_ignore(src: str, names: list[str]) -> set[str]:
        ignored = set(_base_ignore(src, names))
        # Exclude context_dir itself (when context_dir is inside agent_dir)
        try:
            ctx_rel = context_dir.relative_to(Path(src))
            top = ctx_rel.parts[0]
            if top in names:
                ignored.add(top)
        except ValueError:
            pass
        return ignored

    shutil.copytree(agent_dir, agent_dest, ignore=_agent_ignore)

    # Dockerfile: use agent's own if present, otherwise fall back to default template
    if (agent_dir / "Dockerfile").exists():
        shutil.copy2(agent_dir / "Dockerfile", context_dir / "Dockerfile")
    else:
        shutil.copy2(_find_dockerfile(), context_dir / "Dockerfile")


def build_image(
    agent_dir: Path,
    name: str | None = None,
    tag: str = "latest",
) -> None:
    """Build a Docker image.

    Args:
        agent_dir: Agent project directory.
        name: Image name. If None, reads from hull.toml [agent].name.
        tag: Image tag, defaults to "latest".
    """
    agent_dir = Path(agent_dir).resolve()
    if name is None:
        name = _read_agent_name(agent_dir)

    with tempfile.TemporaryDirectory(prefix="vessal-build-") as tmpdir:
        context_dir = Path(tmpdir)
        assemble_build_context(agent_dir, context_dir)
        image_tag = f"{name}:{tag}"
        cmd = ["docker", "build", "-t", image_tag, str(context_dir)]
        print(f"Building {image_tag} ...")
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print(f"Error: docker build failed (exit {result.returncode})", file=sys.stderr)
            sys.exit(1)
        print(f"Image built: {image_tag}")


def run_container(
    name: str,
    port: int = 8420,
    detach: bool = True,
    env: dict[str, str] | None = None,
) -> None:
    """Start a Docker container.

    Args:
        name: Image name (also used as container name and volume name).
        port: Host-mapped port.
        detach: Run in background (default True).
        env: Environment variables (e.g. API keys, sensitive config not baked into image).
    """
    volume_name = f"{name}_agent"
    print(f"Creating volume {volume_name} ...")
    subprocess.run(
        ["docker", "volume", "create", volume_name],
        check=True,
    )
    cmd = [
        "docker", "run",
        "--name", name,
        "--restart", "unless-stopped",
        "-p", f"{port}:8420",
        "-v", f"{volume_name}:/app/agent",
    ]
    for k, v in (env or {}).items():
        cmd.extend(["-e", f"{k}={v}"])
    if detach:
        cmd.append("-d")
    cmd.append(f"{name}:latest")
    print(f"Starting container {name} on port {port} ...")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"Error: docker run failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(1)
    print(f"Container started: {name}")
    print(f"  Access: http://localhost:{port}/status")
    print(f"  Logs: docker logs -f {name}")
    print(f"  Stop: docker stop {name}")


def _read_agent_name(agent_dir: Path) -> str:
    """Read [agent].name from hull.toml.

    Args:
        agent_dir: Agent project directory.

    Raises:
        FileNotFoundError: hull.toml not found.
        ValueError: [agent].name not found in hull.toml.
    """
    toml_path = Path(agent_dir) / "hull.toml"
    if not toml_path.exists():
        raise FileNotFoundError(f"hull.toml not found in {agent_dir}")
    with open(toml_path, "rb") as f:
        config = tomllib.load(f)
    name = config.get("agent", {}).get("name")
    if not name:
        raise ValueError(f"[agent].name not found in hull.toml: {toml_path}")
    return name
