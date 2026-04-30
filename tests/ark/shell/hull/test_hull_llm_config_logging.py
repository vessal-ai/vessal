"""test_hull_llm_config_logging.py — verify Hull logs effective LLM config at boot with redacted api_key."""
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from vessal.ark.shell.hull.cell.protocol import LLMConfig


def _make_minimal_project(tmp_path: Path) -> Path:
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=sk-test123456789abcdef\n"
        "OPENAI_BASE_URL=http://localhost:8001/v1\n"
        "OPENAI_MODEL=qwen-test\n",
        encoding="utf-8",
    )
    (tmp_path / "hull.toml").write_text(
        '[agent]\nname = "t"\nlanguage = "en"\n'
        '[cell]\nmax_frames = 1\n'
        '[core]\ntimeout = 60\nmax_retries = 3\n'
        '[core.api_params]\ntemperature = 0.7\nmax_tokens = 4096\n'
        '[hull]\nskills = []\n'
        '[cells.main]\ndata_dir = "data/main"\n'
        '[gates]\n',
        encoding="utf-8",
    )
    (tmp_path / "SOUL.md").write_text("test agent", encoding="utf-8")
    return tmp_path


def test_hull_logs_redacted_llm_config_at_boot(tmp_path, caplog):
    from vessal.ark.shell.hull.hull import Hull
    project = _make_minimal_project(tmp_path)

    with caplog.at_level(logging.INFO):
        with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI"):
            Hull(project_dir=str(project))

    log_text = "\n".join(r.message for r in caplog.records)
    assert "core config" in log_text.lower() or "llm config" in log_text.lower()
    assert "qwen-test" in log_text
    assert "http://localhost:8001/v1" in log_text
    # api_key MUST be redacted; full key MUST NOT appear
    assert "sk-test123456789abcdef" not in log_text
    # redacted form shows prefix + *** + last char
    assert "sk-" in log_text and "***" in log_text


def test_hull_passes_llm_config_to_main_cell(tmp_path):
    from vessal.ark.shell.hull.hull import Hull
    project = _make_minimal_project(tmp_path)

    with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI"):
        hull = Hull(project_dir=str(project))

    cfg = hull._main_cell._default_llm_config
    assert isinstance(cfg, LLMConfig)
    assert cfg.api_key == "sk-test123456789abcdef"
    assert cfg.base_url == "http://localhost:8001/v1"
    assert cfg.model == "qwen-test"
    assert cfg.api_params["temperature"] == 0.7
    assert cfg.api_params["max_tokens"] == 4096


def test_redact_api_key_masks_middle():
    from vessal.ark.shell.hull.hull_init_mixin import HullInitMixin
    assert HullInitMixin._redact_api_key("sk-test123456789abcdef") == "sk-***f"
    assert HullInitMixin._redact_api_key("short") == "***"
    assert HullInitMixin._redact_api_key("sk-12345") == "***"
    assert HullInitMixin._redact_api_key("sk-123456789") == "sk-***9"
