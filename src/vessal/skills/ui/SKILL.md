---
name: ui
description: Control the agent body and page environment
---

# ui

Controls the Agent's body (hermit crab avatar) and page environment (components). The signal shows body state, page layout, and pending events.

## Body Methods

ui.body.move_to(target) — Move the avatar (pass a coordinate tuple or element id)
ui.body.speak(text, duration=3) — Display a speech bubble
ui.body.emote(emotion) — Switch expression (idle/thinking/working/happy/sleeping/confused)
ui.body.point_at(element_id) — Point at a component
ui.body.offer_choices(options) — Show a choice bubble
ui.body.ask(prompt) — Show an input dialog

## Environment Methods

ui.render(components) — Update page components
ui.read() — Get user events and clear the inbox (click/avatar_tap/choice/input_submit, etc.)
ui.current_layout() — Return the current full page state

## Components

ui.text(content) — Text
ui.card(children, title=...) — Card container
ui.button(label, id) — Button (id required for event identification)
ui.input(placeholder, id) — Input field (id required for event identification)
ui.panel(title, children, position=...) — Panel
ui.chart(data, kind="bar") — Chart

## Usage

When a UI event arrives (signal shows pending events):

```python
events = ui.read()
for e in events:
    if e["event"] == "click" and e["id"] == "go":
        result = do_work()
        ui.body.speak("Done!")
        ui.render([ui.panel("Result", [ui.text(str(result))])])
```

Building the initial page:

```python
ui.body.emote("happy")
ui.body.speak("Hello! How can I help you?")
ui.render([
    ui.panel("Welcome", [
        ui.text("Click the button below to get started"),
        ui.button("Start", id="start"),
    ]),
])
```
