"""UI Skill integration tests."""
import json

from vessal.ark.shell.hull.skill import SkillBase
from vessal.skills.ui.skill import UI


class TestUIBase:
    def test_is_skillbase(self):
        assert issubclass(UI, SkillBase)

    def test_has_required_attrs(self):
        assert isinstance(UI.name, str) and UI.name == "ui"
        assert isinstance(UI.description, str) and UI.description

    def test_init_no_args(self):
        ui = UI()
        assert ui.body is not None
        assert ui._inbox == []


class TestRender:
    def test_render_stores_components(self):
        ui = UI()
        ui.render([ui.text("hello")])
        assert len(ui._components) == 1
        assert ui._components[0]["type"] == "text"

    def test_render_replaces_previous(self):
        ui = UI()
        ui.render([ui.text("first")])
        ui.render([ui.text("second")])
        assert len(ui._components) == 1
        assert ui._components[0]["props"]["content"] == "second"

    def test_render_pushes_to_outbox(self):
        ui = UI()
        ui.render([ui.card([ui.text("hi")])])
        assert len(ui._outbox) == 1
        spec = ui._outbox[0]
        assert "body" in spec
        assert "components" in spec

    def test_render_spec_json_serializable(self):
        ui = UI()
        ui.body.speak("hello")
        ui.render([ui.button("go", id="go")])
        spec = ui._outbox[0]
        json.dumps(spec)  # Should not raise

    def test_render_drains_body_actions_between_calls(self):
        """Second render() should see empty body actions from fresh drain."""
        ui = UI()
        ui.body.speak("first message")
        ui.render([ui.text("page 1")])
        # Now do a second render with a new body action
        ui.body.emote("happy")
        ui.render([ui.text("page 2")])
        # First spec should have speak action
        first_spec = ui._outbox[0]
        assert len(first_spec["body"]["actions"]) >= 1
        assert first_spec["body"]["actions"][0]["type"] == "speak"
        # Second spec should only have emote action (not the earlier speak)
        second_spec = ui._outbox[1]
        action_types = [a["type"] for a in second_spec["body"]["actions"]]
        assert "speak" not in action_types
        assert "emote" in action_types


class TestRead:
    def test_read_empty(self):
        ui = UI()
        events = ui.read()
        assert events == []

    def test_read_returns_and_clears(self):
        ui = UI()
        ui._inbox.append({"event": "click", "id": "btn-1", "ts": 1.0})
        ui._inbox.append({"event": "avatar_tap", "ts": 2.0})
        events = ui.read()
        assert len(events) == 2
        assert ui._inbox == []

    def test_read_preserves_order(self):
        ui = UI()
        ui._inbox.append({"event": "click", "id": "a", "ts": 1.0})
        ui._inbox.append({"event": "click", "id": "b", "ts": 2.0})
        events = ui.read()
        assert events[0]["id"] == "a"
        assert events[1]["id"] == "b"


class TestCurrentLayout:
    def test_empty(self):
        ui = UI()
        layout = ui.current_layout()
        assert "body" in layout
        assert layout["components"] == []

    def test_after_render(self):
        ui = UI()
        ui.render([ui.panel("Test", [ui.text("data")])])
        layout = ui.current_layout()
        assert len(layout["components"]) == 1
        assert layout["components"][0]["type"] == "panel"


class TestComponentMethods:
    """Verify component factory methods on the UI instance."""
    def test_text(self):
        ui = UI()
        c = ui.text("hello")
        assert c["type"] == "text"

    def test_card(self):
        ui = UI()
        c = ui.card([ui.text("x")])
        assert c["type"] == "card"

    def test_button(self):
        ui = UI()
        c = ui.button("go", id="go")
        assert c["type"] == "button"

    def test_input(self):
        ui = UI()
        c = ui.input("placeholder", id="inp")
        assert c["type"] == "input"

    def test_panel(self):
        ui = UI()
        c = ui.panel("title", [ui.text("x")])
        assert c["type"] == "panel"

    def test_chart(self):
        ui = UI()
        c = ui.chart([1, 2], kind="line")
        assert c["type"] == "chart"


class TestSignal:
    def test_signal_none_when_empty_and_no_events(self):
        ui = UI()
        result = ui._signal()
        # Even with empty page, signal should show body state
        assert result is not None

    def test_signal_shows_body_state(self):
        ui = UI()
        ui.body.emote("thinking")
        result = ui._signal()
        _, body = result
        assert "thinking" in body

    def test_signal_shows_components(self):
        ui = UI()
        ui.render([ui.panel("Data", [ui.text("x")])])
        _, body = ui._signal()
        assert "Data" in body

    def test_signal_shows_pending_events(self):
        ui = UI()
        ui._inbox.append({"event": "click", "id": "btn", "ts": 1.0})
        _, body = ui._signal()
        assert "pending: 1" in body


class TestPrompt:
    def test_prompt_returns_tuple(self):
        ui = UI()
        result = ui._prompt()
        assert isinstance(result, tuple)
        assert len(result) == 2
        condition, methodology = result
        assert isinstance(condition, str) and condition.strip()
        assert isinstance(methodology, str) and methodology.strip()

    def test_prompt_mentions_render(self):
        ui = UI()
        _, methodology = ui._prompt()
        assert "render" in methodology

    def test_prompt_mentions_signal(self):
        """Cognitive protocol must guide Agent to check signal first."""
        ui = UI()
        condition, methodology = ui._prompt()
        assert "signal" in condition or "signal" in methodology

    def test_prompt_no_method_signatures(self):
        """_prompt() must not contain method signatures."""
        ui = UI()
        _, methodology = ui._prompt()
        assert "ui.render(" not in methodology
        assert "ui.read(" not in methodology


class TestDrainOutbox:
    def test_drain_returns_and_clears(self):
        ui = UI()
        ui.render([ui.text("a")])
        ui.render([ui.text("b")])
        msgs = ui.drain_outbox()
        assert len(msgs) == 2
        assert ui._outbox == []


class TestReceiveEvent:
    def test_receive_adds_to_inbox(self):
        ui = UI()
        ui.receive_event({"event": "click", "id": "x", "ts": 1.0})
        assert len(ui._inbox) == 1
        assert ui._inbox[0]["event"] == "click"
