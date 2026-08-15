# VEYRA Architecture (MVP)

## Pipeline

```
DNA sequence input
       │
       ▼
Deterministic genomic engine  (src/lib/genomic-engine)
  PAM search → filter → GC/properties → off-target scan → seed/mismatch weighting → ranking
       │
       ▼
Genomic context assembly  (candidate list + per-candidate features, JSON)
       │
       ▼
AI reasoning layer  (src/app/api/reason — server route calling an LLM)
  Explains ranked candidates, flags high-risk patterns, in plain language
       │
       ▼
Interpretable risk assessment  (structured: score + explanation, not just a number)
       │
       ▼
Interactive visualization  (3D DNA helix + results UI, src/components/dna, src/app/analyze)
```

## Layers

- **UI (Next.js App Router)** — `src/app/`. Landing page (`/`) and analysis flow (`/analyze`). Server Components by default; client components only for interactivity (input form, 3D canvas).
- **Deterministic engine** — `src/lib/genomic-engine/`. Pure TypeScript functions, no I/O, no LLM calls. This is the only source of numeric scores. See [scientific-assumptions.md](scientific-assumptions.md).
- **AI reasoning** — `src/app/api/reason/route.ts` (Next.js API route). Takes the deterministic engine's output as input, returns a structured explanation. Does not compute or override scores.
- **Visualization** — `src/components/dna/`. React Three Fiber double-helix component, driven by props (sequence, candidate positions, risk highlights) — no visualization-internal state that isn't derived from engine output.

## Data flow contract

`Sequence (string)` → `GenomicEngineResult` (candidates with scores, all deterministic) → optionally sent to `/api/reason` → `AIExplanation` (text tied to specific candidate IDs) → UI renders both together, never merges them into a single opaque number.

## Explicit non-goals for this MVP

- No database / persistence layer.
- No genome-wide reference index — off-target search is scoped to the provided sequence/context window (see scientific-assumptions.md).
- No auth, no multi-user state.
- No CI/CD, no deployment pipeline.
