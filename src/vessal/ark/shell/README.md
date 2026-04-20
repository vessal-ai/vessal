# Shell

Agent Carrier Layer. Shell is "a place to put an Agent" — it covers every artifact that lets the outside world reach a running Hull, across every carrier shape that Vessal supports (foreground CLI process, `vessal start --daemon` process, Docker container).

## Three Subdomains

Shell has three orthogonal responsibilities. Keep them in separate subdirectories so new carrier shapes (e.g. a future systemd unit adapter) land in an obvious place.

| Subdomain | Purpose | Files |
|-----------|---------|-------|
| Entry | How a user interacts with Vessal | `cli/` (process/skill/init subcommands) + `tui/` |
| Runtime | Which process carries the Hull | `runtime/subprocess_mode.py` (Popen'd by `ShellServer`) + `runtime/container_mode.py` (Docker `ENTRYPOINT`) + `runtime/hull_adapter.py` (shared HTTP bridge) |
| Supervisor | The HTTP proxy + crash-restart watchdog that wraps subprocess mode | `server.py` |

Plus carrier-agnostic plumbing: `http_server.py` (stdlib `HTTPServer` base with quiet disconnect policy), `protocol.py` (`handle()` type definitions), `events.py`.

## Responsible for

- Hosting the Hull subprocess (subprocess mode) or Hull in-process (container mode)
- Parsing HTTP and forwarding to `Hull.handle()` via `HullHttpHandlerBase`
- Crash detection + auto-restart (supervisor, subprocess mode only)
- CLI entry (`vessal` console script)

## Not responsible for

- Business logic (Hull)
- Frame execution (Cell)
- Skill management (Hull; `shell/hull/hub/` is Hull's installation infrastructure)
- Heartbeat scheduling (handled by the `heartbeat` skill)

## Design

Subprocess mode = foreground + `--daemon` CLI. The main process runs `ShellServer` (HTTP proxy + `_ProxyHandler` + watchdog thread); it `subprocess.Popen`s `python -m vessal.ark.shell.runtime.subprocess_mode` which creates `Hull`, binds 127.0.0.1 on an internal port, and forwards each request through `SubprocessHullHandler` (a subclass of `HullHttpHandlerBase`). Crash isolation: native-library segfaults kill only the Hull child; the supervisor restarts it and returns HTTP 503 in the interim.

Container mode = Docker `ENTRYPOINT`. There is no `ShellServer` — the container itself *is* the supervisor (restarts are Docker's job). `python -m vessal.ark.shell.runtime.container_mode` directly constructs `Hull`, binds 0.0.0.0, and runs `ContainerHullHandler` (also a subclass of `HullHttpHandlerBase`) on the user-visible port. A `SIGTERM` handler shuts Hull down gracefully; `/healthz` is a handler-level bypass for Docker's HEALTHCHECK. A first-boot step (`sync_image_to_volume`) seeds the volume from the baked `/opt/agent-image/`.

The two carriers share exactly one base class (`HullHttpHandlerBase`) that owns `do_GET`, `do_POST`, `_read_json`, and `_respond`. Differences between carriers are declared by subclass overrides (HOST, healthz path, logging, lifecycle hooks) — nothing is duplicated.

Shell depends on Hull; Hull does not know Shell exists. `TYPE_CHECKING` blocks avoid runtime circular imports.

## Public Interface

See `cli/`, `runtime/`, `server.py` for detail.

## Status

### TODO

None.

### Known Issues

None.
