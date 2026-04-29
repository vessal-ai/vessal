# Compaction Skill

Preset Skill of the compaction Cell. Hull instantiates one `CompactionSkill` per project, configured with the main Cell's `frame_log.sqlite` path. Not for direct use in user agents.

System prompt is shipped as `system.md` and loaded as `COMPACTION_SYSTEM_PROMPT`. Built-in and immutable — no project-level override.

See `docs/architecture/cell/06-compaction.md` for the full design.
