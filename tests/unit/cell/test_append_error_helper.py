"""test_append_error_helper.py — Unit tests for the _errors_helper ring buffer."""


def test_append_error_caps_at_given_size():
    from vessal.ark.shell.hull.cell._errors_helper import append_error
    ns = {"_errors": [], "_error_buffer_cap": 3}
    for i in range(5):
        append_error(ns, {"i": i})
    assert len(ns["_errors"]) == 3
    assert [r["i"] for r in ns["_errors"]] == [2, 3, 4]


def test_append_error_respects_override_cap_arg():
    from vessal.ark.shell.hull.cell._errors_helper import append_error
    ns = {"_errors": [], "_error_buffer_cap": 1000}
    for i in range(5):
        append_error(ns, {"i": i}, cap=2)
    assert len(ns["_errors"]) == 2
