"""Unit tests for the compaction trigger SQL — finds the lowest layer with
>=k uncovered entries against the main Cell's frame_log."""


def _seed(path, layer_counts):
    """layer_counts: dict[layer -> count]. Inserts that many disjoint entries on each layer."""
    import sqlite3
    from vessal.cell.kernel.frame_log.schema import open_db
    conn = open_db(path)
    n = 1
    for layer, count in sorted(layer_counts.items()):
        for _ in range(count):
            conn.execute("INSERT INTO entries(layer, n_start, n_end) VALUES (?, ?, ?)", (layer, n, n))
            n += 1
    conn.close()


def test_no_compaction_when_layer0_below_k(tmp_path):
    from vessal.hull._compaction_trigger import should_compact
    db = str(tmp_path / "main.sqlite")
    _seed(db, {0: 3})
    assert should_compact(db, k=4) is False


def test_compaction_when_layer0_at_k(tmp_path):
    from vessal.hull._compaction_trigger import should_compact
    db = str(tmp_path / "main.sqlite")
    _seed(db, {0: 4})
    assert should_compact(db, k=4) is True


def test_compaction_when_higher_layer_at_k(tmp_path):
    """4 layer-1 entries, layer-0 fully covered → still triggers."""
    import sqlite3
    from vessal.cell.kernel.frame_log.schema import open_db
    from vessal.hull._compaction_trigger import should_compact

    db = str(tmp_path / "main.sqlite")
    conn = open_db(db)
    # 4 layer-1 entries spanning n=1..4, n=5..8, n=9..12, n=13..16
    spans = [(1, 4), (5, 8), (9, 12), (13, 16)]
    for ns, ne in spans:
        conn.execute("INSERT INTO entries(layer, n_start, n_end) VALUES (1, ?, ?)", (ns, ne))
    conn.close()

    assert should_compact(db, k=4) is True
