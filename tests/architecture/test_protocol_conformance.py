"""test_protocol_conformance — Protocol dataclass conformance validation.

Verifies that frame protocol dataclasses are frozen=True and checks key field structure.
"""
import dataclasses
import importlib
import inspect


def _discover_dataclasses(module_path: str) -> list[tuple[str, type]]:
    """Dynamically discover all dataclass classes in a module.

    Args:
        module_path: Dot-separated module path.
    Returns:
        List of (class_name, class) tuples.
    """
    mod = importlib.import_module(module_path)
    results = []
    for name, obj in inspect.getmembers(mod, inspect.isclass):
        if dataclasses.is_dataclass(obj) and obj.__module__ == mod.__name__:
            results.append((name, obj))
    return results


def test_frame_record_dataclasses_are_frozen():
    """All dataclasses in protocol.py are frozen=True."""
    classes = _discover_dataclasses("vessal.ark.shell.hull.cell.protocol")
    assert len(classes) > 0, "No dataclasses found, check module path"
    not_frozen = []
    for name, cls in classes:
        if not cls.__dataclass_params__.frozen:
            not_frozen.append(name)
    assert not_frozen == [], f"Non-frozen dataclasses: {not_frozen}"


def _get_field_names(cls: type) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


def test_pong_has_think_and_action():
    """Pong has think and action fields, does not directly expose operation/expect."""
    from vessal.ark.shell.hull.cell.protocol import Pong, Action  # noqa: F401

    fields = _get_field_names(Pong)
    assert "think" in fields, f"Pong missing think field, current fields: {fields}"
    assert "action" in fields, f"Pong missing action field, current fields: {fields}"
    assert "operation" not in fields, "Pong should not have operation field directly (should be in Action)"
    assert "expect" not in fields, "Pong should not have expect field directly (should be in Action)"


def test_action_has_operation_and_expect():
    """Action has operation and expect fields."""
    from vessal.ark.shell.hull.cell.protocol import Action

    fields = _get_field_names(Action)
    assert "operation" in fields, f"Action missing operation field, current fields: {fields}"
    assert "expect" in fields, f"Action missing expect field, current fields: {fields}"


def test_ping_has_system_prompt_and_state():
    """Ping has system_prompt and state fields, does not directly expose frame_stream/signals."""
    from vessal.ark.shell.hull.cell.protocol import Ping, State  # noqa: F401

    fields = _get_field_names(Ping)
    assert "system_prompt" in fields, f"Ping missing system_prompt field, current fields: {fields}"
    assert "state" in fields, f"Ping missing state field, current fields: {fields}"
    assert "frame_stream" not in fields, "Ping should not have frame_stream field directly (should be in State)"
    assert "signals" not in fields, "Ping should not have signals field directly (should be in State)"


def test_state_has_frame_stream_and_signals():
    """State has frame_stream and signals fields."""
    from vessal.ark.shell.hull.cell.protocol import State

    fields = _get_field_names(State)
    assert "frame_stream" in fields, f"State missing frame_stream field, current fields: {fields}"
    assert "signals" in fields, f"State missing signals field, current fields: {fields}"


def test_token_usage_not_in_protocol():
    """TokenUsage should not exist in the protocol module."""
    import vessal.ark.shell.hull.cell.protocol as proto

    assert not hasattr(proto, "TokenUsage"), "TokenUsage should not appear in the protocol module"


def test_step_result_has_only_protocol_error():
    """StepResult has only the protocol_error field."""
    from vessal.ark.shell.hull.cell.protocol import StepResult

    fields = _get_field_names(StepResult)
    assert fields == {"protocol_error"}, (
        f"StepResult should have only protocol_error field, actual fields: {fields}"
    )
