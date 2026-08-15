---
name: demo
description: Use when preparing VEYRA for a live hackathon demo or recording — checklist for a smooth run-through.
---

# Demo Prep

## Before demoing

- Pick 1-2 known-good example sequences (short, clean, produce a clear ranked guide list and at least one visible off-target/risk highlight) and hardcode them as quick-fill buttons on the input screen — don't rely on typing/pasting live.
- Confirm `npm run dev` starts clean with no console errors.
- Run through the full flow once end-to-end: landing → click into analyze → paste/select sequence → run → results with 3D visualization → AI explanation panel.
- Check the 3D DNA visualization renders and rotates smoothly on the actual demo machine (perf can differ from dev laptop).
- Have a fallback if the AI reasoning call fails or is slow live (loading state, or a cached/precomputed example response) — a hung network call mid-demo is the most common failure mode.

## Talking points (tie back to the problem statement)

- Deterministic engine = full transparency on every score (no black box).
- 3D context view = the "long-range context" existing tools (BLAST/CRISPOR) structurally can't show.
- AI reasoning layer = explains *why* a site is risky, not just a probability number.
- Say explicitly: this is a research prototype/illustrative pipeline, not a validated clinical tool — see [[scientific-review]].
