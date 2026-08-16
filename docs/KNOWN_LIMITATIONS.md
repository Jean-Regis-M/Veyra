# VEYRA — Known Limitations

Read-only audit finding. Full evidence and per-claim table in `docs/PROJECT_HANDOFF.md` §15/§18.

## Scientific limitations

- **Client-side off-target/specificity scoring is a bespoke heuristic**, not a published or validated model. It is deterministic (reproducible) but the seed-weighting formula (`seedMismatches × 8`, `distalMismatches × 2`, plus a closeness bonus) was authored for this project, not sourced from literature. Do not present it as equivalent to CFD.
- **No chromatin, epigenetic, or 3D-genome context anywhere in the codebase.** The 3D visualization shows sequence/structural context only, not chromatin accessibility.
- **No chromosomal rearrangement or long-range genomic context modeling.**
- **No epistasis / gene-interaction modeling.**
- **Off-target search is scoped to the input sequence only** in the client heuristic and in `/analyze` before backend confirmation; genome-scale search exists on the backend (Cas-OFFinder-backed) but requires a registered reference genome.
- **CFD off-target scoring is real** (Doench et al. 2016, using the actual CRISPOR `mismatch_score.pkl`/`pam_scores.pkl` resources) but its own output metadata explicitly states it is "NOT experimentally validated by VEYRA."
- **On-target efficiency models (Doench 2014 / Rule Set 2 / Rule Set 3) are real, published models** with a transparent fallback chain, but Rule Set 2/3 depend on isolated Python runtime provisioning (`rs3`, `azimuth`, LightGBM) that is not pinned in `veyra/backend/requirements.txt`. Whether they resolve on a fresh clone without manual setup is `UNKNOWN — requires verification`.
- **No clinical, diagnostic, or regulatory validity anywhere** — and the product explicitly disclaims this in its own footer copy.

## Technical / engineering limitations

- **Zero automated frontend tests.** No `*.test.*`/`*.spec.*` files exist in `src/`. All frontend verification has been manual, browser-driven testing.
- **Two committed docs are stale**: `docs/architecture.md` and `docs/scientific-assumptions.md` describe only the earlier, client-only version of the system and omit the entire Python backend and MIDEND layer. Do not treat them as current.
- **Dead code**: `src/app/midend/MidendConsole.tsx` is no longer referenced — `midend/page.tsx` now re-exports `ChatConsole` instead.
- **No dependency manifest for MIDEND** (`veyra/midend/` has no `requirements.txt`/`pyproject.toml`), and the backend's manifest omits the on-target-model dependencies actually used by `core/ontarget.py`.
- **No process supervision.** Three independent long-running services (frontend, backend, MIDEND) with no Docker Compose, no process manager — they have dropped between idle periods repeatedly during this project's development and must be manually restarted each time.
- **No auth, no rate limiting, no persistence layer anywhere.** Acceptable for a local hackathon demo; a real gap before any shared or hosted deployment.
- **AI reliability is fully dependent on an external provider** (`MIDEND_AI_*` env vars, default `https://api.llm7.io/v1`). The `/chat` path has no graceful degraded mode if the provider call fails — the `/analyze`-only `/api/reason` route does have a deterministic stub fallback, but `/chat` does not.
- **No CI/CD, no Dockerfile, no deployment configuration** found anywhere in the repository.

## Explicitly NOT implemented (never claim these exist)

- Chromatin/epigenetic accessibility modeling
- Long-range/3D genome context beyond the provided sequence
- Epistatic interaction modeling
- Genome-wide off-target indexing without an explicitly registered reference genome
- Wet-lab experimental validation of any score produced by this system
- Clinical, diagnostic, or regulatory-grade risk assessment
- Per-nucleotide/per-rung 3D recoloring (the shared GLB asset is a single fused mesh with texture-baked colors and no vertex-color attribute — structurally incapable of this without a shader rewrite or asset replacement)

## Path to closing the biggest gaps (not a commitment, just the logical next steps)

1. Update or retire `docs/architecture.md` and `docs/scientific-assumptions.md` so they reflect the current three-tier system.
2. Add a minimal frontend test layer (even a handful of component/route smoke tests) to catch regressions the manual-testing-only workflow currently misses.
3. Pin MIDEND's dependencies explicitly; add the on-target-model dependencies to the backend manifest or document the isolated-runtime provisioning step clearly.
4. Verify Rule Set 2/3 model availability from a genuinely fresh clone, not just the currently-provisioned dev environment.
5. Remove the orphaned `MidendConsole.tsx` once confirmed unused.
