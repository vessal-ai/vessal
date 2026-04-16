# V5 Design Discussion Q&A

Conclusions and reasoning from design discussions. Supplements details not covered in the main whitepaper text.

---

## Architecture

### Q: Is Shell the only channel?

Shell controls only **inbound traffic** (outside world → Agent). Outbound traffic (Agent → outside world) originates directly from the Kernel executor — exec'd code has full system permissions (HTTP requests, system commands, file operations). Outbound security is the responsibility of Gate. Shell is an inbound gateway, not an outbound firewall.

### Q: Can an Agent start a background service inside the Kernel?

Yes. exec'd code can spin up a persistent service with `threading.Thread(...).start()`. That thread persists across frames. The distinction: a Skill's server is **managed** by Hull (Hull controls its lifecycle), whereas a service started via exec is **unmanaged** (the Agent manages it itself).

### Q: What is the return format for Hull's interface to Shell?

`handle(method, path, body) → (int, dict)`. The int is an HTTP status code; the dict is a JSON-serializable response body. Shell serializes the dict to JSON and returns it.

### Q: Nested directories vs flat layout?

`ark/shell/hull/cell/` nesting reflects the containment relationship. Import paths are mitigated through re-exports. Reversible decision.

---

## Cell

### Q: Why the Ping-Pong naming?

**Ping** = the system's outgoing state projection (system_prompt + state). **Pong** = the LLM's response (think + action). Follows ICMP convention. The whitepaper uses the intended naming throughout. Implementation alignment is a code-level TODO, not a design question.

### Q: Does Cell need `run_until_idle()`?

No. Keep the single-frame `step()` design. The frame loop is driven by Hull.

### Q: Renaming `_idle`?

Rename to `_sleeping`. Provide a `sleep()` function — the Agent calls it to enter sleep mode, and Hull detects `_sleeping` to stop the frame loop.

### Q: What does a frame record contain?

Trimmed to: frame number, action (operation + expect), observation (stdout + diff + error + verdict). Removed: think (goes into audit trace), wake_reason (set once on wake), frame_type (frame-level metadata).

### Q: How are namespace accessors distinguished?

Tool functions (executing inside Cell) operate directly on the dict. External callers (Hull) use get/set/keys methods. The distinction is purely by code convention — a tool in the exec environment naturally receives a dict reference, while an external caller only receives a Cell object.

### Q: Does the Kernel executor have full permissions?

Yes. Code executed via exec() can do anything — send HTTP requests, read and write files, execute commands. This is intentional — an Agent must be able to interact with the outside world. Security is the responsibility of the Gate system.

---

## Gate

### Q: How is Gate configured?

Gate rules are Python files placed at a conventional location within the agent project directory (e.g., `gates/`). Hull reads them and passes them in via `cell.set_gate("action", fn)`.

Function signature: `check(code: str) -> tuple[bool, str]`. Returns `(True, "")` to pass, `(False, "reason")` to block.

When no configuration files are present, everything passes by default. Developers write whatever logic they need — blocklists, allowlists, a secondary LLM for review, a permissions database query — all are valid.

### Q: What do the two Gates each do?

`state_gate`: checks state validity before a Ping is sent (verifies that namespace contents are well-formed). `action_gate`: checks code safety before a Pong is executed.

---

## Skill

### Q: Why is the server separated from the Skill class?

Cell is frame-driven (execute → sleep → execute); a server runs continuously. Sharing a class would create concurrent access to `self` attributes. After separation, the two sides communicate through thread-safe channels.

### Q: What are the two parts of a Skill?

**Skill class** (Cell side): SOP metadata (name + summary + guide path) + Tool (declared methods) + Signal (_signal).

**Server** (Hull side): standalone code in any language; Hull manages start/stop.

### Q: How do the two parts of a Skill communicate?

Three paths: (1) shared mutable data structures (passed to both sides at construction time); (2) HTTP (tool calls a server route, or the reverse); (3) namespace keys (passed across frames).

### Q: What is hull_api's interface?

`register_route` / `unregister_route` / `wake` (injects an event into the event queue). Routes are automatically prefixed with `/skills/{name}`. **`create_timer` is strictly prohibited** — servers manage their own timer threads.

### Q: What is the word limit for a guide?

