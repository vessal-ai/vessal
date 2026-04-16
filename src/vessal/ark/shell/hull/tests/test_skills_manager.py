"""Test SkillsManager: list, load, unload (renamed from list_skills, load_skill, unload_skill)."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_hull():
    hull = MagicMock()
    hull.available_skills.return_value = [{"name": "human", "description": "Human skill"}]
    hull.has_skill_server.return_value = False
    hull.get_ns.return_value = None
    hull.ns_keys.return_value = []
    hull.loaded_skill_names.return_value = []
    return hull


def test_list(mock_hull):
    from vessal.ark.shell.hull.skills_manager import SkillsManager
    meta = SkillsManager(mock_hull)
    result = meta.list()
    assert isinstance(result, list)
    mock_hull.available_skills.assert_called_once()


def test_load_no_server(mock_hull):
    from vessal.ark.shell.hull.skills_manager import SkillsManager
    meta = SkillsManager(mock_hull)
    result = meta.load("human")
    assert "loaded" in result
    mock_hull.load_skill.assert_called_once_with("human")


def test_load_phase1_failure(mock_hull):
    from vessal.ark.shell.hull.skills_manager import SkillsManager
    mock_hull.load_skill.side_effect = Exception("no such skill")

    meta = SkillsManager(mock_hull)
    result = meta.load("nonexistent")
    assert "load failed" in result


def test_unload(mock_hull):
    from vessal.ark.shell.hull.skills_manager import SkillsManager
    mock_hull.get_ns.return_value = None  # no instance in namespace
    meta = SkillsManager(mock_hull)
    result = meta.unload("human")
    assert "unloaded" in result
    mock_hull.stop_skill_server.assert_called_once_with("human")
    mock_hull.unload_skill_from_manager.assert_called_once_with("human")


def test_signal_lists_available_skills(mock_hull):
    """_signal() output contains all available skill names and descriptions."""
    from vessal.ark.shell.hull.skills_manager import SkillsManager
    mock_hull.available_skills.return_value = [
        {"name": "human", "description": "send/receive human messages"},
        {"name": "search", "description": "search tool"},
    ]
    mock_hull.loaded_skill_names.return_value = ["human"]

    meta = SkillsManager(mock_hull)
    result = meta._signal()

    assert result is not None
    title, body = result
    assert "available skills" in title
    assert "human" in body
    assert "search" in body
    assert "[loaded]" in body
    assert "[available]" in body


def test_signal_contains_guide_reminder(mock_hull):
    """_signal() ends with a guide usage reminder."""
    from vessal.ark.shell.hull.skills_manager import SkillsManager
    mock_hull.available_skills.return_value = []
    mock_hull.loaded_skill_names.return_value = []

    meta = SkillsManager(mock_hull)
    result = meta._signal()

    assert result is not None
    _, body = result
    assert "print(" in body
    assert "guide)" in body


def test_signal_no_method_names(mock_hull):
    """_signal() must not contain method names (load/unload/list, etc.)."""
    from vessal.ark.shell.hull.skills_manager import SkillsManager
    mock_hull.available_skills.return_value = [
        {"name": "chat", "description": "send/receive human messages"},
    ]
    mock_hull.loaded_skill_names.return_value = []

    meta = SkillsManager(mock_hull)
    result = meta._signal()
    _, body = result
    # API method names should not appear in the signal
    assert "load(" not in body
    assert "unload(" not in body
    assert "load_skill" not in body
    assert "unload_skill" not in body


def test_load_server_failure_rolls_back(mock_hull):
    """When server startup fails, phase 1 is rolled back — cleaning up namespace and skill_manager."""
    from vessal.ark.shell.hull.skills_manager import SkillsManager
    mock_hull.has_skill_server.return_value = True
    mock_hull.start_skill_server.side_effect = Exception("port in use")

    meta = SkillsManager(mock_hull)
    result = meta.load("human")
    assert "failed" in result
    mock_hull.set_ns.assert_any_call("human", None)
    mock_hull.unload_skill_from_manager.assert_called_once_with("human")


def test_name_is_skills():
    """SkillsManager.name should be 'skills', not '_meta'."""
    from vessal.ark.shell.hull.skills_manager import SkillsManager
    assert SkillsManager.name == "skills"


def test_tools_uses_new_names():
    """tools list uses new method names."""
    from vessal.ark.shell.hull.skills_manager import SkillsManager
    assert "load" in SkillsManager.tools
    assert "unload" in SkillsManager.tools
    assert "load_skill" not in SkillsManager.tools
    assert "unload_skill" not in SkillsManager.tools
    assert "query_guide" not in SkillsManager.tools


def test_search_hub_returns_results():
    from vessal.ark.shell.hull.skills_manager import SkillsManager

    hull = MagicMock()
    sm = SkillsManager(hull)

    with patch("vessal.ark.shell.hull.skills_manager.Registry") as MockReg:
        mock_instance = MockReg.fetch.return_value
        mock_instance.search.return_value = [
            {"name": "browser", "description": "web browsing", "source": "x", "tags": ["web"]}
        ]
        result = sm.search_hub("web")

    assert "browser" in result
    assert "web browsing" in result


def test_list_hub_returns_paged():
    from vessal.ark.shell.hull.skills_manager import SkillsManager

    hull = MagicMock()
    sm = SkillsManager(hull)

    with patch("vessal.ark.shell.hull.skills_manager.Registry") as MockReg:
        mock_instance = MockReg.fetch.return_value
        mock_instance.list_paged.return_value = [
            {"name": "a", "description": "desc a", "source": "x", "tags": []},
            {"name": "b", "description": "desc b", "source": "y", "tags": []},
        ]
        mock_instance.list_all.return_value = [
            {"name": "a", "description": "desc a", "source": "x", "tags": []},
            {"name": "b", "description": "desc b", "source": "y", "tags": []},
        ]
        result = sm.list_hub(page=1)

    assert "a" in result
    assert "b" in result


def test_skills_manager_prompt(mock_hull):
    """SkillsManager._prompt() returns a valid cognitive protocol."""
    from vessal.ark.shell.hull.skills_manager import SkillsManager

    ms = SkillsManager(mock_hull)
    result = ms._prompt()
    assert isinstance(result, tuple)
    assert len(result) == 2
    condition, methodology = result
    assert isinstance(condition, str) and condition.strip()
    assert isinstance(methodology, str) and methodology.strip()
    assert "guide" in methodology
