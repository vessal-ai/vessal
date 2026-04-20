# render

Sub-package for rendering namespace to Ping. This is an internal implementation detail of Kernel and should not be directly imported from outside Kernel.

Responsible for:
- render(ns, config) -> Ping: main entry point, assembles system_prompt + frame stream + signals
- RenderConfig: render configuration (system_prompt_key, frame_budget_ratio)
- SystemPromptBuilder + Section: modular system_prompt assembly
- Frame stream trimming: trims frame history by token budget (_frame_render.py)
- Signal rendering: concatenates _signal_outputs (_signal_render.py)

Not responsible for:
- Holding namespace (handled by Kernel)
- Signal collection (handled by Kernel.update_signals())
- LLM calls (handled by Core)

## Design

The render sub-package exists to encapsulate the complete assembly logic of "namespace to inference input". Ping has three fields (system_prompt, frame_stream, signals); the computation logic for each field differs; each is handled by a separate module: renderer.py is the main coordinator, _frame_render.py handles frame stream trimming, _signal_render.py handles signal concatenation, prompt.py handles modular system_prompt assembly.

Frame stream budget trimming is the core algorithm: context_budget - max_tokens is the total budget; subtract system_prompt token count then multiply by frame_budget_ratio to get the frame stream budget. When over budget, frames are dropped starting from the oldest.

## Public Interface

### DEFAULT_CONFIG

Default RenderConfig instance used by Kernel when no explicit config is supplied.

### class RenderConfig

Renderer configuration.

### render(ns: dict[str, Any]) -> str

Renders validation result section.


## Tests

_No test directory._


## Status

### TODO
None.

### Known Issues
None.

### Active
None.
