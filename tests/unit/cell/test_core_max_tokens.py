from unittest.mock import patch, MagicMock

import pytest


def _make_core(api_params=None, **kwargs):
    """Construct a Core instance with the OpenAI client patched out."""
    from vessal.ark.shell.hull.cell.core.core import Core
    with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI", return_value=MagicMock()):
        return Core(api_params=api_params, **kwargs)


def test_core_max_tokens_defaults_to_4096():
    core = _make_core()
    assert core.max_tokens == 4096


def test_core_max_tokens_reads_max_tokens_key():
    core = _make_core(api_params={"max_tokens": 8000})
    assert core.max_tokens == 8000


def test_core_max_tokens_falls_back_to_max_completion_tokens():
    core = _make_core(api_params={"max_completion_tokens": 16000})
    assert core.max_tokens == 16000


def test_cell_proxies_max_tokens_from_core():
    from vessal.ark.shell.hull.cell import Cell
    with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI", return_value=MagicMock()):
        c = Cell(api_params={"max_tokens": 2048})
    assert c.max_tokens == 2048
