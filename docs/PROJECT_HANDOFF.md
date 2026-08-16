# VEYRA — Project Handoff

Read-only audit of the repository as it exists today. This is not a design doc — it describes what is actually built, verified by reading source code, running `tsc`/`eslint`, and live-testing the running application. Where something could not be verified, it is marked `UNKNOWN — requires verification`.

**Important finding up front:** the two committed docs `docs/architecture.md` and `docs/scientific-assumptions.md` describe an **earlier, smaller version** of VEYRA (client-side-only heuristic engine + one `/api/reason` route). They predate the Python backend, the MIDEND AI-orchestration service, `/chat`, `/raw`, `/midend`, file upload, and calibration. Anyone using those two files as ground truth will get an outdated picture. This handoff supersedes them; they have not been edited (out of scope for this audit) but should be updated or retired in a follow-up.

---

## 1. What VEYRA actually is

A three-tier CRISPR/Cas9 guide-RNA design and off-target risk-assessment tool:

1. **Frontend** (Next.js 16) — UI, a client-side heuristic scoring engine, a 3D DNA visualization, and three distinct ways to reach the backend (direct REST calls, a raw API console, and an AI chat orchestrated by MIDEND).
2. **MIDEND** (FastAPI/Python) — an AI-orchestration layer. Never computes biology itself; it calls the backend's real tools and has an LLM interpret the results.
3. **Backend** (FastAPI/Python) — the deterministic scientific core: PAM scanning, GC/Tm/homopolymer/secondary-structure features, CFD off-target scoring (real CRISPOR pickle data), and on-target efficiency prediction (Doench 2014 / Rule Set 2 / Rule Set 3, with a documented fallback chain).

All three run as separate local processes (ports 3000 / 8080 / 8000) with no shared database.

---

## 2. Repository map (top level)

```text
VEYRA/
├── src/                        Next.js app (frontend) — see §3
├── veyra/
│   ├── backend/                Python/FastAPI deterministic engine — see §4
│   ├── midend/                 Python/FastAPI AI orchestration layer — see §5
│   ├── data/                   Reference genomes, model envs, resource caches
│   ├── cache/                  Runtime cache (SQLite, model runtime state)
│   └── midend.md                Machine-facing MIDEND API contract doc
├── docs/
│   ├── architecture.md          STALE — describes pre-backend architecture only
│   ├── scientific-assumptions.md STALE — describes only the client heuristic engine
│   └── (this audit's new files)
├── public/models/               dna.glb — the shared 3D asset
├── package.json                 Frontend dependency manifest
└── CLAUDE.md / PRODUCT.md / DESIGN.md   Project instructions/notes (untracked in git for the latter two)
```

Root also contains several stray one-off report `.md` files (`AGENTIC_ROBUSTNESS_REPORT.md`, `CONTEXT_AUDIT.md`, `PORTABILITY_PATH_AUDIT.md`, `TOOLSET_FREEZE_REPORT.md`, `Status.md`, `pending.md`, `site.md`) — these look like prior ad-hoc session artifacts, not living documentation. Not modified by this audit.

---

## 3. Frontend — file-by-file

```text
src/
├── app/
│   ├── page.tsx                 Landing page. Hero, 3D DNA, readouts, pipeline demo,
│   │                            "Approach" cards, "Why off-target evidence matters"
│   │                            (cited real-world CRISPR case studies), footer.
│   ├── layout.tsx                Root layout — fonts, global CSS, <Header/>.
│   ├── globals.css               Design tokens (glass, colors, animations). Tailwind v4.
│   ├── analyze/
│   │   ├── page.tsx               Thin wrapper
│   │   └── AnalyzeClient.tsx       Sequence paste + file upload (FASTA/FASTQ/GenBank) →
│   │                               client heuristic engine → optional real backend
│   │                               scoring (on-target, CFD, Tm, homopolymer) → 3D tint.
│   ├── api/
│   │   ├── ingest/route.ts         Bridges browser file upload → backend's real
│   │   │                           /ingest (path-only endpoint) → extracts sequence
│   │   │                           text locally (backend never returns sequence text).
│   │   └── reason/route.ts         AI explanation for /analyze candidates. Tries
│   │                               MIDEND_AI_*/OPENAI_* → ANTHROPIC_API_KEY → stub.
│   ├── chat/
│   │   ├── page.tsx                 Thin wrapper
│   │   └── ChatConsole.tsx (27KB)    THE primary AI experience. Session start,
│   │                                 file/calibration attach, live tool-call activity
│   │                                 feed, DNA & Evidence side panel. Talks to MIDEND.
│   ├── midend/
│   │   ├── page.tsx                  Now just re-exports ChatConsole (see §14 finding)
│   │   └── MidendConsole.tsx          ORPHANED — my earlier standalone MIDEND console,
│   │                                  no longer referenced by any route.
│   ├── raw/
│   │   ├── page.tsx                  Thin wrapper
│   │   └── RawConsole.tsx             Generic UI over all 27 backend HTTP routes —
│   │                                  no AI, exact request/response passthrough.
│   └── docs/page.tsx                  Renders a static in-app user-guide (MarkdownViewer).
├── components/
│   ├── dna/HelixModel.tsx             The 3D DNA component — see §8 for full detail.
│   ├── DnaAnalysisPanel.tsx           Side panel used by ChatConsole (linear track view).
│   ├── Header.tsx                     Shared nav (Overview/Analyze/VEYRA Chat/Docs/Raw API).
│   ├── PipelineDemo.tsx               Landing-page clickable 5-step pipeline visual.
│   ├── Reveal.tsx                     Scroll-triggered fade-in wrapper (IntersectionObserver).
│   ├── MarkdownViewer.tsx             Renders docs/ content in-app.
│   └── execution/                     ToolCallRow, SkillCallRow, ParallelGroupRow,
│                                       AIActivityRow, ExecutionActivity — render MIDEND's
│                                       live tool-call/AI-generation timeline.
└── lib/
    ├── backend.ts                     Typed client for the Python backend (:8000).
    ├── backendEndpoints.ts            Manifest of all 27 backend routes (powers /raw).
    ├── midend.ts                      Typed client for MIDEND (:8080).
    ├── examples.ts                    Two hardcoded demo sequences for /analyze.
    └── genomic-engine/index.ts        Client-side heuristic CRISPR engine — see §6.
```

