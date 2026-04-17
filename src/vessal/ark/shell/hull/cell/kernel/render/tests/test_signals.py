from __future__ import annotations


def test_compressed_history_signal_removed():
    from vessal.ark.shell.hull.cell.kernel.render.signals import BASE_SIGNALS
    signal_names = [name for name, _ in BASE_SIGNALS]
    assert "history summary" not in signal_names
