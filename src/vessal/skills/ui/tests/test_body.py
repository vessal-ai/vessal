"""Body unit tests — avatar action queue and serialization."""
from vessal.skills.ui.body import Body


class TestBodyInit:
    def test_default_state(self):
        b = Body()
        assert b.position == (0, 0)
        assert b.emotion == "idle"
        assert b.speech == ""

    def test_actions_empty(self):
        b = Body()
        assert b._actions == []


class TestBodyActions:
    def test_move_to_tuple(self):
        b = Body()
        b.move_to((100, 200))
        assert b.position == (100, 200)
        assert len(b._actions) == 1
        assert b._actions[0]["type"] == "move"

    def test_move_to_element_id(self):
        b = Body()
        b.move_to("panel-1")
        assert b.position == "panel-1"
        assert b._actions[0]["target"] == "panel-1"

    def test_speak(self):
        b = Body()
        b.speak("hello")
        assert b.speech == "hello"
        assert b._actions[0]["type"] == "speak"
        assert b._actions[0]["text"] == "hello"
        assert b._actions[0]["duration"] == 3

    def test_speak_custom_duration(self):
        b = Body()
        b.speak("hi", duration=5)
        assert b._actions[0]["duration"] == 5

    def test_emote(self):
        b = Body()
        b.emote("thinking")
        assert b.emotion == "thinking"
        assert b._actions[0]["type"] == "emote"
        assert b._actions[0]["emotion"] == "thinking"

    def test_point_at(self):
        b = Body()
        b.point_at("chart-1")
        assert b._actions[0]["type"] == "point"
        assert b._actions[0]["target"] == "chart-1"

    def test_offer_choices(self):
        b = Body()
        b.offer_choices(["A", "B", "C"])
        assert b._actions[0]["type"] == "offer_choices"
        assert b._actions[0]["options"] == ["A", "B", "C"]

    def test_ask(self):
        b = Body()
        b.ask("What would you like to explore?")
        assert b._actions[0]["type"] == "ask"
        assert b._actions[0]["prompt"] == "What would you like to explore?"

    def test_multiple_actions_in_order(self):
        b = Body()
        b.move_to((50, 50))
        b.speak("hi")
        b.emote("happy")
        assert len(b._actions) == 3
        assert [a["type"] for a in b._actions] == ["move", "speak", "emote"]


class TestBodySerialize:
    def test_serialize_empty(self):
        b = Body()
        spec = b._serialize()
        assert spec["state"]["position"] == (0, 0)
        assert spec["state"]["emotion"] == "idle"
        assert spec["state"]["speech"] == ""
        assert spec["actions"] == []

    def test_serialize_with_actions(self):
        b = Body()
        b.move_to((100, 200))
        b.speak("hello")
        spec = b._serialize()
        assert len(spec["actions"]) == 2
        assert spec["state"]["position"] == (100, 200)
        assert spec["state"]["speech"] == "hello"

    def test_serialize_interactions(self):
        b = Body()
        b.offer_choices(["A", "B"])
        b.ask("input?")
        spec = b._serialize()
        interactions = spec["interactions"]
        assert len(interactions) == 2
        assert interactions[0]["type"] == "choices"
        assert interactions[1]["type"] == "ask"

    def test_serialize_does_not_share_references(self):
        b = Body()
        b.offer_choices(["A", "B"])
        spec = b._serialize()
        spec["actions"][0]["options"].append("INJECTED")
        assert b._actions[0]["options"] == ["A", "B"]


class TestBodyReset:
    def test_drain_clears_actions(self):
        b = Body()
        b.move_to((1, 1))
        b.speak("hi")
        spec = b._drain()
        assert len(spec["actions"]) == 2
        assert b._actions == []

    def test_drain_clears_interactions(self):
        b = Body()
        b.offer_choices(["X"])
        spec = b._drain()
        assert spec["interactions"] == [{"type": "choices", "options": ["X"]}]
        # After drain, interactions cleared
        spec2 = b._drain()
        assert spec2["interactions"] == []

    def test_drain_preserves_state(self):
        b = Body()
        b.move_to((50, 50))
        b.emote("happy")
        b._drain()
        assert b.position == (50, 50)
        assert b.emotion == "happy"