Every `page.tsx` under `app/` is a thin Server Component wrapper around one `"use client"` component; all real logic lives in those client components.

---

## 4. Backend (`veyra/backend/`) — architecture

```text
backend/
├── http_api/app.py         FastAPI app, 27 routes (§9). CORS allows localhost:3000.
├── core/                   Thin request/response adapters — delegate to mcp/tools/*.
├── mcp/tools/               THE actual algorithm implementations (18 tools, real math).
├── parsers/                 FASTA/FASTQ/GenBank parsers (Biopython-backed).
├── schemas/                 Pydantic request/response models + GenomicRecord.
├── services/ingestion.py     Format detection → parse → validate → optional PAM scan.
├── references/               CRISPOR CFD pickle resources, reference genome access.
├── utils/                    Validation helpers.
├── cli/main.py               CLI entrypoint (same core functions as the HTTP API).
└── tests/                    8 test files (§12).
```

Design pattern throughout: `http_api/app.py` → `core/*.py` (validates + adapts) → `mcp/tools/*.py` (does the actual computation) → typed `ToolResult`/`VeyraResult`. The CLI and MCP interfaces reuse the exact same `core/` functions, so there is one source of truth for every score.

Started via `python -m uvicorn http_api.app:app --host 0.0.0.0 --port 8000` **from inside `veyra/backend/`**.

---

## 5. MIDEND (`veyra/midend/`) — architecture

```text
midend/
├── http_api/app.py          FastAPI app, 36 routes (§9). CORS allows localhost:3000.
├── control_plane.py          THE orchestration core (~900+ lines). Conversation store,
│                              PromptBuilder, execution state machine, skill dispatch,
│                              input registry (analysis + calibration file validation).
├── ai/openai_compatible.py    OpenAI-Chat-Completions-compatible provider client.
├── config/ai_provider.py      Reads MIDEND_AI_BASE_URL/API_KEY/MODEL from env/.env.
├── connectors/                HTTP connector (calls backend over REST) + MCP connector.
├── skills/                    3 registered skills — see §7.
├── input_validation.py        Validates uploaded analysis/calibration files, assigns
│                              typed IDs (input_..., calib_...).
└── tests/                     15 test files (§12) — the most heavily tested part of VEYRA.
```

MIDEND never imports or reimplements backend algorithms — it calls the backend's HTTP (or MCP) API for every number, then asks the configured LLM to interpret the *results*. This separation is enforced structurally (there is no scoring math anywhere in `veyra/midend/`, confirmed by search).

Started via `python -m uvicorn midend.http_api.app:app --host 0.0.0.0 --port 8080` **from `veyra/`** (its relative imports require `midend` to be the top-level package — running it from inside `veyra/midend/` fails).

---

## 6. Deterministic engines — REAL vs HEURISTIC (critical distinction)

VEYRA has **two independent scoring pipelines**. This is the single most important architectural fact for anyone extending or demoing the product.

### 6a. Client-side heuristic engine — `src/lib/genomic-engine/index.ts`

Runs entirely in the browser, no network call. Used by `/analyze` for instant candidate discovery before/regardless of backend availability.

