"""Unit tests for component factory methods."""
from vessal.skills.ui.components import text, card, button, input_field, panel, chart


class TestText:
    def test_basic(self):
        c = text("hello")
        assert c["type"] == "text"
        assert c["props"]["content"] == "hello"

    def test_with_props(self):
        c = text("hello", bold=True)
        assert c["props"]["bold"] is True


class TestCard:
    def test_basic(self):
        c = card([text("hi")])
        assert c["type"] == "card"
        assert len(c["children"]) == 1
        assert c["children"][0]["type"] == "text"

    def test_with_title(self):
        c = card([text("hi")], title="Header")
        assert c["props"]["title"] == "Header"


class TestButton:
    def test_basic(self):
        c = button("Click me", id="btn-1")
        assert c["type"] == "button"
        assert c["props"]["label"] == "Click me"
        assert c["props"]["id"] == "btn-1"

    def test_no_id_raises(self):
        import pytest
        with pytest.raises(ValueError, match="id"):
            button("Click me")


class TestInputField:
    def test_basic(self):
        c = input_field("Enter name", id="name-input")
        assert c["type"] == "input"
        assert c["props"]["placeholder"] == "Enter name"
        assert c["props"]["id"] == "name-input"

    def test_no_id_raises(self):
        import pytest
        with pytest.raises(ValueError, match="id"):
            input_field("placeholder")


class TestPanel:
    def test_basic(self):
        c = panel("Results", [text("data")])
        assert c["type"] == "panel"
        assert c["props"]["title"] == "Results"
        assert len(c["children"]) == 1

    def test_with_position(self):
        c = panel("Side", [button("go", id="go")], position="right")
        assert c["props"]["position"] == "right"


class TestChart:
    def test_basic(self):
        c = chart([1, 2, 3], kind="bar")
        assert c["type"] == "chart"
        assert c["props"]["data"] == [1, 2, 3]
        assert c["props"]["kind"] == "bar"

    def test_default_kind(self):
        c = chart([1, 2])
        assert c["props"]["kind"] == "bar"


class TestNesting:
    def test_panel_with_card_with_children(self):
        c = panel("Test", [
            card([
                text("hello"),
                button("go", id="go"),
            ]),
        ])
        assert c["type"] == "panel"
        assert c["children"][0]["type"] == "card"
        assert c["children"][0]["children"][0]["type"] == "text"
        assert c["children"][0]["children"][1]["type"] == "button"


class TestJsonSerializable:
    def test_all_components_json_safe(self):
        import json
        components = [
            text("hi"),
            card([text("x")]),
            button("b", id="b"),
            input_field("p", id="i"),
            panel("t", [text("c")]),
            chart([1, 2, 3]),
        ]
        for c in components:
            json.dumps(c)  # Should not raise
