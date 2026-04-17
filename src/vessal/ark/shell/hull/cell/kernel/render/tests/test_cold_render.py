from __future__ import annotations

from vessal.ark.shell.hull.cell.kernel.render._cold_render import (
    project_compaction_record,
    render_cold_zone,
)


def _rec(layer=0, a=0, b=1, intent="t", ops=("op",), outs="o",
         arts=(), notable="") -> dict:
    return {
        "schema_version": 7,
        "range": [a, b],
        "intent": intent,
        "operations": list(ops),
        "outcomes": outs,
        "artifacts": list(arts),
        "notable": notable,
        "layer": layer,
        "compacted_at": b + 1,
    }


def test_project_single_record_contains_sections():
    text = project_compaction_record(_rec(layer=0, a=0, b=15,
                                          intent="build auth",
                                          ops=("hash pw", "store session"),
                                          outs="session token",
                                          arts=("auth.py",),
                                          notable="used bcrypt"))
    assert "## L_0 frames 0" in text
    assert "Intent" in text and "build auth" in text
    assert "Operations" in text and "hash pw" in text
    assert "Outcomes" in text and "session token" in text
    assert "Artifacts" in text and "auth.py" in text
    assert "Notable" in text and "bcrypt" in text


def test_project_skips_empty_fields():
    text = project_compaction_record(_rec(intent="only intent", arts=(), notable=""))
    assert "Intent" in text
    assert "Artifacts" not in text
    assert "Notable" not in text


def test_render_cold_zone_orders_old_to_new():
    cold_view = [
        [_rec(layer=1, a=0, b=31, intent="older block")],
        [_rec(layer=0, a=32, b=47, intent="newer block")],
    ]
    text = render_cold_zone(cold_view)
    assert text.index("L_1") < text.index("L_0")


def test_render_cold_zone_empty_returns_empty_string():
    assert render_cold_zone([]) == ""
    assert render_cold_zone([[]]) == ""