| Feature | Classification | Detail |
|---|---|---|
| PAM search (NGG) | REAL IMPLEMENTATION | Manual character scan, both strands, exact NGG match |
| GC content | REAL IMPLEMENTATION | Simple fraction, thresholds at 20%/40%/65%/80% |
| Off-target search | HEURISTIC | Mismatch-tolerant scan **within the same input sequence only** — no genome index |
| Seed-region weighting | HEURISTIC | Custom formula: `seedWeight = seedMismatches × 8`, `distalWeight = otherMismatches × 2`, plus a closeness bonus — not CFD, not any published model |
| Specificity/overall score | HEURISTIC | `100 - penalty`, then a flat −15 GC penalty if GC is "low" |
| Risk level | HEURISTIC | Thresholds on the above: ≥75 low, ≥45 moderate, else high |

This is deterministic (same input → same output, pure functions, no randomness) but it is **not a published or empirically validated model**. `docs/scientific-assumptions.md` documents this pipeline accurately.

### 6b. Backend — `veyra/backend/`

Runs as a real Python service. Reachable via `/analyze` (when backend is online), `/raw`, and MIDEND tool calls from `/chat`.

| Feature | Classification | Detail |
|---|---|---|
| PAM search | REAL IMPLEMENTATION | `mcp/tools/pam_scan.py` — regex from IUPAC pattern, both strands, 1-based half-open coordinates |
| GC content, Tm, homopolymer runs, secondary structure, positional features, dinucleotide composition, seed GC, cut-site | REAL IMPLEMENTATION | Each a dedicated `mcp/tools/*.py`; secondary structure uses ViennaRNA (optional dependency — see §11) |
| Off-target search | REAL IMPLEMENTATION (scope-limited) | `mcp/tools/offtarget_search.py` — Cas-OFFinder-backed for genome-scale search when a genome is registered; otherwise scoped to input |
| CFD off-target scoring | REAL IMPLEMENTATION | `mcp/tools/score_offtargets.py` — genuine CFD algorithm (Doench et al. 2016) using the actual CRISPOR `mismatch_score.pkl`/`pam_scores.pkl` resources. Output explicitly labeled "NOT experimentally validated by VEYRA" in its own metadata. |
| On-target efficiency | REAL IMPLEMENTATION, multi-model | `core/ontarget.py` — `doench_2014` (hand-ported linear regression, always available), `rule_set_2` (Azimuth/Fusi, requires isolated Python runtime), `rule_set_3` (LightGBM via the `rs3` package). `auto` mode picks the highest-priority **verified** model with a fully reported fallback chain (never silently substitutes). |
| Ranking | REAL IMPLEMENTATION | `mcp/tools/rank_candidates.py` — combines the above into a ranked list |
| Model calibration | REAL IMPLEMENTATION | Deterministic least-squares fit against user-supplied labeled CSV/TSV (see §7, `model_calibration` skill) |

**No chromatin/epigenetic context, no long-range 3D genome data, no clinical/regulatory validity anywhere in the codebase** — confirmed absent by search across both `src/` and `veyra/`.

---

## 7. AI reasoning layer — two separate paths

### 7a. `/api/reason` (Next.js route, used only by `/analyze`)

Simple one-shot: takes the top 5 client-heuristic candidates, builds a text prompt ("do not invent scores"), and tries, in order: MIDEND-configured OpenAI-compatible endpoint → `ANTHROPIC_API_KEY` → a deterministic stub response listing the same numbers in template sentences. No tool calling, no streaming, no memory.

### 7b. MIDEND `control_plane.py` (used by `/chat`, the primary experience)

Genuinely agentic: `PromptBuilder.build()` assembles `[system instructions, developer context, compacted conversation history, injected tool-evidence block, user message]` and sends it to the configured provider (`ai/openai_compatible.py`, OpenAI-Chat-Completions-compatible; base URL/model/key from `MIDEND_AI_*` env vars, default provider `https://api.llm7.io/v1`).

The **actual system prompt** (verbatim, `control_plane.py:810-818`):
> "You are VEYRA — VEYRA Intelligence, an interpretable genomic intelligence engine for CRISPR/Cas9 guide design, sequence analysis, and empirical model calibration. [compact tool directory] MANDATORY TOOL USE RULE: Whenever the user asks to find PAM sites, design/evaluate CRISPR guides, calculate sequence properties (GC, Tm, cut sites, homopolymers), search off-target loci, evaluate toxicity risk, or calibrate models, you MUST invoke the appropriate native tool or skill to obtain real deterministic evidence before providing your final answer. Ground all biological claims directly in deterministic tool evidence."

Three registered **skills** (`veyra/midend/skills/`), each a structured workflow that only calls real backend tools:
- `spcas9_gene_cutting` — PAM discovery + cut-site + feature evidence + optional on/off-target scoring + ranking
- `offtarget_toxicity_risk` — combines explicitly-provided off-target features into a risk estimate; explicitly refuses to substitute missing features
- `model_calibration` — deterministic least-squares fit against a user's labeled CSV/TSV dataset

Execution is asynchronous: `POST /ai/chat` → `execution_id` → frontend polls `GET /executions/{id}` (an SSE `/stream` endpoint exists server-side but the frontend uses polling, not `EventSource` — confirmed by grep of `ChatConsole.tsx`).

---

