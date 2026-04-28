"""Spec §3 / §08 invariants on Observation."""
from __future__ import annotations

import dataclasses

from vessal.ark.shell.hull.cell.protocol import Observation


def test_observation_has_only_four_fields() -> None:
    field_names = {f.name for f in dataclasses.fields(Observation)}
    assert field_names == {"stdout", "stderr", "diff", "error"}, (
        "Spec §3: observation = {stdout, stderr, diff, error}. "
        "verdict is its own L key, not nested in Observation."
    )


def test_observation_error_field_is_exception_or_none() -> None:
    o_clean = Observation(stdout="", stderr="", diff="", error=None)
    assert o_clean.error is None

    e = ZeroDivisionError("division by zero")
    o_err = Observation(stdout="", stderr="", diff="", error=e)
    assert o_err.error is e
    assert isinstance(o_err.error, ZeroDivisionError)


def test_observation_to_dict_serialises_error_via_repr() -> None:
    """to_dict must produce a string for error (JSON-serialisable); in-memory L holds raw exception."""
    e = ValueError("bad")
    o = Observation(stdout="x\n", stderr="", diff="", error=e)
    d = o.to_dict()
    assert d["stdout"] == "x\n"
    assert d["stderr"] == ""
    assert d["diff"] == ""
    assert "ValueError" in d["error"]
    assert "bad" in d["error"]
    assert "verdict" not in d
