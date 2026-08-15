---
name: code-review
description: Use for a quick self-review pass on VEYRA code before considering a change done — correctness, scope, and scientific-integrity checks specific to this project.
---

# Code Review (VEYRA-specific)

Fast checklist, not a formal process — this is a 2-hour hackathon build.

- **Scope**: does the diff do only what was asked? No drive-by refactors, no speculative config.
- **Determinism boundary**: any new code in `src/lib/genomic-engine/` — is it still pure (no randomness, no network/LLM calls)? Any new AI-facing code — does it only *consume* engine output, never invent scores? See [[genomic-engine]] and [[scientific-review]].
- **Dependencies**: did this change add a package? Could it have been done with what's already installed?
- **Types**: no `any` creeping in on the engine or API boundary types — those are the contracts between deterministic/AI/UI layers.
- **Dead code**: no unused exports, no commented-out blocks left behind.
- **UI copy**: run [[scientific-review]] if the change touches anything user-visible showing scores/results.