## 8. 3D visualization architecture (`src/components/dna/HelixModel.tsx`)

- **Stack**: React Three Fiber (`@react-three/fiber`) + drei (`OrbitControls`, `useGLTF`, `ContactShadows`, `Html`) + three.js.
- **Asset**: `public/models/dna.glb` — a single fused mesh (~51,000 vertices), one `MeshStandardMaterial`, colors baked into a diffuse texture. **No vertex-color attribute** — confirmed by an earlier in-session debug probe. This means per-nucleotide/per-rung recoloring is not possible with this asset without a shader rewrite or a replacement model; the codebase never attempts it.
- **Auto-orientation**: on load, samples ~1000 mesh vertices, computes the principal axis via power-iteration PCA, and rotates that axis onto world-Y — makes the helix stand upright regardless of how it was exported, without hardcoding a rotation.
- **Normalization**: bounding box computed post-rotation, uniformly scaled to a fixed max dimension (8 units), recentered at the origin.
- **Coloring**: whole-model tint only, via `material.color.lerp(tintColor, 0.4)` on a **cloned** material (cloning is required — `Object3D.clone()` does not clone materials, and an earlier bug from mutating the shared material in place caused colors to compound across renders).
- **Hotspots**: 5 fixed structural labels (5′ terminus, major/minor groove, base pair, backbone) defined by a target (height-fraction, angle) and snapped at runtime to the nearest actual sampled vertex — avoids raycasts missing through the helix's open gaps. Rendered via drei's `<Html>` as clickable dots with an info popover. These labels are illustrative B-DNA vocabulary, **not derived from any sequence or engine output**.
- **Lighting**: hemisphere + ambient + 3 point lights (cyan, green, white) — no HDRI/environment map, so material metalness is capped and roughness floored to avoid the PBR material rendering near-black.
- **Animation loop**: a single `useFrame` incrementing Y-rotation when `autoRotate` is true; `OrbitControls` handles user drag/zoom (`enablePan={false}`, zoom min/max 3–10).
- **No shaders** beyond stock `MeshStandardMaterial`. No instancing, no per-nucleotide geometry, no LOD.
- Reused identically on the landing page and `/analyze` (only the `tintColor` prop differs, driven by GC% via HSL hue interpolation — RGB lerp was tried first and rejected because it desaturates through gray at ~50% GC).

---

## 9. API inventory

### Backend (`:8000`) — 27 routes, no auth, CORS-open to `localhost:3000`

