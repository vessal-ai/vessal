from unittest.mock import patch, MagicMock
from vessal.cell.protocol import LLMConfig


def _make_llm_config(**overrides):
    base = dict(api_key="k", base_url="u", model="m", api_params={})
    base.update(overrides)
    return LLMConfig(**base)


def test_cell_max_tokens_defaults_to_4096():
    from vessal.cell import Cell
    with patch("vessal.cell.core.core.openai.OpenAI", return_value=MagicMock()):
        c = Cell()
    assert c.max_tokens == 4096


def test_cell_max_tokens_reads_max_tokens_key():
    from vessal.cell import Cell
    cfg = _make_llm_config(api_params={"max_tokens": 8000})
    with patch("vessal.cell.core.core.openai.OpenAI", return_value=MagicMock()):
        c = Cell(default_llm_config=cfg)
    assert c.max_tokens == 8000


def test_cell_max_tokens_falls_back_to_max_completion_tokens():
    from vessal.cell import Cell
    cfg = _make_llm_config(api_params={"max_completion_tokens": 16000})
    with patch("vessal.cell.core.core.openai.OpenAI", return_value=MagicMock()):
        c = Cell(default_llm_config=cfg)
    assert c.max_tokens == 16000


def test_cell_max_tokens_prefers_max_tokens_over_max_completion_tokens():
    from vessal.cell import Cell
    cfg = _make_llm_config(api_params={"max_tokens": 1000, "max_completion_tokens": 2000})
    with patch("vessal.cell.core.core.openai.OpenAI", return_value=MagicMock()):
        c = Cell(default_llm_config=cfg)
    assert c.max_tokens == 1000
