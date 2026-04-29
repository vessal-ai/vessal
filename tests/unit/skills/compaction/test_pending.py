"""Unit tests for PendingView / PendingGroup dataclasses."""


def test_pending_group_fields():
    from vessal.skills.compaction._pending import PendingGroup
    g = PendingGroup(layer=0, n_start=1, n_end=4, items=[{"n": 1}, {"n": 2}, {"n": 3}, {"n": 4}])
    assert g.layer == 0
    assert g.n_start == 1
    assert g.n_end == 4
    assert len(g.items) == 4


def test_pending_view_fields():
    from vessal.skills.compaction._pending import PendingGroup, PendingView
    g = PendingGroup(layer=0, n_start=1, n_end=4, items=[])
    view = PendingView(groups=[g])
    assert view.groups == [g]