| Method | Path | Purpose |
|---|---|---|
| GET | /health | Liveness |
| POST | /ingest | Parse a FASTA/FASTQ/GenBank file by **server-side path** (not multipart) |
| POST | /pam/scan | PAM scan a raw sequence |
| POST | /pam/scan-region | PAM scan a genomic region (requires registered genome) |
| POST | /index/build | Build an off-target search index |
| POST | /offtarget/search | Genome-scale off-target search |
| POST | /offtarget/score | CFD scoring of off-target candidates |
| POST | /offtarget/analyze-seed | Seed-region mismatch analysis |
| POST | /rank | Rank candidates |
| GET | /genomes, /genomes/{id} | Registered reference genome metadata |
| GET | /cache/status, POST /cache/clear | Cache introspection/management |
| GET | /tools | List of backend tool metadata (used by MIDEND's connector) |
| POST | /sequence/gc, /homopolymer, /tm, /secondary-structure, /positional-features, /dinucleotide-composition, /seed-gc, /cut-site | Individual sequence-feature tools |
| POST | /score/ontarget | On-target efficiency prediction |
| GET | /models, /models/{id}, /models/{id}/status | Model registry / runtime state |
| POST | /models/{id}/setup, /models/{id}/verify | Explicit model provisioning (never implicit) |

### MIDEND (`:8080`) — 36 routes, no auth, CORS-open to `localhost:3000`

Grouped by concern: **inputs** (`/inputs/file`, `/calibration/file`, `/inputs/{id}`), **calibration** (`/calibration/status`, `/calibration/{id}`, `/calibration/run`), **AI provider config** (`/ai/config`, `/ai/status`, `/ai/providers`, `/ai/active`, `/ai/test`), **chat** (`/ai/chat`), **backend status** (`/backend/status`, `/backend/active`), **discovery** (`/tools`, `/skills`, `/skills/{id}`, `/skills/{id}/status`), **execution** (`/skills/{id}` POST, `/executions`, `/executions/{id}`, `/executions/{id}/tools`, `/executions/{id}/tools/{call_id}`, `/executions/{id}/ai`, `/executions/{id}/stream`), **conversations** (`/conversations`, `/conversations/{id}`, `/conversations/{id}/messages`), **prompts** (`/prompts/preview`), **health** (`/health`).

### Frontend Next.js API routes (2)

| Route | Purpose |
|---|---|
| POST /api/reason | See §7a |
| POST /api/ingest | Bridges browser upload → backend `/ingest` (path-based) → locally extracts sequence text since the backend never returns it |

No undocumented/mock/unused endpoints found in the frontend. Backend/MIDEND route inventories are exhaustive per `grep` of `@app.get/post/delete`.

---

## 10. Environment variables

| Variable | Purpose | Used by | Required? | Public/Private |
|---|---|---|---|---|
| `NEXT_PUBLIC_VEYRA_BACKEND_URL` | Backend base URL for browser fetches | `src/lib/backend.ts` | No (defaults `http://localhost:8000`) | Public |
| `NEXT_PUBLIC_VEYRA_MIDEND_URL` | MIDEND base URL for browser fetches | `src/lib/midend.ts` | No (defaults `http://localhost:8080`) | Public |
| `MIDEND_AI_BASE_URL` | OpenAI-compatible provider base URL | `/api/reason`, `veyra/midend/config/ai_provider.py` | No (defaults `https://api.llm7.io/v1`) | Private |
| `MIDEND_AI_API_KEY` | Provider API key | same | Yes, for AI responses (else stub/error) | **Secret** |
| `MIDEND_AI_MODEL` | Model name | same | No (default `"default"`) | Private |
| `MIDEND_AI_TIMEOUT` | Provider request timeout (s) | midend config | No | Private |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | Fallback aliases in `/api/reason` | `/api/reason` only | No | **Secret** |
| `ANTHROPIC_API_KEY` | Second fallback provider in `/api/reason` | `/api/reason` only | No | **Secret** |
| `MIDEND_BACKEND_CONNECTOR` | `"http"` or `"mcp"` — how MIDEND reaches the backend | `veyra/midend/config/settings.py` | No (default `http`) | Private |
| `MIDEND_BACKEND_TIMEOUT`, `MIDEND_MCP_TIMEOUT` | Connector timeouts | midend settings | No | Private |
| `VEYRA_ROOT`, `VEYRA_DATA_DIR`, `VEYRA_CACHE_DIR`, `GENOME_REFERENCES_DIR`, `ECOLI_FASTA_PATH`, `GRCH38_FASTA_PATH`, `CAS_OFFINDER_BIN` | Path overrides (all optional, auto-discovered by default) | backend core | No | Private |
| `VEYRA_MODEL_ENVS_DIR`, `VEYRA_MODEL_RUNTIME_STATE_DIR` | Isolated model-runtime provisioning paths | `backend/core/model_runtime.py` | No | Private |

No secret values were found committed in source. `veyra/backend/.gitignore` and `veyra/midend/.gitignore` (added this session) explicitly exclude `.env`, `.env.local`, `*.key`, `*.pem`, `credentials.json`, `secrets.json`. `veyra/midend/.env` exists locally (not committed) and is git-ignored — verified via `git check-ignore -v`.

---

## 11. Dependency audit

### Frontend (`package.json`)
Production: `next@16.3.1`, `react@19.2.8`, `react-dom@19.2.8`, `@react-three/fiber@^9.7.0`, `@react-three/drei@^10.7.8`, `three@^0.185.1`, `lucide-react@^1.31.0`. Dev: `typescript@^5`, `tailwindcss@^4`, `@tailwindcss/postcss@^4`, `eslint@^9`, `eslint-config-next@16.3.1`, plus `@types/*`. Minimal and all in active use — no unused or suspicious packages found.

### Backend (`veyra/backend/requirements.txt`)
`biopython>=1.83,<1.84`, `numpy>=1.26`, `fastapi>=0.115,<1`, `uvicorn>=0.30,<1`, `httpx>=0.28,<1`. Notably thin — the on-target models (`rs3`, LightGBM, `azimuth`) and secondary-structure tool (ViennaRNA) are **not** in this file, meaning they're either installed separately/manually or provisioned into isolated runtimes at `data/model_envs/` (confirmed by `core/model_runtime.py`'s isolated-runtime subprocess execution path). `UNKNOWN — requires verification`: whether a fresh clone can run `predict_ontarget_efficiency(model="rule_set_3")` out of the box without manual runtime setup.

### MIDEND
No `requirements.txt`/`pyproject.toml` found in `veyra/midend/`. `UNKNOWN — requires verification`: exact pinned dependency set; presumably shares the backend's Python environment plus `fastapi`/`uvicorn`/`httpx` (all imported in code).

---

## 12. Testing

| Tier | Test files | Notes |
|---|---|---|
| Frontend | **0** | No `*.test.*`/`*.spec.*` files anywhere in `src/`. Confirmed by search. |
| Backend | 8 (`veyra/backend/tests/`) | `test_ingestion.py`, `test_interfaces.py`, `test_mcp.py`, `test_audit_regressions.py`, `test_portability.py`, `test_live_midend_verification.py`, plus fixtures/conftest |
| MIDEND | 15 (`veyra/midend/tests/`) | Notably thorough: `test_agentic_robustness.py`, `test_backend_live_correctness.py`, `test_blackbox_agent_freeze.py`, `test_calibration.py`, `test_compaction.py`, `test_exposure_control_plane.py`, `test_frontend_integration_contract.py`, `test_input_validation.py`, `test_offtarget_toxicity.py`, `test_skills.py`, `test_tool_catalog.py`, etc. |

