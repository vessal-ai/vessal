"""test_create_wizard — unit tests for wizard finalize + env template logic."""
from __future__ import annotations

from vessal.ark.shell.tui.create_wizard import DEFAULT_ANSWERS, _build_env_content, finalize_answers


def test_build_env_content_all_values_provided():
    content = _build_env_content(api_key="sk-abc", base_url="https://api.openai.com/v1", model="gpt-4o")
    assert "OPENAI_API_KEY=sk-abc" in content
    assert "OPENAI_BASE_URL=https://api.openai.com/v1" in content
    assert "OPENAI_MODEL=gpt-4o" in content
    # no Chinese characters
    assert all(ord(c) < 128 for c in content)


def test_build_env_content_all_skipped_uses_english_placeholders():
    content = _build_env_content(api_key="", base_url="", model="")
    # All three keys present with placeholder comments
    assert "OPENAI_API_KEY=" in content
    assert "OPENAI_BASE_URL=" in content
    assert "OPENAI_MODEL=" in content
    # Placeholders are English
    lowered = content.lower()
    assert "your api key" in lowered or "paste" in lowered
    assert all(ord(c) < 128 for c in content)


def test_build_env_content_partial_fills_rest_with_placeholder():
    content = _build_env_content(api_key="sk-abc", base_url="", model="")
    assert "OPENAI_API_KEY=sk-abc" in content
    # base_url / model lines still present as placeholders
    assert "OPENAI_BASE_URL=" in content
    assert "OPENAI_MODEL=" in content


def test_finalize_answers_requires_name():
    import pytest
    with pytest.raises(ValueError):
        finalize_answers({"name": ""})


def test_finalize_answers_defaults_applied():
    merged = finalize_answers({"name": "my-agent"})
    assert merged["name"] == "my-agent"
    assert merged["dockerize"] is False


def test_defaults_include_all_keys():
    assert set(DEFAULT_ANSWERS.keys()) == {"name", "api_key", "base_url", "model", "dockerize"}


def test_finalize_fills_missing_with_defaults():
    merged = finalize_answers({"name": "hello"})
    assert set(merged.keys()) == set(DEFAULT_ANSWERS.keys())
    for key in ("api_key", "base_url", "model", "dockerize"):
        assert merged[key] == DEFAULT_ANSWERS[key]


def test_validate_project_name_rejects_existing_dir(tmp_path):
    from vessal.ark.shell.tui.create_wizard import validate_project_name
    (tmp_path / "agent_test").mkdir()
    error = validate_project_name("agent_test", tmp_path)
    assert error is not None
    assert "agent_test" in error
    assert "exists" in error.lower()


def test_validate_project_name_accepts_unused_name(tmp_path):
    from vessal.ark.shell.tui.create_wizard import validate_project_name
    assert validate_project_name("fresh-agent", tmp_path) is None


def test_validate_project_name_rejects_empty(tmp_path):
    from vessal.ark.shell.tui.create_wizard import validate_project_name
    error = validate_project_name("", tmp_path)
    assert error is not None
    assert "empty" in error.lower()
