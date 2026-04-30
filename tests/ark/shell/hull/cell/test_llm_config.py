import pytest
from dataclasses import FrozenInstanceError
from vessal.ark.shell.hull.cell.protocol import LLMConfig


def test_llm_config_has_four_fields():
    cfg = LLMConfig(
        api_key="sk-test",
        base_url="http://localhost:8001/v1",
        model="qwen",
        api_params={"temperature": 0.7, "max_tokens": 4096},
    )
    assert cfg.api_key == "sk-test"
    assert cfg.base_url == "http://localhost:8001/v1"
    assert cfg.model == "qwen"
    assert cfg.api_params == {"temperature": 0.7, "max_tokens": 4096}


def test_llm_config_is_frozen():
    cfg = LLMConfig(api_key="k", base_url="u", model="m", api_params={})
    with pytest.raises(FrozenInstanceError):
        cfg.model = "other"


def test_llm_config_api_params_independent_per_instance():
    """api_params dict identity must not be shared across instances."""
    a = LLMConfig(api_key="k", base_url="u", model="m", api_params={"t": 1})
    b = LLMConfig(api_key="k", base_url="u", model="m", api_params={"t": 2})
    assert a.api_params is not b.api_params
    assert a.api_params == {"t": 1}