**Critical untested path**: the entire frontend — no component tests, no route tests, no E2E. All frontend verification this session was manual (live browser interaction via Chrome DevTools MCP), not an automated suite. `npx tsc --noEmit` and `npx eslint` both pass clean as of this audit, which catches type/lint issues but not behavior regressions.

---

## 13. Build / run / deploy

| Command | Purpose | Status | Notes |
|---|---|---|---|
| `npm install` | Install frontend deps | Not re-run this audit | `package-lock.json` present |
| `npm run dev` | Frontend dev server (Turbopack) | Verified working | Port 3000 |
| `npm run build` | Production build | Not run this audit | `UNKNOWN — requires verification` |
| `npm run start` | Production server | Not run this audit | `UNKNOWN — requires verification` |
| `npm run lint` (`eslint`) | Lint | Verified clean | |
| `npx tsc --noEmit` | Typecheck | Verified clean | Not a package.json script, but works |
| `python -m uvicorn http_api.app:app --host 0.0.0.0 --port 8000` (from `veyra/backend/`) | Backend dev server | Verified working | Must run from inside `backend/` |
| `python -m uvicorn midend.http_api.app:app --host 0.0.0.0 --port 8080` (from `veyra/`) | MIDEND dev server | Verified working | Must run from `veyra/`, not `veyra/midend/` (relative imports) |
| Tests (`pytest` implied) | Backend/MIDEND test suites | Not run this audit | `UNKNOWN — requires verification` (no explicit pytest invocation recorded) |

No Docker, no CI/CD config, no deployment platform config found anywhere in the repo (confirmed by search for `Dockerfile`, `.github/workflows`, `vercel.json`, etc. — none exist). This is a local-only, three-process hackathon setup.

---

## 14. Current health

| Severity | Finding |
|---|---|
| MEDIUM | `docs/architecture.md` and `docs/scientific-assumptions.md` are stale — describe only the earlier client-only architecture, contradicting the actual (much larger) current system. Misleading for onboarding. |
| MEDIUM | `src/app/midend/MidendConsole.tsx` is dead code — `midend/page.tsx` now re-exports `ChatConsole` instead. Not deleted per this audit's no-changes constraint. |
| LOW | No frontend tests at all. |
| LOW | No `requirements.txt`/`pyproject.toml` for `veyra/midend/` — dependency set isn't pinned/documented. |
| LOW | Backend `requirements.txt` doesn't list the on-target-model dependencies (`rs3`, `azimuth`, ViennaRNA) actually used by `core/ontarget.py`/secondary-structure tooling — likely provisioned separately into isolated runtimes, but this isn't self-evident from the manifest alone. |
| INFO | Recurring operational issue (observed repeatedly this session, not a code bug): all three dev processes (backend/midend/frontend) drop between conversation turns and must be manually restarted. |
| INFO | `tsc --noEmit` and `eslint` both pass clean at time of audit. No console errors or failed network requests observed during live manual testing of `/`, `/analyze` (paste + file upload), `/raw`, `/docs`, `/midend`, `/chat` (session start, file attach, calibration attach). |

No CRITICAL or HIGH severity issues found.

---

## 15. Scientific validity audit

| Claim | Implemented? | Evidence in code | Scientifically demonstrated? | Mock/Prototype? | Safe to say in demo? |
|---|---|---|---|---|---|
| PAM detection (SpCas9 NGG) | Yes, both engines | `genomic-engine/index.ts`, `mcp/tools/pam_scan.py` | Yes — exact pattern matching, not probabilistic | No | Yes |
| GC content | Yes, both engines | Same files | Yes — arithmetic | No | Yes |
| Off-target detection (client heuristic) | Yes | `genomic-engine/index.ts` | No — custom penalty formula, not a published model | Heuristic | Only with the "input-sequence-only, illustrative" caveat, which the UI already states |
| Off-target detection (backend, genome-scale) | Yes, when a genome is registered | `mcp/tools/offtarget_search.py` (Cas-OFFinder-backed) | Partially — Cas-OFFinder is a real, published tool | No | Yes, with scope caveat (requires registered genome) |
| CFD off-target scoring | Yes | `mcp/tools/score_offtargets.py` | Yes — real published CFD algorithm (Doench 2016) with real CRISPOR pickle data; the tool's own output explicitly disclaims "NOT experimentally validated by VEYRA" | No | Yes — "we use the real CFD algorithm; VEYRA itself hasn't run wet-lab validation" |
| On-target efficiency (Doench 2014 / RS2 / RS3) | Yes, with fallback chain | `core/ontarget.py` | Yes — real published models | No, but RS2/RS3 availability depends on runtime provisioning (`UNKNOWN` whether verified out-of-box) | Yes, with the caveat that model availability/fallback is reported transparently |
| Model calibration against user data | Yes | `midend/skills/model_calibration.py`, backend feature tools | Deterministic least-squares fit — real math, but the *dataset* quality is user-supplied and unverified | No | Yes — frame as "fits to whatever data you give it," not as pre-validated |
| Chromatin/epigenetic context | No | Not present anywhere in codebase | N/A | Not implemented | Do not claim |
| Chromosomal rearrangement / long-range genomic context | No | Not present | N/A | Not implemented | Do not claim |
| Epistasis / gene interaction modeling | No | Not present | N/A | Not implemented | Do not claim |
| AI reasoning (`/chat`) | Yes | `control_plane.py` | The AI's *text* is not scientifically validated (it's an LLM interpreting real numbers) — the underlying numbers it cites are real tool output | Interpretation layer, not computation | Yes — "the AI never invents a number, it explains ones we computed," which is enforced by the system prompt and by every skill delegating math to the backend |
| Clinical/diagnostic validity | No, and explicitly disclaimed in UI copy (footer: "Research prototype. Not for clinical or diagnostic use.") | UI text | N/A | N/A | Never claim clinical validity |

