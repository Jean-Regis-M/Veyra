# VEYRA — Genomic Intelligence

An interpretable CRISPR/Cas9 guide-RNA design and off-target risk-assessment platform. Every score traces to a real, deterministic computation; an AI layer explains the results but never invents them.

---

## Overview

VEYRA scores CRISPR guide-RNA candidates against a target DNA sequence — PAM discovery, on-target efficiency, off-target risk — and presents the results through an interactive 3D locus view and a conversational AI assistant. It's built as three independent services: a deterministic scientific backend, an AI-orchestration layer that calls that backend's real tools, and a Next.js frontend with three ways to use the engine (a guided analysis flow, a conversational chat, and a raw API console).

Research prototype. Not for clinical or diagnostic use.

---

## Problem

Off-target CRISPR risk is real and documented — not hypothetical. Published trials have detected unintended genomic events in edited patient cells (see [References](#references)), yet the tools researchers use to *predict* that risk typically hand back a single opaque probability from a short sequence window, with no way to see what algorithm produced it or why. When something needs scrutiny — a detected translocation, an unexpected off-target hit — there's often no trail back to the underlying computation.

## Solution

VEYRA scores the *whole* provided locus, not a 20 bp window, and keeps every number traceable:

- **Deterministic core** — PAM search, GC content, melting temperature, homopolymer runs, secondary structure, CFD off-target scoring (real CRISPOR data), and multi-model on-target prediction (Doench 2014 / Rule Set 2 / Rule Set 3) with a transparent fallback chain. Same input always produces the same output.
- **AI reasoning, not AI computation** — the AI layer explains and contextualizes deterministic results; it never fabricates a score. Every AI-generated claim in the UI is either traced to a specific tool call or clearly labeled as interpretation.
- **Interactive visualization** — a real-time 3D DNA structure and a live tool-call activity feed, so the AI's reasoning is auditable rather than a black box.

---

## Tech stack & architecture

VEYRA runs as three independently deployable services with no shared database:

| Tier | Component | Technology | Default port |
|---|---|---|---|
| **Frontend** | Web UI | Next.js 16, React 19, TypeScript, Tailwind CSS v4, React Three Fiber / three.js | `localhost:3000` |
| **MIDEND** | AI orchestration | FastAPI (Python), tool-calling control plane, OpenAI-compatible LLM provider | `localhost:8080` |
| **Backend** | Deterministic engine | FastAPI (Python), Biopython, CRISPOR CFD resources, Cas-OFFinder | `localhost:8000` |

MIDEND never computes biology itself — it calls the backend's real HTTP tools and has an LLM interpret the results. Full architecture detail, data-flow diagrams, and an API inventory: [`docs/ARCHITECTURE_ACTUAL.md`](docs/ARCHITECTURE_ACTUAL.md) and [`docs/PROJECT_HANDOFF.md`](docs/PROJECT_HANDOFF.md).

### Running locally

Each service runs in its own terminal.

**Backend** (from `veyra/backend/`):
```bash
cd veyra/backend
python -m uvicorn http_api.app:app --host 0.0.0.0 --port 8000
```
Health check: `curl http://localhost:8000/health`

**MIDEND** (from `veyra/` — its relative imports require this):
```bash
cd veyra
python -m uvicorn midend.http_api.app:app --host 0.0.0.0 --port 8080
```
Health check: `curl http://localhost:8080/health`

**Frontend**:
```bash
npm install
npm run dev
```
Then open:
- [`/`](http://localhost:3000) — landing page
- [`/analyze`](http://localhost:3000/analyze) — paste or upload a sequence for ranked guide candidates
- [`/chat`](http://localhost:3000/chat) — conversational, tool-orchestrated analysis
- [`/raw`](http://localhost:3000/raw) — direct 1:1 access to every backend endpoint

### Tests

```bash
# Backend
cd veyra/backend && pytest tests/ -v

# MIDEND (from veyra/)
cd veyra && pytest midend/tests/ -v

# Frontend — type-check and lint
npm run lint
npx tsc --noEmit
```

Frontend currently has no automated test suite (see [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md)).

### Input classes

- **`analysis_input`** — FASTA, FASTQ, GenBank, or a raw DNA string, for standard guide-RNA analysis.
- **`calibration_input`** — an optional labeled CSV/TSV dataset for fitting model coefficients against experimental data. Calibration is always optional; ordinary analysis never requires it.

---

## References

Scientific methods and resources VEYRA's deterministic engine is built on:

- Doench, J.G. et al. (2016). *Optimized sgRNA design to maximize activity and minimize off-target effects of CRISPR-Cas9.* — CFD off-target scoring.
- Doench, J.G. et al. (2014). *Rational design of highly active sgRNAs for CRISPR-Cas9–mediated gene inactivation.* — on-target efficiency (fallback model).
- Doench, J.G. et al. (2021) / Rule Set 3 — on-target efficiency (primary model when available).
- Bae, S. et al. — Cas-OFFinder, used for genome-scale off-target search.
- CRISPOR (Haeussler, M. et al.) — source of the CFD scoring resource data.
- Cock, P.J.A. et al. (2009). *Biopython: freely available Python tools for computational molecular biology and bioinformatics.*

Real-world case studies referenced on the landing page (see the app for full citations and context):

- New England Journal of Medicine — first-in-human CRISPR-Cas9 sickle-cell trial.
- PubMed Central (PMC) / Nature — first-in-human CRISPR-Cas9 T-cell cancer trial.
- ICMR/DBT guidelines; the ART Act — India's current gene-editing regulatory framework.

### Further documentation

- [`docs/PROJECT_HANDOFF.md`](docs/PROJECT_HANDOFF.md) — full technical audit: architecture, API inventory, dependencies, testing, known limitations.
- [`docs/ARCHITECTURE_ACTUAL.md`](docs/ARCHITECTURE_ACTUAL.md) — system diagrams and data flow.
- [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) — what's real, what's heuristic, what's not implemented.
- [`docs/scientific-assumptions.md`](docs/scientific-assumptions.md) — deterministic-engine scope and simplifications.
