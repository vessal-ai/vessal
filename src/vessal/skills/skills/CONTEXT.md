# skills — CONTEXT

This Skill provides a human-facing UI for skill management. It exposes no agent-callable tools. The UI lives in `ui/` and is loaded by the Launcher via the `/skills/ui` discovery endpoint. Data is fetched from Hull's `/skills/list` endpoint (per-skill name, summary, has_ui flag).
