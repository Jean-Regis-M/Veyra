# VEYRA — Demo Guide

Read-only audit finding, not a script to follow blindly — adapt to time available. Full evidence in `docs/PROJECT_HANDOFF.md` §16.

## Before judges arrive

1. Start all three services and verify each `/health` endpoint responds — they have repeatedly dropped between idle periods this session (operational quirk, not a code bug):
   - Backend: `cd veyra/backend && python -m uvicorn http_api.app:app --host 0.0.0.0 --port 8000` → `curl localhost:8000/health`
   - MIDEND: `cd veyra && python -m uvicorn midend.http_api.app:app --host 0.0.0.0 --port 8080` → `curl localhost:8080/health` (check `ai_configured: true`)
   - Frontend: `npm run dev` → `curl -o /dev/null -w "%{http_code}" localhost:3000`
2. Check `GET localhost:8000/models` to see which on-target model is actually verified right now (don't promise Rule Set 2/3 without checking — see Known Limitations).
3. Confirm `MIDEND_AI_API_KEY` is set and the provider isn't rate-limited/exhausted — `/chat` has no graceful fallback if the provider call fails.

## Demo flow

### Step 1 — Landing page (`/`)
**Do**: drag-rotate the 3D DNA model; scroll to "Why off-target evidence matters."
**Real**: the 3D model, the deterministic-core framing, the cited case studies (sickle-cell trial, T-cell cancer trial, India's regulatory gap — all sourced, stated only as strongly as the source states them).
**Simulated**: nothing on this page makes a computational claim.
**Say verbally**: "This is a research prototype — every score you'll see traces to a real algorithm, and we'll show you which one."

### Step 2 — `/chat` (the strongest wow moment)
**Do**: click "Start VEYRA Session," then either paste a sequence and ask "Find candidate SpCas9 cutting sites" or attach a FASTA file via the `+` button.
**Real**: every tool call shown in the live activity feed (`pam_scan`, `compute_gc_content`, `compute_cut_site`, etc.) is a genuine HTTP call to the backend, with real timing, that actually executed — not staged. The candidate table and cut-site geometry come directly from that evidence.
**Simulated**: the AI's prose interpretation is a real LLM call, but its text isn't a scientific instrument — it's explaining numbers that are.
**Say verbally**: "Every claim the AI makes traces to a named tool call you can expand — it's structurally required to call these tools before answering, not a suggestion."

### Step 3 — `/analyze`
**Do**: paste or upload a sequence, show the instant client-side candidate list, then (if backend is online) the real backend-confirmed scores layering in (CFD off-target, melting temp, homopolymer runs), and the 3D model's GC-driven color tint.
**Real**: PAM search and GC content in both engines; CFD/Tm/homopolymer once the backend responds.
**Simulated/heuristic**: the initial client-side off-target/specificity score is a custom penalty formula, not the published CFD model — say so if asked, don't imply it's the same math as the backend's.

### Step 4 — `/raw` (for technical judges)
**Do**: run `GET /health`, then something more specific like `POST /score/ontarget`.
**Real**: this is a byte-for-byte passthrough to the actual backend — nothing rendered here is reshaped or invented by the frontend.
**Say verbally**: "This proves there's no hidden layer between what you see and what the backend actually returns."

## Strongest wow moment
The `/chat` live tool-call activity feed — watching real HTTP calls resolve into a grounded answer, with full transparency into which tool produced which number, is the single most differentiated thing in this build relative to a typical "chatbot on top of an API" hackathon project.

## Things that could embarrass in a live demo — and how to avoid them

| Risk | Mitigation |
|---|---|
| A service dropped since last check | Re-run all three `/health` checks immediately before demoing, not just once at setup |
| Rule Set 2/3 on-target model isn't provisioned in this environment | Check `GET /models` first; fall back to describing `doench_2014` (always available) if RS2/RS3 show unverified |
| AI provider key exhausted/misconfigured | `/chat` will show a hard error, not a graceful mock — test one real message before judges arrive |
| Asked to recolor DNA per-nucleotide live | Don't attempt it — the GLB asset is a single fused mesh with texture-baked colors, structurally incapable of per-rung recoloring without a shader rewrite. Whole-model tint (GC-driven) is the real, demoable feature. |
| Asked about clinical/production readiness | Be direct: no auth, no persistence, no load testing, "research prototype, not for clinical or diagnostic use" is stated in the UI footer for a reason |
| Asked whether off-target scoring is validated | Real CFD algorithm (Doench 2016) with real CRISPOR data — but VEYRA itself hasn't run wet-lab validation, and the tool's own metadata says so |

## What to never claim, under any circumstance

- Chromatin/epigenetic context — not implemented anywhere in the codebase.
- Chromosomal rearrangement or long-range genomic context modeling — not implemented.
- Epistasis/gene-interaction modeling — not implemented.
- Clinical, diagnostic, or regulatory validity — explicitly disclaimed in the product itself.
- Wet-lab-validated off-target predictions — the algorithm is real and published; VEYRA's own use of it is not experimentally validated.