---

## 16. Hackathon demo audit

### Recommended demo flow

**Step 1 — Landing page.** Show the 3D DNA model (drag to rotate), the deterministic-core framing, and the "Why off-target evidence matters" section (real cited cases — sickle-cell trial, T-cell cancer trial, India's regulatory gap). *Real*: the 3D model, the copy, the citations. *Simulated*: nothing — this page makes no computational claims.

**Step 2 — `/chat`.** Start a session, ask "Find candidate SpCas9 cutting sites in [sequence]" or attach a FASTA file. Watch the live tool-call activity feed (`pam_scan`, `compute_gc_content`, `compute_cut_site`, etc., each with real HTTP timing) resolve into a structured candidate table, then the AI's plain-language summary. This is the strongest wow moment — real tool orchestration, visibly transparent (every claim traceable to a named tool call), not a black box.

**Step 3 — `/analyze`.** Paste or upload a sequence, show instant client-side candidate discovery, then real backend-confirmed scores (CFD, Tm, homopolymer) layering in, plus the 3D model's GC-driven tint.

**Step 4 — `/raw`.** For technical judges: show that every number in the app traces to a real, directly-callable backend endpoint — no hidden magic.

### What could embarrass in a live demo
- All three services must be running and warm — they've dropped between turns repeatedly this session; start them well before judges arrive and verify all three `/health` endpoints.
- Rule Set 2/3 on-target models depend on runtime provisioning that hasn't been verified fresh-clone (§11) — if asked to demo model selection live, `doench_2014` is the guaranteed-available fallback; don't promise RS2/RS3 will resolve without checking `GET /models` first.
- The AI provider (`MIDEND_AI_*`) must have a valid, funded API key — if it's exhausted/misconfigured, `/chat` falls through to error text, not a graceful mock.
- Don't claim per-nucleotide 3D recoloring — the asset structurally can't do it (§8); whole-model tint is real and demoable, per-rung is not.

---

## 17. Project strengths

**Technical**: genuinely three-tier separation with each tier enforced structurally (MIDEND has zero scoring math; the raw console proves the backend contract 1:1). Real, correctly-fallback-chained multi-model on-target prediction. Real CFD implementation using actual published CRISPOR resources, not a reimplementation-by-guess.

**Product**: three distinct, honestly-differentiated ways to use the same underlying engine (raw/deterministic, guided/analyze, conversational/chat) rather than one monolithic flow.

**UX**: live tool-call activity feed makes AI orchestration legible rather than opaque; consistent "Engine" vs "AI" evidence tagging throughout every surface.

**Scientific**: unusually disciplined about labeling what's real vs. heuristic vs. AI-generated, both in code comments and UI copy (e.g., the CFD tool's own metadata self-disclaims validation status).

**Hackathon differentiation**: the MIDEND layer's mandatory-tool-use system prompt plus 15-file test suite (`test_agentic_robustness.py`, `test_blackbox_agent_freeze.py`) is a level of AI-reliability engineering well beyond typical hackathon "call an LLM" integrations.

## 18. Project weaknesses

Being direct, as requested:

- **Zero frontend tests.** Every UI verification this session was manual browser interaction, not an automated regression net.
- **Two committed architecture docs are stale** and actively misleading about system scope.
- **Client-side heuristic engine's off-target scoring is not a validated model** — it's a bespoke penalty formula. Fine as a fast instant-feedback layer, but must never be presented as equivalent to the backend's real CFD scoring.
- **On-target model availability (RS2/RS3) is environment-dependent** and not verified to work from a fresh clone — a real risk for reproducibility/demo reliability.
- **No auth, no rate limiting, no persistence** anywhere — fine for a local hackathon demo, would need real work before any shared/hosted deployment.
- **Operational fragility**: three separate long-running processes with no supervisor/orchestration (no Docker Compose, no process manager) — they've dropped repeatedly this session and require manual restart.
- **Dead code** (`MidendConsole.tsx`) left in the tree from an iteration that got superseded.
- **AI reliability depends entirely on an external provider** (`MIDEND_AI_*`) with no offline/local fallback beyond a deterministic stub in the `/analyze`-only reasoning path (the `/chat` path has no equivalent stub — a provider outage degrades that surface hard).

