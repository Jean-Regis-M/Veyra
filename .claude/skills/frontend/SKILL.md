---
name: frontend
description: Use when building or editing VEYRA's Next.js UI — landing page, product flow screens, layout, components, styling.
---

# Frontend (VEYRA)

Next.js App Router + TypeScript + Tailwind. Premium scientific/technical aesthetic: dark base, precise typography, restrained color (bio-signal accent — teal/cyan or violet on near-black), generous whitespace, monospace for sequence/data display.

## Rules

- Reuse components from `src/components/` before creating new ones.
- Server Components by default; add `"use client"` only where interactivity (state, effects, three.js canvas) requires it.
- No UI component library beyond what's installed. Tailwind + hand-rolled components is enough for this MVP.
- Sequence/data text uses a monospace font (e.g. `font-mono`) to read as genomic/technical data, not prose.
- Never render a number as a "score" or "risk" unless it came from the deterministic engine or an explicitly-labeled AI response — see [[scientific-review]].
- Keep the landing page, analysis input, and results view as separate routes/pages, not one giant page.

## Structure

- `src/app/` — routes (`/` landing, `/analyze` input+results)
- `src/components/` — shared UI (nav, cards, sequence display, risk badges)
- `src/components/dna/` — three.js DNA visualization (see [[threejs-dna]])
- `src/lib/` — genomic engine + API client helpers
