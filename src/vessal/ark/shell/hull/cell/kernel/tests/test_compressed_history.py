"""test_compressed_history — compressed history built-in signal tests."""
from vessal.ark.shell.hull.cell.kernel.render.signals.compressed_history import render


def test_empty_history_returns_empty():
    assert render({"_compressed_history": ""}) == ""


def test_missing_key_returns_empty():
    assert render({}) == ""


def test_renders_history():
    result = render({"_compressed_history": "Frame 1-10: Initialization complete."})
    assert "Frame 1-10" in result
    assert "history summary" not in result  # title is provided by BASE_SIGNALS infrastructure
