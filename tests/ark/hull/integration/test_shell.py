# test_shell.py — Shell CLI tests
#
# Strategy: mock Hull (avoid real API calls and filesystem dependencies),
# verify CLI argument parsing, branch logic, and file generation.
#
# _cmd_run internally does `from vessal import Hull`; patch target is vessal.Hull.

import fcntl
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vessal.ark.shell.cli.__main__ import main
from vessal.ark.shell.cli.process_utils import _is_project_running, _read_lock_port, _read_lock_pid, _is_port_in_use


# ============================================================
# vessal init tests
# ============================================================


class TestInit:
    """vessal init command: scaffold generation."""

    def test_init_creates_project_directory(self, tmp_path, monkeypatch):
        """vessal init name creates a project directory under the current directory."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        assert (tmp_path / "my-agent").is_dir()

    def test_init_creates_hull_toml(self, tmp_path, monkeypatch):
        """Generated hull.toml contains the project name."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        content = (tmp_path / "my-agent" / "hull.toml").read_text()
        assert 'name = "my-agent"' in content

    def test_init_creates_env_example_not_env(self, tmp_path, monkeypatch):
        """Generates .env.example (with three OpenAI variables) instead of .env."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        assert (tmp_path / "my-agent" / ".env.example").exists()
        assert not (tmp_path / "my-agent" / ".env").exists()
        content = (tmp_path / "my-agent" / ".env.example").read_text()
        assert "OPENAI_API_KEY" in content
        assert "OPENAI_BASE_URL" in content
        assert "OPENAI_MODEL" in content

    def test_init_creates_gitignore(self, tmp_path, monkeypatch):
        """Generates .gitignore that excludes .env and logs/."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        content = (tmp_path / "my-agent" / ".gitignore").read_text()
        assert ".env" in content
        assert "logs/" in content

    def test_init_creates_skills_example(self, tmp_path, monkeypatch):
        """Generates skills/local/example/ Skill package (with __init__.py and requirements.txt)."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        example_dir = tmp_path / "my-agent" / "skills" / "local" / "example"
        assert example_dir.is_dir()
        assert (example_dir / "__init__.py").exists()
        assert (example_dir / "requirements.txt").exists()

    def test_init_example_skill_is_valid_package(self, tmp_path, monkeypatch):
        """Example Skill package has module docstring and __all__, discoverable by search_skills."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        init_file = tmp_path / "my-agent" / "skills" / "local" / "example" / "__init__.py"
        content = init_file.read_text(encoding="utf-8")
        assert '"""' in content          # has module docstring
        assert "__all__" in content       # has public API declaration
        assert "def " in content          # has function definitions
        assert "__guide__" not in content # does not contain __guide__
        assert "from pathlib import Path" not in content  # does not import Path

    def test_init_hull_toml_skills_uses_name_list(self, tmp_path, monkeypatch):
        """Generated hull.toml skills field uses a name list (commented example), no glob."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        content = (tmp_path / "my-agent" / "hull.toml").read_text()
        # New format: does not contain glob patterns (*.py)
        assert "*.py" not in content
        # skill_paths should exist
        assert "skill_paths" in content

    def test_init_fails_if_directory_exists(self, tmp_path, monkeypatch):
        """Exits with non-zero status when the directory already exists."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "my-agent").mkdir()
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_init_hull_toml_has_all_sections(self, tmp_path, monkeypatch):
        """Generated hull.toml contains [agent], [cell], [hull], and [gates] sections."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "test-proj"]), \
             patch("subprocess.run"):
            main()

        content = (tmp_path / "test-proj" / "hull.toml").read_text()
        assert "[agent]" in content
        assert "[cell]" in content
        assert "[hull]" in content
        assert "[gates]" in content

    def test_init_creates_pyproject_toml(self, tmp_path, monkeypatch):
        """Generates pyproject.toml containing the project name and requires-python."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        content = (tmp_path / "my-agent" / "pyproject.toml").read_text()
        assert 'name = "my-agent"' in content
        assert "requires-python" in content
        assert '"vessal"' in content

    def test_init_creates_venv(self, tmp_path, monkeypatch):
        """vessal init calls python -m venv when uv is not available."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("shutil.which", return_value=None), \
             patch("subprocess.run") as mock_run:
            main()

        all_args = [call[0][0] for call in mock_run.call_args_list]
        assert any("-m" in a and "venv" in a for a in all_args)

    def test_init_gitignore_includes_venv(self, tmp_path, monkeypatch):
        """Generated .gitignore contains .venv/ entry."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        content = (tmp_path / "my-agent" / ".gitignore").read_text()
        assert ".venv/" in content

    def test_init_creates_soul_md(self, tmp_path, monkeypatch):
        """Generates SOUL.md Agent identity definition file."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        soul_path = tmp_path / "my-agent" / "SOUL.md"
        assert soul_path.exists()

    def test_init_soul_md_contains_project_name(self, tmp_path, monkeypatch):
        """SOUL.md contains the project name."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        content = (tmp_path / "my-agent" / "SOUL.md").read_text(encoding="utf-8")
        assert "my-agent" in content

    def test_init_hull_toml_has_required_sections(self, tmp_path, monkeypatch):
        """hull.toml contains currently required sections: [hull], [cell], [core], [gates]."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        content = (tmp_path / "my-agent" / "hull.toml").read_text(encoding="utf-8")
        assert "[hull]" in content
        assert "[cell]" in content
        assert "[core]" in content
        assert "[gates]" in content
        assert "[compression]" not in content

    def test_init_hull_toml_has_context_budget_comment(self, tmp_path, monkeypatch):
        """hull.toml contains context_budget comment."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        content = (tmp_path / "my-agent" / "hull.toml").read_text(encoding="utf-8")
        assert "context_budget" in content

    def test_init_hull_toml_has_core_section(self, tmp_path, monkeypatch):
        """Generated hull.toml contains [core] section."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        content = (tmp_path / "my-agent" / "hull.toml").read_text(encoding="utf-8")
        assert "[core]" in content
        assert "timeout" in content

    def test_init_hull_toml_has_core_timeout(self, tmp_path, monkeypatch):
        """hull.toml [core] section contains timeout configuration."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        content = (tmp_path / "my-agent" / "hull.toml").read_text(encoding="utf-8")
        assert "timeout = 60" in content

    def test_init_hull_toml_has_core_max_retries(self, tmp_path, monkeypatch):
        """hull.toml [core] section contains max_retries configuration."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        content = (tmp_path / "my-agent" / "hull.toml").read_text(encoding="utf-8")
        assert "max_retries = 3" in content

    def test_init_example_skill_md_has_frontmatter(self, tmp_path, monkeypatch):
        """Generated example SKILL.md contains YAML frontmatter."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        skill_md = tmp_path / "my-agent" / "skills" / "local" / "example" / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert "---" in content  # frontmatter delimiter
        assert "name: example" in content
        assert "version:" in content
        assert "description:" in content
        assert "tags:" in content
        assert "category:" in content

    def test_init_copies_builtin_skills(self, tmp_path, monkeypatch):
        """vessal init copies built-in Skills to skills/bundled/ (human is deprecated, not copied)."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        bundled_dir = tmp_path / "my-agent" / "skills" / "bundled"
        assert (bundled_dir / "chat" / "skill.py").exists()
        assert (bundled_dir / "tasks" / "skill.py").exists()
        assert (bundled_dir / "pin" / "skill.py").exists()
        assert not (bundled_dir / "human").exists()

    def test_init_hull_toml_has_skill_paths(self, tmp_path, monkeypatch):
        """Generated hull.toml contains skill_paths configuration."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("subprocess.run"):
            main()

        content = (tmp_path / "my-agent" / "hull.toml").read_text(encoding="utf-8")
        assert "skill_paths" in content
        assert "skills" in content

    def test_init_no_venv_skips_subprocess(self, tmp_path, monkeypatch):
        """--no-venv flag skips all subprocess calls."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent", "--no-venv"]), \
             patch("subprocess.run") as mock_run:
            main()

        mock_run.assert_not_called()

    def test_init_uses_uv_sync_when_uv_available(self, tmp_path, monkeypatch):
        """When uv is on PATH, init calls uv sync instead of python -m venv."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("shutil.which", return_value="/usr/bin/uv"), \
             patch("subprocess.run") as mock_run:
            main()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args == ["uv", "sync"]

    def test_init_uses_pip_when_uv_not_available(self, tmp_path, monkeypatch):
        """When uv is not on PATH, init falls back to python -m venv + pip install."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "init", "my-agent"]), \
             patch("shutil.which", return_value=None), \
             patch("subprocess.run") as mock_run:
            main()

        assert mock_run.call_count == 2
        all_args = [call[0][0] for call in mock_run.call_args_list]
        assert any("venv" in a for a in all_args)
        assert any("pip" in a for a in all_args)


# ============================================================
# No subcommand tests
# ============================================================


class TestNoCommand:
    """Behavior when no subcommand is provided."""

    def test_no_command_exits_with_error(self):
        """vessal (no subcommand) exits with non-zero status."""
        with patch("sys.argv", ["vessal"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1


# ============================================================
# vessal skill tests
# ============================================================


class TestSkillInit:
    """vessal skill init command: Skill scaffold generation."""

    def test_skill_init_creates_scaffold(self, tmp_path, monkeypatch):
        """vessal skill init <name> generates the correct scaffold files."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "skill", "init", "my_skill"]):
            main()

        assert (tmp_path / "my_skill" / "__init__.py").exists()
        assert (tmp_path / "my_skill" / "SKILL.md").exists()
        assert (tmp_path / "my_skill" / "requirements.txt").exists()
        assert (tmp_path / "my_skill" / "tests" / "__init__.py").exists()
        assert (tmp_path / "my_skill" / "tests" / "test_my_skill.py").exists()

    def test_skill_init_creates_skill_py(self, tmp_path, monkeypatch):
        """Generated scaffold contains skill.py."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "skill", "init", "my_skill"]):
            main()

        assert (tmp_path / "my_skill" / "skill.py").exists()

    def test_skill_init_init_py_imports_skill_class(self, tmp_path, monkeypatch):
        """Generated __init__.py imports Skill class from skill.py and exports __all__."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "skill", "init", "my_skill"]):
            main()

        content = (tmp_path / "my_skill" / "__init__.py").read_text(encoding="utf-8")
        assert "from .skill import" in content
        assert "as Skill" in content
        assert '__all__ = ["Skill"]' in content
        assert "__guide__" not in content
        assert "from pathlib import Path" not in content

    def test_skill_init_skill_py_has_skillbase(self, tmp_path, monkeypatch):
        """Generated skill.py inherits SkillBase and defines name/description class attributes."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "skill", "init", "my_skill"]):
            main()

        content = (tmp_path / "my_skill" / "skill.py").read_text(encoding="utf-8")
        assert "SkillBase" in content
        assert 'name = "my_skill"' in content
        assert "description =" in content

    def test_skill_init_camelcase_classname(self, tmp_path, monkeypatch):
        """Generated class name is the CamelCase form of the skill_name."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "skill", "init", "my_cool_skill"]):
            main()

        content = (tmp_path / "my_cool_skill" / "skill.py").read_text(encoding="utf-8")
        assert "class MyCoolSkill(SkillBase)" in content
        init_content = (tmp_path / "my_cool_skill" / "__init__.py").read_text(encoding="utf-8")
        assert "from .skill import MyCoolSkill as Skill" in init_content

    def test_skill_init_skill_md_has_frontmatter(self, tmp_path, monkeypatch):
        """Generated SKILL.md contains v1 YAML frontmatter with required fields."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "skill", "init", "my_skill"]):
            main()

        content = (tmp_path / "my_skill" / "SKILL.md").read_text(encoding="utf-8")
        assert "---" in content  # frontmatter delimiter
        assert "name: my_skill" in content
        assert "description:" in content
        assert 'version: "0.1.0"' in content
        assert 'author: ""' in content
        assert 'license: "Apache-2.0"' in content
        assert "requires:" in content
        assert "skills: []" in content
        assert "tags:" not in content
        assert "category:" not in content

    def test_skill_init_skill_md_has_name(self, tmp_path, monkeypatch):
        """Generated SKILL.md contains the Skill name."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "skill", "init", "my_skill"]):
            main()

        content = (tmp_path / "my_skill" / "SKILL.md").read_text(encoding="utf-8")
        assert "my_skill" in content

    def test_skill_init_no_readme(self, tmp_path, monkeypatch):
        """vessal skill init does not generate README.md."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "skill", "init", "my_skill"]):
            main()

        assert not (tmp_path / "my_skill" / "README.md").exists()

    def test_skill_init_skill_md_is_minimal(self, tmp_path, monkeypatch):
        """Generated SKILL.md body is a short placeholder without a writing guide."""
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["vessal", "skill", "init", "my_skill"]):
            main()

        md = (tmp_path / "my_skill" / "SKILL.md").read_text(encoding="utf-8")
        assert "---" in md
        assert "name: my_skill" in md
        assert "writing principles" not in md
        assert "recommended body structure" not in md

    def test_skill_no_subcommand_exits_with_error(self):
        """vessal skill (no subcommand) exits with code 1."""
        with patch("sys.argv", ["vessal", "skill"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1


class TestSkillCheck:
    """vessal skill check command: static compliance checking."""

    def _make_valid_skill(self, tmp_path: Path, name: str = "my_skill") -> Path:
        """Create a compliant Skill directory (passes all checks)."""
        skill_dir = tmp_path / name
        skill_dir.mkdir()
        class_name = "".join(part.capitalize() for part in name.split("_"))
        (skill_dir / "__init__.py").write_text(
            f'"""{name}"""\nfrom .skill import {class_name} as Skill\n__all__ = ["Skill"]\n',
            encoding="utf-8",
        )
        (skill_dir / "skill.py").write_text(
            f'from vessal.ark.shell.hull.skill import SkillBase\n\n'
            f'class {class_name}(SkillBase):\n'
            f'    name = "{name}"\n'
            f'    description = "test Skill"\n'
            f'    def __init__(self): super().__init__()\n',
            encoding="utf-8",
        )
        (skill_dir / "SKILL.md").write_text(
            f'---\nname: {name}\nversion: "0.1.0"\ndescription: "test Skill"\nauthor: "test"\nlicense: "Apache-2.0"\nrequires:\n  skills: []\n---\n# {name}\n',
            encoding="utf-8",
        )
        return skill_dir

    def test_check_valid_skill_exits_zero(self, tmp_path):
        """Compliant Skill exits with code 0."""
        skill_dir = self._make_valid_skill(tmp_path)
        with patch("sys.argv", ["vessal", "skill", "check", str(skill_dir)]):
            main()  # should not raise SystemExit → exit code 0

    def test_check_missing_directory_exits_one(self, tmp_path):
        """Exits with code 1 when directory does not exist."""
        with patch("sys.argv", ["vessal", "skill", "check", str(tmp_path / "no_such")]):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 1

    def test_check_missing_init_py_exits_one(self, tmp_path):
        """Exits with code 1 when __init__.py does not exist."""
        skill_dir = tmp_path / "bad_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            '---\nname: bad_skill\nversion: "1.0"\ndescription: "x"\n---\n',
            encoding="utf-8",
        )
        with patch("sys.argv", ["vessal", "skill", "check", str(skill_dir)]):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 1

    def test_check_missing_skill_md_warns_not_fails(self, tmp_path, capsys):
        """Outputs WARN (not error) when SKILL.md does not exist."""
        skill_dir = self._make_valid_skill(tmp_path, "no_md")
        (skill_dir / "SKILL.md").unlink()
        with patch("sys.argv", ["vessal", "skill", "check", str(skill_dir)]):
            main()  # should not raise SystemExit
        out = capsys.readouterr().out
        assert "[WARN]" in out
        assert "SKILL.md" in out

    def test_check_missing_frontmatter_field_warns(self, tmp_path, capsys):
        """Outputs WARN when SKILL.md is missing description field."""
        skill_dir = self._make_valid_skill(tmp_path, "no_description")
        # Overwrite SKILL.md with only name, no description
        (skill_dir / "SKILL.md").write_text(
            '---\nname: no_description\n---\n# no_description\n',
            encoding="utf-8",
        )
        with patch("sys.argv", ["vessal", "skill", "check", str(skill_dir)]):
            main()
        out = capsys.readouterr().out
        assert "[WARN]" in out
        assert "description" in out

    def test_check_import_error_exits_one(self, tmp_path):
        """Exits with code 1 when __init__.py has a syntax error causing import failure."""
        skill_dir = tmp_path / "broken"
        skill_dir.mkdir()
        (skill_dir / "__init__.py").write_text(
            'this is not valid python!!!\n', encoding="utf-8"
        )
        with patch("sys.argv", ["vessal", "skill", "check", str(skill_dir)]):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 1

    def test_check_missing_skill_py_exits_one(self, tmp_path):
        """Exits with code 1 when skill.py does not exist."""
        skill_dir = self._make_valid_skill(tmp_path, "no_skill_py")
        (skill_dir / "skill.py").unlink()
        with patch("sys.argv", ["vessal", "skill", "check", str(skill_dir)]):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 1

    def test_check_not_skillbase_subclass_exits_one(self, tmp_path):
        """Exits with code 1 when Skill does not inherit SkillBase."""
        skill_dir = tmp_path / "bad_skill"
        skill_dir.mkdir()
        (skill_dir / "__init__.py").write_text(
            'from .skill import BadSkill as Skill\n__all__ = ["Skill"]\n',
            encoding="utf-8",
        )
        (skill_dir / "skill.py").write_text(
            'class BadSkill:\n    name = "bad_skill"\n    description = "x"\n',
            encoding="utf-8",
        )
        (skill_dir / "SKILL.md").write_text(
            '---\nname: bad_skill\ndescription: "x"\n---\n',
            encoding="utf-8",
        )
        with patch("sys.argv", ["vessal", "skill", "check", str(skill_dir)]):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 1

    def test_check_skillbase_subclass_ok(self, tmp_path, capsys):
        """Outputs OK with class name when Skill correctly inherits SkillBase."""
        skill_dir = self._make_valid_skill(tmp_path, "good_skill")
        with patch("sys.argv", ["vessal", "skill", "check", str(skill_dir)]):
            main()
        out = capsys.readouterr().out
        assert "[FAIL]" not in out
        assert "SkillBase" in out

    def test_check_output_includes_skill_name(self, tmp_path, capsys):
        """Check output contains the Skill name."""
        skill_dir = self._make_valid_skill(tmp_path, "named_skill")
        with patch("sys.argv", ["vessal", "skill", "check", str(skill_dir)]):
            main()
        out = capsys.readouterr().out
        assert "named_skill" in out

    def test_check_test_flag_runs_pytest(self, tmp_path):
        """--test flag triggers a pytest call on the tests/ directory."""
        skill_dir = self._make_valid_skill(tmp_path)
        tests_dir = skill_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_placeholder.py").write_text(
            'def test_ok(): pass\n', encoding="utf-8"
        )
        with patch("sys.argv", ["vessal", "skill", "check", str(skill_dir), "--test"]), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            main()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "pytest" in call_args
        assert str(tests_dir) in call_args

    def test_check_test_flag_no_tests_dir_warns(self, tmp_path, capsys):
        """Outputs WARN (no error) when --test is given but tests/ does not exist."""
        skill_dir = self._make_valid_skill(tmp_path)
        with patch("sys.argv", ["vessal", "skill", "check", str(skill_dir), "--test"]):
            main()
        out = capsys.readouterr().out
        assert "[WARN]" in out
        assert "tests/" in out

    def test_check_result_line_shows_pass(self, tmp_path, capsys):
        """Result line shows pass for a compliant Skill."""
        skill_dir = self._make_valid_skill(tmp_path)
        with patch("sys.argv", ["vessal", "skill", "check", str(skill_dir)]):
            main()
        out = capsys.readouterr().out
        assert "Result:" in out
        assert "passed" in out

    def test_check_result_line_shows_error_count(self, tmp_path, capsys):
        """Result line shows error count when there are errors."""
        skill_dir = tmp_path / "bad"
        skill_dir.mkdir()
        # No __init__.py → FAIL
        with patch("sys.argv", ["vessal", "skill", "check", str(skill_dir)]):
            with pytest.raises(SystemExit):
                main()
        out = capsys.readouterr().out
        assert "error" in out


def _write_canonical_jsonl(path: Path, frame_dicts: list[dict]) -> None:
    """Write a canonical JSONL log file (for log command tests)."""
    with open(path, "w", encoding="utf-8") as f:
        for d in frame_dicts:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


def _make_frame_dict(
    number: int = 1,
    error: str | None = None,
    diff: str = "",
) -> dict:
    """Construct a canonical format frame dict (for writing test JSONL)."""
    from vessal.ark.shell.hull.cell.protocol import (
        Action,
        FrameRecord,
        Observation,
        Pong,
    )
    frame = FrameRecord(
        number=number,
        pong=Pong(think="", action=Action(operation="pass", expect="")),
        observation=Observation(stdout="", diff=diff, error=error, verdict=None),
    )
    return frame.to_dict()


class TestProcessLock:
    """Process lock (flock) helper functions."""

    def test_is_project_running_false_when_no_lock_file(self, tmp_path):
        lock_path = tmp_path / "data" / "vessal.lock"
        assert not _is_project_running(lock_path)

    def test_is_project_running_false_when_unlocked(self, tmp_path):
        lock_path = tmp_path / "data" / "vessal.lock"
        lock_path.parent.mkdir(parents=True)
        lock_path.write_text("8420\n99999\n")
        assert not _is_project_running(lock_path)

    def test_is_project_running_true_when_locked(self, tmp_path):
        lock_path = tmp_path / "data" / "vessal.lock"
        lock_path.parent.mkdir(parents=True)
        fd = open(lock_path, "w")
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.write("8420\n12345\n")
        fd.flush()
        try:
            assert _is_project_running(lock_path)
        finally:
            fd.close()

    def test_read_lock_port(self, tmp_path):
        lock_path = tmp_path / "vessal.lock"
        lock_path.write_text("8420\n12345\n")
        assert _read_lock_port(lock_path) == 8420

    def test_read_lock_pid(self, tmp_path):
        lock_path = tmp_path / "vessal.lock"
        lock_path.write_text("8420\n12345\n")
        assert _read_lock_pid(lock_path) == 12345

    def test_read_lock_port_missing_file(self, tmp_path):
        lock_path = tmp_path / "vessal.lock"
        assert _read_lock_port(lock_path) is None

    def test_is_port_in_use_free_port(self):
        import socket
        with socket.socket() as s:
            s.bind(("localhost", 0))
            free_port = s.getsockname()[1]
        # port is released; verify probe reports free
        assert not _is_port_in_use(free_port)


class TestStartForegroundLock:
    """Foreground startup flock mutex, using vessal.lock for identity."""

    def test_foreground_creates_lock_file_only(self, tmp_path):
        """_start_foreground creates data/vessal.lock, not a PID file."""
        import argparse
        from unittest.mock import patch
        from vessal.ark.shell.cli.process_cmds import _start_foreground

        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        toml = (
            '[agent]\nname = "test"\n'
            '[cell]\nmax_frames=1\n'
            '[hull]\nskills=[]\nskill_paths=[]\n'
            '[core]\ntimeout=60\nmax_retries=3\n'
            '[compression]\nenabled=false\n'
            '[gates]\n'
        )
        (project_dir / "hull.toml").write_text(toml)
        (project_dir / "data").mkdir()

        lock_file_created = {}

        def capture_serve_forever(*args, **kwargs):
            lock_path = project_dir / "data" / "vessal.lock"
            if lock_path.exists():
                lock_file_created["exists"] = True
            raise KeyboardInterrupt

        with patch("vessal.ark.shell.server.ShellServer") as MockShell:
            mock_shell = MockShell.return_value
            mock_shell.start.return_value = None
            mock_shell.serve_forever.side_effect = capture_serve_forever

            args = argparse.Namespace(dir=str(project_dir), port=9997, daemon=False)
            try:
                _start_foreground(args)
            except (SystemExit, KeyboardInterrupt):
                pass

        assert lock_file_created.get("exists"), "Lock file should be created in foreground mode"

    def test_foreground_creates_lock_file(self, tmp_path):
        """_start_foreground creates data/vessal.lock and writes the port number."""
        import argparse
        from unittest.mock import patch
        from vessal.ark.shell.cli.process_cmds import _start_foreground

        project_dir = tmp_path / "proj2"
        project_dir.mkdir()
        toml = (
            '[agent]\nname = "test"\n'
            '[cell]\nmax_frames=1\n'
            '[hull]\nskills=[]\nskill_paths=[]\n'
            '[core]\ntimeout=60\nmax_retries=3\n'
            '[compression]\nenabled=false\n'
            '[gates]\n'
        )
        (project_dir / "hull.toml").write_text(toml)

        lock_contents = {}

        def capture_serve_forever(*args, **kwargs):
            lock_path = project_dir / "data" / "vessal.lock"
            if lock_path.exists():
                lock_contents["data"] = lock_path.read_text()
            raise KeyboardInterrupt

        with patch("vessal.ark.shell.server.ShellServer") as MockShell:
            mock_shell = MockShell.return_value
            mock_shell.start.return_value = None
            mock_shell.serve_forever.side_effect = capture_serve_forever

            args = argparse.Namespace(dir=str(project_dir), port=9998, daemon=False)
            try:
                _start_foreground(args)
            except (SystemExit, KeyboardInterrupt):
                pass

        # Lock file content should contain port number
        assert "9998" in lock_contents.get("data", "")

    def test_foreground_shell_start_error_releases_lock(self, tmp_path, monkeypatch):
        """When shell.start() raises RuntimeError, the lock file is released and exits with code 1."""
        import argparse
        import threading
        from vessal.ark.shell.cli.process_cmds import _start_foreground

        project_dir = tmp_path / "proj3"
        project_dir.mkdir()
        toml = (
            '[agent]\nname = "test"\n'
            '[cell]\nmax_frames=1\n'
            '[hull]\nskills=[]\nskill_paths=[]\n'
            '[core]\ntimeout=60\nmax_retries=3\n'
            '[compression]\nenabled=false\n'
            '[gates]\n'
        )
        (project_dir / "hull.toml").write_text(toml)
        (project_dir / "data").mkdir()

        class FakeShellServer:
            def __init__(self, project_dir, host="0.0.0.0", port=8420):
                self._stop_event = threading.Event()
                self.port = port

            def start(self):
                raise RuntimeError("Hull startup failed")

            def serve_forever(self):
                pass

            def shutdown(self):
                pass

        monkeypatch.setattr("vessal.ark.shell.server.ShellServer", FakeShellServer)

        args = argparse.Namespace(dir=str(project_dir), port=9001, daemon=False)

        with pytest.raises(SystemExit) as exc_info:
            _start_foreground(args)

        assert exc_info.value.code == 1

        # Lock file should be deleted
        lock_path = project_dir / "data" / "vessal.lock"
        assert not lock_path.exists()


class TestStopCommand:
    """vessal stop command."""

    def test_stop_reports_not_running_when_no_lock(self, tmp_path, capsys):
        """Reports Agent is not running when no lock file exists."""
        import argparse
        from vessal.ark.shell.cli.process_cmds import _cmd_stop

        (tmp_path / "data").mkdir()
        args = argparse.Namespace(dir=str(tmp_path), port=8420)
        _cmd_stop(args)
        captured = capsys.readouterr()
        assert "not running" in captured.out

    def test_stop_reports_not_running_when_no_data_dir(self, tmp_path, capsys):
        """Reports Agent is not running when data/ directory does not exist."""
        import argparse
        from vessal.ark.shell.cli.process_cmds import _cmd_stop

        args = argparse.Namespace(dir=str(tmp_path), port=8420)
        _cmd_stop(args)
        captured = capsys.readouterr()
        assert "not running" in captured.out
