# Changelog

All notable changes to this project will be documented in this file.

## [0.0.2] - 2026-04-16

### Added

- **Global CLI usage** — `vessal init` now auto-detects `uv` and runs `uv sync` to create a `.venv` and install dependencies. Falls back to `python -m venv` + `pip install vessal` when `uv` is not available. Added `--no-venv` flag to skip environment setup entirely.
- **SkillHub integration** — `vessal skill install`, `uninstall`, `update`, `search`, `list`, `publish` commands. Skills can be installed from the SkillHub registry by short name, or from any Git URL.
- **Three-directory skill layout** — `skills/bundled/` (preinstalled), `skills/hub/` (SkillHub downloads), `skills/local/` (user-developed). `hull.toml` now declares `skill_paths` covering all three.
- **SKILL.md v1 frontmatter** — New fields: `version`, `author`, `license`, `requires.skills`, `requires.python`. Backward-compatible with v0 format.
- **Skill dependency checking** — Hull validates `requires.skills` at load time and raises a clear error if a dependency is missing.
- **Runtime SkillHub access** — Agent can search and install Skills at runtime via `skills.search_hub()` and `skills.download_skill()`.

## [0.0.1] - 2026-04-14

### Added

- Initial release of Vessal — ARK (Agent Runtime Kit) with Cell, Hull, Shell layers.
- SORA loop (State, Observation, Reasoning, Action) with Ping-Pong protocol.
- Built-in Skills: `tasks`, `pin`, `chat`, `heartbeat`, `memory`, `pip`, `search`, `audio`, `vision`, `ui`, `skill_creator`.
- `vessal init`, `start`, `stop`, `status`, `send`, `read`, `once` CLI commands.
- Docker container support: `vessal build`, `vessal run`.
- Gates: `action_gate.py`, `state_gate.py` safety hooks.
