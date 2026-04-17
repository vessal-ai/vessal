from vessal.ark.shell.tui.create_wizard import DEFAULT_ANSWERS, finalize_answers


def test_defaults_include_all_six():
    assert set(DEFAULT_ANSWERS.keys()) == {"name", "provider", "api_key", "template", "dockerize", "deploy"}


def test_finalize_fills_missing_with_defaults():
    answers = finalize_answers({"name": "hello"})
    assert answers["name"] == "hello"
    assert answers["provider"] == DEFAULT_ANSWERS["provider"]
    assert answers["template"] == DEFAULT_ANSWERS["template"]


def test_finalize_rejects_empty_name():
    import pytest
    with pytest.raises(ValueError):
        finalize_answers({"name": ""})
