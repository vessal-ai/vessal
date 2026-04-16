# Vessal Whitepaper V5 — Crab

Fifth-generation specification. Codename Crab — a hermit crab's exoskeleton (Shell) protects the soft body (Hull) and the brain (Cell). The shell controls inbound communication; the kernel stays minimal.

V5 begins with the action space problem: where other Agent frameworks hand the LLM a finite menu of functions, Vessal hands it a Turing-complete programming language. That choice, worked through the SORA loop (State, Observation, Reasoning, Action), derives both the three-layer architecture and the three runtime problems that must be solved. A Skill is the Agent's two-sided interface to the outside world — composed of a skill class on the Cell side and an independent server on the Hull side. The final chapters show that the same architecture that runs agents also generates structured RL-ready training data — and that cache coordination can turn this insight into a practical deployment-training loop.


## Chapters

`01-problem.md` — Problem and Choice. The action space problem, the SORA loop, code as action, and the three runtime problems that must be solved.

`02-architecture.md` — Three-Layer Architecture. Cell (compute), Hull (orchestration), Shell (inbound boundary + gateway + guardianship). The Ping-Pong protocol, Gate review, the cost of outbound safety, the containment model, and an OS-level perspective (process / thread / memory / disk).

`03-skills.md` — The Skill Model. The two-sided interface (Agent ↔ outside world). Separation of Skill class and server. Meta-skills. Kernel duck-typing discovery. Load and unload protocol.

`04-frame.md` — Frame Protocol. Ping structure (system_prompt + state), Pong structure (think + action). The lifecycle of a single frame, signal, sleep, and compression.

`05-embodiment.md` — Embodiment and Evolution. The hermit crab model (shell = Shell, body = cognitive core, claws = Skills). Shell as an abstraction layer (standalone / container / embedded). Skills as organs (hardware access). exec() and container isolation. The evolutionary path (user-space → containerized → Agent-is-OS). Agent definition (including Shell configuration).

`06-cache.md` — Cache Coordination. KV Cache and Prefix Cache mechanics. How Agent frameworks systematically destroy the inference engine's caching optimizations. Five Cache-Aware Context construction principles (P1–P5) — derived from the physical constraints of Transformer Attention. System prompt purification, three-stage reverse compression, and the adapter pattern. Four layers of optimization strategy (framework-independent → API cooperation → module registration → non-prefix reuse). The ultimate path: baking the protocol into model weights.

`07-training.md` — Training and Scaling. The SORA loop as a Markov Decision Process. Structured trajectories as self-annotating training data. Three scaling axes (parameters, trajectories, environment complexity). RL from environment feedback. The virtuous cycle from deployment through training to redeployment.

`QA.md` — Design Discussion Summary. Specific Q&A covering details not addressed in the main text.


## Reading Order

Front to back. Each chapter builds on the conclusions of the one before it.


## Relationship to Component READMEs

The whitepaper argues the macro-architecture. Component READMEs describe concrete implementation and development status. The whitepaper answers *why* and *what*; the READMEs answer *how* and *how far along*.
