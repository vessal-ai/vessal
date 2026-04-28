"""test_no_hull_compaction.py — PR 5: Hull no longer hosts compaction worker."""
from __future__ import annotations
import os


def test_hull_runtime_mixin_no_compaction_methods():
    from vessal.ark.shell.hull import hull_runtime_mixin
    src = open(hull_runtime_mixin.__file__).read()
    assert "_drain_compaction_results" not in src
    assert "_try_shift_compaction" not in src
    assert "/state/compactions" not in src


def test_hull_no_compaction_thread_pool():
    from vessal.ark.shell.hull import hull_init_mixin
    src = open(hull_init_mixin.__file__).read()
    assert "_compaction_thread_pool" not in src
    assert "_compaction_result_queue" not in src
    assert "compression_core" not in src
    assert "_compaction_k" not in src
    assert "_compaction_n" not in src


def test_hull_compaction_mixin_renamed_to_snapshot_only():
    """hull_compaction_mixin.py is renamed; no compaction methods remain."""
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    old = os.path.join(repo, "src/vessal/ark/shell/hull/hull_compaction_mixin.py")
    new = os.path.join(repo, "src/vessal/ark/shell/hull/hull_snapshot_mixin.py")
    assert not os.path.exists(old), "hull_compaction_mixin.py must be renamed/deleted"
    assert os.path.exists(new), "hull_snapshot_mixin.py expected"
    src = open(new).read()
    assert "_resume_pending_compaction" not in src
    assert "_run_compaction_task" not in src
    assert "_build_compression_ping" not in src
