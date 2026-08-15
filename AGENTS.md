<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->


## What VEYRA is

DNA sequence → deterministic CRISPR guide/off-target analysis → genomic context → AI reasoning → interpretable risk assessment → interactive visualization. Hackathon MVP, Next.js 16 + TypeScript.

## Hard constraints

- No `git init`, no commits, no CI/CD work. This is explicitly out of scope right now.
- No fabricated scientific numbers. Deterministic scores come from the scoring engine (`src/lib/genomic-engine` or equivalent) only. AI output explains/interprets, never invents a score.
- Minimal dependencies. Don't add a package if a few lines of TS or an already-installed lib does the job.
- Don't build the full backend. API routes in the Next.js app are enough for the MVP.

## Where things live

- `docs/architecture.md` — system layers and data flow.
- `docs/scientific-assumptions.md` — exact formulas/algorithms used and their known limitations. Update this file, don't just update code, if you change how scoring works.
- `.claude/skills/` — task-specific playbooks (frontend, threejs-dna, genomic-engine, scientific-review, code-review, demo). Skim the relevant one before starting related work.

## Priorities (in order)

1. Landing page (premium scientific/technical aesthetic, 3D DNA visualization)
2. 3D DNA visualization component
3. Core product flow (sequence input → analysis → results)
4. Demo-ready genomic analysis UI
5. Deterministic analysis prototype
6. AI reasoning integration point

## Working style

Smallest working diff. Reuse existing components/utilities before writing new ones. No speculative abstractions or config for hypothetical future needs.
