from vessal.ark.shell.tui.create_wizard import DEFAULT_ANSWERS, finalize_answers


def test_defaults_include_all_keys():
    assert set(DEFAULT_ANSWERS.keys()) == {"name", "api_key", "base_url", "model", "dockerize"}


def test_finalize_fills_missing_with_defaults():
    answers = finalize_answers({"name": "hello"})
    assert answers["name"] == "hello"
    assert answers["dockerize"] == DEFAULT_ANSWERS["dockerize"]
    assert answers["model"] == DEFAULT_ANSWERS["model"]


def test_finalize_rejects_empty_name():
    import pytest
    with pytest.raises(ValueError):
        finalize_answers({"name": ""})
