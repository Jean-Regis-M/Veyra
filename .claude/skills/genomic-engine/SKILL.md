---
name: genomic-engine
description: Use when building or editing the deterministic CRISPR guide-RNA scoring pipeline — PAM search, GC content, off-target/mismatch analysis, candidate ranking.
---

# Genomic Engine (deterministic layer)

This is the source-of-truth scoring pipeline. Pure TypeScript, no external bio APIs required for the MVP — everything computable from the input sequence(s) locally.

## Pipeline (matches docs/scientific-assumptions.md)

1. **Ingest** — parse/validate the input DNA sequence (A/C/G/T only, uppercase, reject invalid chars with a clear error).
2. **PAM search** — scan for valid PAM sites (default SpCas9 `NGG`, both strands).
3. **Filter candidates** — drop guides that fail basic validity (length, N-content, PAM-proximity).
4. **Sequence properties** — GC content and other per-candidate features.
5. **Off-target prediction** — search the same input/reference for near-matches (mismatch-tolerant substring scan). No genome-wide index for the MVP — score off-targets found within the provided sequence/context window, and say so in the UI.
6. **Mismatch/seed analysis** — weight mismatches near the PAM-proximal seed region higher (they matter more for specificity) than distal mismatches.
7. **Ranking** — combine into a specificity/quality score per candidate, sorted.

## Rules

- Every function here must be **pure and deterministic**: same sequence in → same candidates/scores out, every time. No randomness, no calls to an LLM in this layer.
- Keep it in `src/lib/genomic-engine/` as plain TS functions with explicit types — this is the part most likely to get scrutinized, so keep it simple and readable over clever.
- This is a simplified/illustrative implementation, not a validated clinical tool (no genome-wide reference, no chromatin data) — [[scientific-review]] and docs/scientific-assumptions.md must reflect that honestly.
- The AI reasoning layer consumes this output; it must not need to re-derive or override these numbers.
