"""test_skills — merged Skills(SkillBase) class contract."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vessal.skills._base import BaseSkill
from vessal.skills.skills.skill import Skills


@pytest.fixture
def hull():
    h = MagicMock()
    h.available_skills.return_value = [{"name": "chat", "description": "chat desc"}]
    h.has_skill_server.return_value = False
    h.get_ns.return_value = None
    h.ns_keys.return_value = []
    h.loaded_skill_names.return_value = []
    return h


@pytest.fixture
def skills(hull):
    s = Skills()
    s._bind_hull(hull)
    return s


# ── Class-level contract ──

def test_inherits_skillbase():
    assert issubclass(Skills, BaseSkill)


def test_name_and_description_are_class_attrs():
    assert Skills.name == "skills"
    assert isinstance(Skills.description, str) and Skills.description


def test_tools_list_uses_new_names():
    assert "load" in Skills.tools
    assert "unload" in Skills.tools
    assert "load_skill" not in Skills.tools


# ── list / load / unload ──

def test_list_delegates_to_hull(skills, hull):
    result = skills.list()
    assert isinstance(result, list)
    hull.available_skills.assert_called_once()


def test_load_no_server_returns_loaded_message(skills, hull):
    result = skills.load("chat")
    assert "loaded" in result
    hull.load_skill.assert_called_once_with("chat")


def test_load_phase1_failure_returns_error_string(skills, hull):
    hull.load_skill.side_effect = Exception("no such skill")
    result = skills.load("ghost")
    assert "load failed" in result


def test_load_server_failure_rolls_back_phase1(skills, hull):
    hull.has_skill_server.return_value = True
    hull.start_skill_server.side_effect = Exception("port in use")

    result = skills.load("chat")
    assert "failed" in result
    hull.set_ns.assert_any_call("chat", None)
    hull.unload_skill_from_manager.assert_called_once_with("chat")


def test_unload_clears_instance_and_stops_server(skills, hull):
    hull.get_ns.return_value = None
    result = skills.unload("chat")
    assert "unloaded" in result
    hull.stop_skill_server.assert_called_once_with("chat")
    hull.unload_skill_from_manager.assert_called_once_with("chat")


# ── signal / prompt ──

def test_signal_lists_available_with_load_markers(hull):
    hull.available_skills.return_value = [
        {"name": "chat", "description": "chat"},
        {"name": "search", "description": "search"},
    ]
    hull.loaded_skill_names.return_value = ["chat"]

    s = Skills()
    s._bind_hull(hull)
    s.signal_update()
    assert s.signal != {}
    body = s.signal["available"]
    assert "[loaded]" in body and "[available]" in body
    assert "chat" in body and "search" in body


def test_signal_contains_guide_reminder(hull):
    hull.available_skills.return_value = []
    hull.loaded_skill_names.return_value = []
    s = Skills()
    s._bind_hull(hull)
    s.signal_update()
    body = s.signal["available"]
    assert "print(" in body and "guide)" in body


def test_signal_has_no_method_names(hull):
    hull.available_skills.return_value = [{"name": "chat", "description": "desc"}]
    hull.loaded_skill_names.return_value = []
    s = Skills()
    s._bind_hull(hull)
    s.signal_update()
    body = s.signal["available"]
    for forbidden in ("load(", "unload(", "load_skill", "unload_skill"):
        assert forbidden not in body


def test_prompt_is_valid_cognitive_protocol(skills):
    result = skills._prompt()
    assert isinstance(result, tuple) and len(result) == 2
    condition, methodology = result
    assert condition.strip() and methodology.strip()
    assert "guide" in methodology


# ── hub interactions ──

def test_search_hub_returns_matches(skills):
    with patch("vessal.skills.skills.skill.Registry") as mock_reg:
        mock_reg.fetch.return_value.search.return_value = [
            {"name": "browser", "description": "web", "source": "x", "tags": ["web"]}
        ]
        result = skills.search_hub("web")
    assert "browser" in result


def test_list_hub_returns_paged(skills):
    with patch("vessal.skills.skills.skill.Registry") as mock_reg:
        instance = mock_reg.fetch.return_value
        instance.list_paged.return_value = [
            {"name": "a", "description": "da", "source": "x", "tags": []},
        ]
        instance.list_all.return_value = instance.list_paged.return_value
        result = skills.list_hub(page=1)
    assert "a" in result


def test_signal_returns_empty_when_hull_unbound():
    s = Skills()
    s.signal_update()
    assert s.signal == {}
