# UI

Cyber-embodiment Skill. Two-layer architecture: body (avatar control) + component environment. Server-driven; Python namespace is the sole source of state.

Responsible for:
- Avatar control (position, emotion, speech bubble, interaction options)
- Component environment (panels, buttons, charts, and other 6 basic component types)
- User event collection (clicks, inputs, avatar clicks)
- Rendering page state summary each frame (_signal)
- Injecting cognitive protocol (_prompt)
- HTTP routes (/render polling, /events event receiving, static files)

Not responsible for:
- Frontend local visual feedback (hover, animation transitions — handled by frontend)
- Persistence (UI state is pure in-memory; no file writes)
- Communication with other Skills (strictly forbidden inter-Skill coupling)

## Design

### Two-Layer Model

Layer 1 body: hermit crab avatar. 6 methods control position, emotion, speech, pointing, selection, and input. Within-frame calls accumulate into the action queue; body._drain() exports and clears the queue on render() (retaining state fields position/emotion/speech). _drain() returns a deepcopy to prevent callers from accidentally modifying the internal queue.

Layer 2 ui: component environment. 6 factory methods generate dicts; render() serializes and pushes. Frontend uses replaceWith for full-tree DOM replacement (no diff, avoiding event listener leaks).

### Data Flow

AI frame code → body._drain() + components → render spec JSON → HTTP → frontend rendering
User action → frontend event → POST /events → skill._inbox → AI next frame ui.read()

### Animation Rhythm

Frontend plays CSS idle animation during thinking (between frames). Body actions in frame code are played sequentially through the frontend action queue; each action has 200-600ms transition.

## Public Interface

### class UI

Cyber-embodiment Skill — Agent's body and environment.


## Tests

- `test_body.py` — Body unit tests — avatar action queue and serialization.
- `test_components.py` — Component factory method unit tests.
- `test_server.py` — UI Server routing tests.
- `test_ui.py` — UI Skill integration tests.

Run: `uv run pytest src/vessal/skills/ui/tests/`


## Status

### TODO
None.

### Known Issues
None.

### Active
None.
