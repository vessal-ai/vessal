# Changelog

All notable changes to this project will be documented in this file.

## [0.0.4] - 2026-04-18

### Console Redesign

- Launcher is now a generic UI shell; the only hard-coded view is `frames`.
- Every other UI (chat, skills management) is provided by a Skill and loaded as an iframe tab via `/skills/ui` discovery.
- Data plane contract: every `GET /<domain>` accepts `?after=<cursor>`; frontend state is append-only.
- Retired: `src/vessal/ark/util/logging/viewer.html`, `/logs`, `/logs/raw`.
- Terminology: `● idle` → `● sleep` in the status indicator.
- Fixes (as side effects of the migration): user chat messages no longer disappear on poll; Current Frame no longer blank after tab switch; Logs view no longer a placeholder.

### Governance

- Added Anti-Rot Governance section to CLAUDE.md (R1–R5).
- Added `references/whitepaper/08-console.md` — Console and the User-Facing Data Plane.

## [0.0.3] - 2026-04-18

### Added

- **Vessal Console** — Browser-based agent UI served at `/console/`. Left pane is live chat; collapsible right pane shows the agent's current Frame (think, action, observation). Alpine.js v3.13.10 vendored (no CDN dependency).
- **TUI picker** — Running bare `vessal` inside an agent project opens an interactive menu (Run dev, Build image, Install skill, Open Console, Stop). Outside a project, prompts to create or open a recent one.
- **`vessal create` wizard** — Six-question interactive scaffold (name, provider, API key, template, Docker, deploy). Accepts Enter × 6 to use all defaults.
- **Hot reload** — `watchfiles`-based file watcher auto-applies changes without Hull restart: `SOUL.md` edits take effect on the next frame, Skill edits reload the affected Skill in place, `hull.toml` changes surface as a yellow Console banner.
- **SSE event bus** — `/events` endpoint streams `frame`, `agent_crash`, `gate_reject`, `llm_timeout`, and `restart_required` events to the Console.
- **Skill UI convention** — A Skill may ship a pre-built static frontend under `ui/index.html`; the Console auto-discovers and mounts it as an iframe activity-bar tab.
- **`GET /frames?after=N`** — Incremental frame polling endpoint used by the Console and FramePublisher.

### Changed

- Shell server now binds to `127.0.0.1` by default (was `0.0.0.0`). Port auto-retries up to +20 if the default is occupied.
- `GET /logs` redirects to `/console/` (HTML log viewer removed).
- README logo now uses a versioned local asset (`assets/vessal-logo-text.jpg`) instead of a private GitHub image URL.

### Fixed

- `ThreadingHTTPServer` replaces plain `HTTPServer` so SSE connections no longer block other requests.

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