~500 words. 300–800 is normal. The guide is not injected into the system prompt — the Agent queries it on demand via the meta-skill's `query_guide(name)`.

### Q: Can the system prompt be modified?

**No.** The system prompt = protocol (system.md) + identity (SOUL.md), and it is fixed after startup. Loading a Skill does not modify the system prompt.

### Q: How does the Kernel discover a Skill's tools and signals?

**Tools**: the `describe/` system scans all user-visible callables in the namespace and auto-generates descriptions embedded in the Ping. A Skill's `tools` attribute filters which methods are exposed to the LLM.

**Signals**: scans all values in the namespace; calls `_signal` on anything that has that attribute. No registry.

### Q: What happens when a Skill fails to load?

If phase one (Cell injection) succeeds but phase two (server start) fails, the unload sequence runs immediately to roll back phase one, and the error is returned to the Agent via the meta-skill.

### Q: How is a server crash handled?

Hull detects when the server process or thread exits. It restarts once by default. On a second failure, it unloads the Skill and notifies the Agent via a signal. Caveat: a server crash may leave data in a corrupted state — that is the server developer's responsibility.

### Q: What is the namespace cleanup protocol?

A Skill should declare the namespace keys it uses (as a class attribute). Hull clears those keys on unload. Undeclared keys are not cleaned up.

### Q: Do detailed docs need to be standardized?

No. Only the guide is a framework standard. Other documentation is defined by the Skill itself.

### Q: Must a server declare its routes and timers?

**No declaration required.** A server is arbitrary code, managed through `start(hull_api)` / `stop()`. There is no declarative configuration.

### Q: How are Skill files organized?

Multiple files: `skill.py` + `server.py` + `sop.md` + `__init__.py`. Distribution packaging = directory compression.

### Q: Any changes to compressed frames in V5?

None. The principle behind compressed frames (semantic compression can only be done by an LLM) is unchanged. Hull switches the prompt — and possibly the Skill configuration — before triggering a compression frame.

---

## Operating System

### Q: Why do Shell and Hull run in separate processes?

exec() executes LLM-generated code. That code can import any Python library, including native libraries with C extensions. Fatal errors in native libraries (abort, segfault) are not Python exceptions — try/except cannot catch them, and they kill the entire process. If exec() and the HTTP server share a process, a single native crash kills both the HTTP service and all Agent state simultaneously. Shell lives alone in the main process, never executes user code, and therefore never crashes.

### Q: Why put Hull + Cell + Kernel together in the subprocess rather than isolating just the Kernel?

If only the Kernel were in the subprocess while Skill instances (chat, tasks, etc.) remained in the main process, then LLM code calling `chat.read()` would require cross-process forwarding — every Skill method call would need argument serialization, a round-trip request, a wait for the response, and deserialization of the result. Worse, non-serializable objects such as database connections and file handles cannot be transferred between processes; they would be lost at the end of every frame. exec() and Skills must share a process, so Hull (which holds Skill instances) and the Kernel (which runs exec) cannot be separated.

### Q: How is state recovered after a subprocess crash?

Shell detects that the subprocess has exited, starts a new subprocess, and restores the namespace from the most recent `snapshot.pkl`. Non-serializable objects (database connections, etc.) are lost during recovery; they are recorded in `_dropped_keys` and reported to the LLM via a signal. The LLM reconstructs them in the next frame.

### Q: How do the processes communicate?

The Hull subprocess runs an HTTP service on an internal port (or Unix socket). Shell forwards incoming requests to it as-is. The protocol is standard HTTP, identical to how nginx proxies a Python application.

### Q: Why does each Agent need its own virtual environment?

LLM-generated code imports all kinds of packages. If multiple Agents share a single Python environment, one Agent installing numpy 1.26 will break another Agent that requires numpy 1.25. A per-agent `.venv` ensures isolation. The Hull subprocess is launched with `agent/.venv/bin/python`, and Skill dependencies are installed into that venv.

### Q: What is the relationship between Shell and Hull?

The same as Docker's relationship to the application inside it. If the application crashes, Docker does not crash. Shell wraps and runs an Agent (Hull and its internal components). The future Hall is to Shell what Kubernetes is to Docker — orchestrating multiple Shells.

