# VEYRA — Platform Documentation & User Guide

Welcome to **VEYRA**, an interpretable, deterministic CRISPR/Cas9 guide-RNA design, off-target risk assessment, and empirical calibration platform.

---

## 1. System Architecture

VEYRA operates across three cleanly isolated, evidence-grounded layers:

| Tier | Component | Technology | Role |
|---|---|---|---|
| **Frontend** | Interactive Web UI | Next.js 16, React 19, Tailwind CSS | 3D DNA model, linear locus visualization, candidate ranking, file attachment, and AI chat co-pilot. |
| **Midend** | Orchestration & AI | FastAPI (Python 3.12), SSE stream | Request boundary validation, SSE execution streaming, skill orchestration, and grounded AI reasoning. |
| **Backend** | Deterministic Core | BWA, Cas-OFFinder, ViennaRNA, Biopython | PAM discovery, canonical cut-site geometry, sequence thermodynamics, CFD scoring, and off-target search. |

---

## 2. Deterministic Core Pipeline

VEYRA never invents scores or hallucinations. All candidate metrics originate from deterministic tools:

1. **PAM Scanning**: Scans for SpCas9 `NGG` motifs across forward (`+`) and reverse (`-`) strands and extracts 20 nt protospacers.
2. **Cleavage Geometry**: Identifies the canonical SpCas9 double-strand break (DSB) relative cut-site between spacer positions 17 and 18 (3 bp upstream of the PAM).
3. **Sequence Feature Profiling**:
   - GC content (optimal 40%–65%)
   - Melting temperature ($T_m$) via nearest-neighbor thermodynamics
   - Secondary structure minimum free energy (MFE) via ViennaRNA folding
   - Homopolymer run detection (poly-T and poly-G filters)
   - Position-20 base bias (favored G, disfavored T)
4. **Off-Target Specificity & CFD Scoring**:
   - Genome-wide and regional mismatch searches via BWA and Cas-OFFinder.
   - Seed-weighted mismatch penalty matrix (Cutting Frequency Determination / Doench et al. 2016).
   - Bulge-aware gap analysis.
5. **Multi-Objective Composite Ranking**:
   - Transparent aggregation of on-target efficacy and off-target specificity.

---

## 3. Input Classes & Calibration Model

VEYRA supports two strictly independent input classes:

### Analysis Input (`analysis_input`)
- **Formats**: FASTA (`.fa`, `.fasta`), FASTQ (`.fq`, `.fastq`), GenBank (`.gb`, `.genbank`), or raw DNA strings.
- **Purpose**: Target sequence for guide discovery and off-target analysis.

### Calibration Input (`calibration_input`)
- **Formats**: CSV (`.csv`), TSV (`.tsv`, `.tab`).
- **Purpose**: Optional experimental labeled dataset (e.g. GUIDE-seq read counts) used for empirical parameter fitting.
- **CRITICAL RULE**: `calibration_input` is strictly **OPTIONAL**. Normal guide-RNA analysis workflows never require calibration datasets.

### Calibration Status Lifecycle

```
[not_provided] ──> [unavailable]
       │
       ├──> [uncalibrated] (prototype model)
       │
       ├──> [user_supplied] (explicit manual weights)
       │
       └──> [calibrated] (fitted on experimental CSV/TSV with R², MSE metrics)
```

---

## 4. Grounded AI Co-Pilot & Evidence Rules

- **Deterministic First**: The AI co-pilot contextualizes and explains deterministic backend evidence; it does not replace backend calculations.
- **Literature Grounding**: Biological interpretations are grounded in established peer-reviewed literature.
- **Zero Hallucination**: Missing evidence remains `null` / `unavailable` and is never substituted with zero or synthetic guesses.
- **Privacy & Security**: Internal reasoning tokens, prompt templates, and API keys are isolated and never rendered in user-facing views.

---

## 5. API Reference Summary

### Ingestion & Inputs
- `POST /inputs/file`: Validates and registers analysis or calibration files.
- `POST /calibration/file`: Dedicated multipart upload for calibration datasets.
- `GET /inputs/{input_id}`: Validates stored input metadata.

### Skills & Orchestration
- `GET /skills`: Discovers available skills (`spcas9_gene_cutting`, `offtarget_toxicity_risk`, `model_calibration`).
- `POST /skills/{skill_id}`: Launches asynchronous skill execution.
- `GET /executions/{id}/stream`: Real-time Server-Sent Events (SSE) stream.

### AI & Chat
- `POST /ai/chat`: Launches conversation-aware AI execution with tool evidence injection.
- `POST /conversations`: Creates and manages conversation threads.
