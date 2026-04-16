---
name: memory
description: Cross-session memory
---

# memory

Cross-session key-value memory. Automatically shown in the signal, and monitors context pressure with warnings.

Core purpose: **search instead of keeping in context** — information that doesn't need to be in every frame should be stored in memory and retrieved when needed.

## Methods

memory.save(key, value) — Save a memory entry (written to disk immediately)
memory.get(key) — Read an entry; returns None if not found
memory.delete(key) — Delete an entry
memory.drop(n) — Physically delete the oldest n frames (at least 1 frame is always retained)

## Context Management Workflow

When the signal shows ⚠ context N% — summarize old frames then call memory.drop(n):

1. Use memory.save() to store key information from old frames
   memory.save("sprint-3-summary", "Completed X, found Y, next step Z")
2. Call memory.drop(n) to physically delete the summarized frames
   memory.drop(5)   # delete the oldest 5 frames
3. drop() prints a confirmation prompt; deletion takes effect after confirmation

Note: drop() only removes frames from in-memory frame stream; cold storage (JSONL log) is unaffected.

## Threshold Configuration

Default threshold is 50%, configurable in hull.toml:

[cell]
compress_threshold = 50   # show warning when context_pct exceeds this value

## Before sleep

Save important findings before calling sleep(); retrieve them with memory.get() after waking.
