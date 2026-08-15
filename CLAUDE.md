# VEYRA — Genomic Intelligence

Hackathon MVP. Pipeline: DNA sequence → deterministic CRISPR guide/off-target analysis → genomic context → AI reasoning → interpretable risk assessment → interactive visualization.

## Ground rules

- **Hackathon MVP mode.** No git init, no commits, no CI/CD, no over-engineering. Ship the smallest thing that demos well.
- **Next.js + TypeScript**, App Router, Tailwind. Keep dependencies minimal — check what's already installed before adding a package.
- No backend service beyond Next.js API routes for now. No database unless a task explicitly needs persistence.
- This project runs on **Next.js 16** (scaffolded fresh) — its APIs/conventions may differ from older training data. See `AGENTS.md`'s auto-generated block and `node_modules/next/dist/docs/` before assuming older Next.js behavior (e.g. Pages Router patterns).

## Scientific integrity (non-negotiable)

- **Never fabricate scientific results, off-target scores, or clinical claims.** If a number isn't computed by the deterministic engine or explicitly returned by a model, don't show it as if it were.
- The **deterministic layer** (PAM search, GC content, mismatch/seed analysis, specificity ranking) is the source of truth for scores. It must be reproducible: same input sequence → same output every run.
- The **AI reasoning layer** interprets and explains deterministic output — it does not invent new scores. Every AI-generated claim in the UI should be traceable to either a deterministic number or clearly labeled as a model-generated hypothesis/explanation, not a fact.
- This is a prototype, not a clinical or regulatory tool. Any UI copy implying diagnostic, clinical, or regulatory validity is wrong — label things "research prototype" / "illustrative" where relevant.
- See [docs/scientific-assumptions.md](docs/scientific-assumptions.md) for the specific algorithms, formulas, and simplifications in use, and keep it updated when the model changes.

## Architecture

See [docs/architecture.md](docs/architecture.md).

## Engineering style

- Ladder: reuse existing code/components before adding new ones. No abstractions for a single use site.
- No speculative config, no feature flags, no "for later" scaffolding.
- Comments only for non-obvious WHY (biological assumptions, algorithm tradeoffs), never WHAT.
- Prefer editing existing files over creating new ones.
