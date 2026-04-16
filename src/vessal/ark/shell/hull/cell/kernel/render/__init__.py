"""__init__.py — Render subsystem public interface: renders namespace as LLM message sequence."""
from vessal.ark.shell.hull.cell.kernel.render.renderer import render, RenderConfig, DEFAULT_CONFIG

__all__ = ["render", "RenderConfig", "DEFAULT_CONFIG"]
