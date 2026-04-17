# Skill Authoring Guide

A Skill is a Python module that extends an Agent's capabilities. It is loaded by Hull at startup and made available to Cell as a namespace object.

## Minimal Layout

```
skills/<name>/
├── SKILL.md        # Frontmatter: name, description + usage guide for the LLM
├── skill.py        # Skill class definition
└── server.py       # (optional) HTTP sub-server for inbox/outbox routes
```

## SKILL.md Frontmatter

```yaml
---
name: my-skill
description: One-line description shown to the LLM
---
```

## skill.py

Define a class with the skill name (PascalCase). The class is instantiated once and injected into the Cell namespace as the lower-case name.

```python
class MySkill:
    def do_something(self, arg: str) -> str:
        ...
```

## server.py (optional)

If the Skill needs HTTP routes (inbox/outbox), define a `create_server(api)` function. The `api` argument is a `ScopedHullApi` that automatically prefixes all routes with `/skills/<name>/`.

```python
def create_server(api):
    @api.route("POST", "/inbox")
    def inbox(body):
        ...
```

## Optional Skill UI (`ui/` convention)

A Skill may ship a pre-built static frontend that the Vessal Console mounts
automatically via iframe. To opt in, place static assets under `ui/` with
an `index.html` entry point:

```
skills/<name>/
├── SKILL.md
├── skill.py
└── ui/
    ├── index.html
    ├── app.js
    └── style.css
```

Any framework is supported provided the output is plain static files
(Vue build, React build, Svelte build, or hand-written HTML all work).
Console discovers UIs via `GET /skills/ui` and adds one activity-bar icon
per loaded skill. Skill authors MUST keep `index.html` as the entry
filename; advanced skills may expose `ui_manifest()` on their skill class
for multi-tab or dynamic-route layouts (to be specified in a later doc).
