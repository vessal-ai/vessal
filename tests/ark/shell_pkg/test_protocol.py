"""Test Shell↔Hull protocol type definitions."""
from vessal.ark.shell.protocol import HandleResult


def test_handle_result_is_tuple_alias():
    """HandleResult is a type alias for the handle() return type."""
    from vessal.ark.shell.hull.hull_api import StaticResponse

    result_dict: HandleResult = (200, {"status": "ok"})
    result_static: HandleResult = (200, StaticResponse(b"hi", "text/plain"))

    assert result_dict[0] == 200
    assert result_static[0] == 200
