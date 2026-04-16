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

## Constraints

1. body and ui components are independent objects; they do not call each other; communicate indirectly via namespace
2. button and input must specify id (for event identification)
3. render() replaces the entire component tree; does not append
4. read() clears inbox; consistent with chat.read() behavior
5. _signal() includes complete page state summary (body + components + events)
6. _prompt() must not contain method signatures
7. Frontend plays body actions in the action queue sequentially; there is a transition delay between each action
8. Clicking avatar is a fixed wake/interrupt entry; events go through UI Skill's own inbox

## Design

### Two-Layer Model

Layer 1 body: hermit crab avatar. 6 methods control position, emotion, speech, pointing, selection, and input. Within-frame calls accumulate into the action queue; body._drain() exports and clears the queue on render() (retaining state fields position/emotion/speech). _drain() returns a deepcopy to prevent callers from accidentally modifying the internal queue.

Layer 2 ui: component environment. 6 factory methods generate dicts; render() serializes and pushes. Frontend uses replaceWith for full-tree DOM replacement (no diff, avoiding event listener leaks).

### Data Flow

AI frame code → body._drain() + components → render spec JSON → HTTP → frontend rendering
User action → frontend event → POST /events → skill._inbox → AI next frame ui.read()

### Animation Rhythm

Frontend plays CSS idle animation during thinking (between frames). Body actions in frame code are played sequentially through the frontend action queue; each action has 200-600ms transition.

## Status

### TODO
None.

### Known Issues
None.

### Active
- 2026-04-13: Initial implementation
