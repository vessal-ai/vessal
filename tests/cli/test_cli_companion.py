"""test_cli_companion — Companion App configuration parsing and process management tests."""
import tomllib
from pathlib import Path


def test_companion_config_parsing(tmp_path):
    """[companion.*] sections in hull.toml can be parsed correctly."""
    hull_toml = tmp_path / "hull.toml"
    hull_toml.write_text(
        """
[agent]
name = "test"

[hull]
skills = ["human"]

[companion.human]
command = "python server.py --data-dir data"
cwd = "skills/human"
port = 8421
""",
        encoding="utf-8",
    )

    with open(hull_toml, "rb") as f:
        config = tomllib.load(f)

    # TOML parses [companion.human] as a nested dict: config["companion"]["human"]
    parsed = config.get("companion", {})

    assert "human" in parsed
    assert parsed["human"]["command"] == "python server.py --data-dir data"
    assert parsed["human"]["cwd"] == "skills/human"
    assert parsed["human"]["port"] == 8421


def test_companion_config_empty_when_absent(tmp_path):
    """Returns empty dict when hull.toml has no [companion.*] section."""
    hull_toml = tmp_path / "hull.toml"
    hull_toml.write_text(
        "[agent]\nname = 'test'\n[hull]\nskills = []\n",
        encoding="utf-8",
    )

    with open(hull_toml, "rb") as f:
        config = tomllib.load(f)

    # TOML parses [companion.*] as a nested dict; returns empty dict when absent
    companions = config.get("companion", {})
    assert companions == {}
