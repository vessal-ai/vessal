# Contributing to vessal-skills

## Register a Third-Party Skill

1. Build your skill following the [Vessal Skill guide](https://github.com/vessal-ai/vessal)
2. Push it to a public Git repository
3. Run `vessal skill check <path>` to verify compliance
4. Open a PR adding an entry to `registry.toml`:

```toml
[your_skill_name]
source = "your-username/your-repo"
description = "one-line description"
tags = ["relevant", "tags"]
```

## Contribute an Official Skill

1. Fork this repository
2. Create your skill under `skills/<name>/` following the standard structure:
   - `__init__.py` — exports `Skill`
   - `skill.py` — `SkillBase` subclass
   - `SKILL.md` — v1 frontmatter + usage guide
   - `tests/` — test suite
3. Add a registry entry pointing to `vessal-ai/vessal-skills#skills/<name>`
4. Open a PR

## SKILL.md v1 Format

```yaml
---
name: your_skill
version: "1.0.0"
description: "one-line description"
author: "your-name"
license: "Apache-2.0"
requires:
  skills: []
  python: ">=3.12"
---
```