---

## 19. Likely judge questions

**Scientific**
- Q: Is the off-target scoring clinically validated? A: No. The backend uses the real, published CFD algorithm (Doench 2016) with actual CRISPOR resource data, but VEYRA itself has not run any wet-lab validation — this is stated in the tool's own output metadata. Do not claim clinical or experimental validation.
- Q: Do you account for chromatin accessibility? A: No, not implemented anywhere in the codebase. Do not claim this exists.

**Technical**
- Q: Is the AI able to invent scores? A: Structurally no — MIDEND's system prompt mandates tool use before any biological claim, every skill delegates math to the backend, and the frontend visually separates "Engine" evidence from "AI" text in every view.
- Q: What happens if the backend is down? A: `/analyze`'s client heuristic still works standalone; `/chat`/`/raw` degrade to explicit error states, not silent fallback numbers.

**AI**
- Q: What model do you use? A: Configurable via `MIDEND_AI_*` env vars, OpenAI-Chat-Completions-compatible; default provider is `https://api.llm7.io/v1`. Do not claim a specific model name unless you've checked the live `.env` — it's operator-configured, not hardcoded.

**CRISPR**
- Q: Which on-target model is actually running right now? A: Check `GET /models` — `auto` mode picks the highest-priority verified model (RS3 > RS2 > Doench 2014) and reports its full fallback chain; don't assume RS3 is active without checking.

**Architecture**
- Q: Why three services instead of one? A: Deliberate separation of concerns — deterministic computation, AI orchestration, and presentation are independently testable/replaceable; MIDEND's 15-file test suite specifically guards the orchestration boundary.

**Scalability**
- Q: Does this scale? A: Not demonstrated — no persistence, no auth, no load testing, single-process services. Do not claim production readiness.

**Validation**
- Q: How do you know the backend math is correct? A: 8 backend test files plus reuse of the exact same `core/` functions across CLI, HTTP, and MCP interfaces (no duplicated logic to drift). Frontend has no automated tests — an honest gap.

**Security**
- Q: How are secrets handled? A: `.env`/`.env.local`/key files are git-ignored at both root and per-service level; no secrets found in committed source this audit. No auth on any endpoint — acceptable for a local demo, not for any shared deployment.

**Clinical safety**
- Q: Could this be used for actual gene therapy design? A: No — explicitly labeled "research prototype, not for clinical or diagnostic use" in the UI footer, and no clinical-grade validation exists anywhere in the pipeline. Never claim otherwise.

**Product**
- Q: What's the actual end-to-end user value? A: Paste/upload a sequence → get ranked guide candidates with transparently-sourced scores → ask the AI to explain the risk in plain language, every claim traceable to a specific tool call.

---

## 20. Final architecture summary

```text
VEYRA
│
├── Frontend (Next.js 16 / React 19 / TypeScript, port 3000)
│   ├── Landing (/)                    — hero, 3D DNA, real-world case citations
│   ├── Analyze (/analyze)             — paste/upload → client heuristic → backend scoring
│   ├── Chat (/chat, alias /midend)    — AI-orchestrated conversational analysis (primary UX)
│   ├── Raw (/raw)                     — direct 1:1 backend endpoint console
│   └── Docs (/docs)                   — static in-app user guide
│
├── 3D Genomic Visualization (React Three Fiber, single GLB asset, whole-model tint only)
│
├── Frontend API routes (Next.js server)
│   ├── /api/ingest   — browser upload → backend path-based /ingest bridge
│   └── /api/reason   — simple one-shot AI explanation for /analyze
│
├── MIDEND (FastAPI/Python, port 8080)
│   ├── control_plane.py   — conversation/execution state, PromptBuilder, skill dispatch
│   ├── 3 skills            — spcas9_gene_cutting, offtarget_toxicity_risk, model_calibration
│   └── connectors/         — HTTP or MCP to reach the backend; never computes biology itself
│
├── Deterministic Backend (FastAPI/Python, port 8000)
│   ├── mcp/tools/          — 18 real algorithm implementations (PAM, CFD, Doench models, etc.)
│   ├── parsers/             — FASTA/FASTQ/GenBank (Biopython)
│   └── references/          — real CRISPOR CFD resource files
│
├── Data
│   ├── public/models/dna.glb          — shared 3D asset
│   ├── veyra/data/                    — reference genomes, model runtime envs
│   └── veyra/cache/                   — SQLite cache, model runtime state
│
└── External Services
    └── One configurable OpenAI-compatible LLM provider (MIDEND_AI_* env vars)
```
