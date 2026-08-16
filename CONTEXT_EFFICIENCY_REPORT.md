# VEYRA MIDEND — Context Efficiency & Layered Tool Discovery Report

Date: August 2026
Location: `CONTEXT_EFFICIENCY_REPORT.md`
Authoritative Contract: `veyra/midend.md`

## 1. Executive Summary

This refactoring implements an in-memory, cached, layered tool discovery and evidence compaction architecture for the VEYRA MIDEND orchestration engine. The entire 3,800+ line authoritative specification (`midend.md`) is no longer dumped into LLM prompts. Instead, context usage is bounded and optimized across every dimension:

1. **Cached Machine Catalog**: Single source of truth derived from live tool definitions with cache invalidation via SHA-256 contract checksum.
2. **Compact Global Directory**: A lightweight text directory of all 17 tools (~722 tokens) included in the system prompt for complete model discovery.
3. **Skill- & Task-Aware Native Tool Provisioning**: The model is lazily passed only the native OpenAI-compatible tool schemas relevant to the active skill, task intent, and attached input class (reducing schema overhead by 20% to 82%).
4. **Deep Evidence Compaction**: Multi-hundred row results (e.g., 350+ off-target loci, 100+ PAM sites) are compacted into high-signal statistical summaries + top 5 representative items for LLM reasoning (reducing tool message token weight by **92.6% – 98.0%**), while full tabular datasets are preserved behind execution/call IDs for UI display.
5. **Structured Session Compaction**: Recent dialogue turns (last 4 turns) are preserved verbatim, while older conversation history is condensed into an authoritative structured session summary referencing execution IDs and input IDs.
6. **Input Context Optimization**: Uploaded genomic files and calibration datasets are referenced by `input_id` and concise structural metadata rather than multi-kilobyte raw sequence string dumps.

---

## 2. Architecture Before vs. After

### Before
```
[User Request] + [Raw FASTA/Sequence Slices (up to 600+ chars)]
       │
       ▼
[System Instructions (prose)]
       │
       ▼
[17 Full Tool JSON Schemas (~2,955 tokens) injected unconditionally]
       │
       ▼
[Linear History Accumulation (unbounded)]
       │
       ▼
[Uncompacted Raw Tool Output Dumps (10,000+ tokens for large alignments)]
```

### After (Layered Architecture)
```
[User Request] + [Compact Input Metadata (input_id, format, record count, 200bp preview)]
       │
       ▼
[System Prompt with Compact Capability Directory (~722 tokens, all 17 tools)]
       │
       ▼
[Active Schema Selector: Skill / Task / Input-Aware Lazy Full Schemas (3 to 14 tools)]
       │
       ▼
[Conversation Compactor: Structured Session Summary + Verbatim Recent 4 Turns]
       │
       ▼
[Deterministic Backend Execution via HTTP/MCP]
       │
       ▼
[Evidence Compactor: Summary + Top-5 Rows for LLM (Full Results Retained for UI)]
```

---

## 3. Tool Catalog & Lazy Schema Design

- **Tool Catalog (`veyra/midend/ai/tool_catalog.py`)**:
  - Derived from `NATIVE_TOOLS_DEFINITIONS`, `AUTHORITATIVE_DEFAULTS`, and `PARAMETER_UNITS`.
  - Computes `contract_hash` across `midend.md` and tool defaults for process-local caching.
  - Exposes category classifications (`pam_discovery`, `geometry`, `sequence_qc`, `thermodynamics`, `features`, `offtarget`, `scoring`, `ranking`, `skill`) and cost tiers (`cheap`, `moderate`, `expensive`).

- **Compact Tool Directory**:
  ```
  AVAILABLE VEYRA CAPABILITY DIRECTORY:
  - pam_scan [pam_discovery, cheap cost | Prereq: sequence]: Scan target DNA sequence for SpCas9 NGG/NAG PAM sites and extract protospacers
  - compute_cut_site [geometry, cheap cost | Prereq: spacer_start, strand]: Compute exact SpCas9 blunt cut site coordinates
  - compute_gc_content [sequence_qc, cheap cost | Prereq: sequence]: Calculate total GC%, sliding-window GC profile, and half-split ratios
  - check_homopolymer_runs [sequence_qc, cheap cost | Prereq: sequence]: Detect homopolymer repeats (>=4 nt) and flag strict poly-T termination
  - compute_melting_temp [thermodynamics, cheap cost | Prereq: sequence]: Calculate nearest-neighbor DNA/DNA melting temperature (Tm)
  - compute_secondary_structure [thermodynamics, moderate cost | Prereq: sequence]: Predict MFE secondary structures and guide hairpin folding
  - compute_positional_features [features, cheap cost | Prereq: sequence]: Extract single-nucleotide position weights and G-bias
  - compute_dinucleotide_composition [features, cheap cost | Prereq: sequence]: Compute adjacent 2-mer dinucleotide frequency matrices
  - compute_seed_gc [sequence_qc, cheap cost | Prereq: sequence]: Compute GC content in critical 10nt PAM-proximal seed region
  - analyze_mismatch_seed [offtarget, cheap cost | Prereq: guide_sequence, offtarget_sequence]: Evaluate mismatch counts in seed vs non-seed
  - offtarget_search [offtarget, expensive cost | Prereq: spacer_sequence, genome_id]: Perform genome-wide alignment search for off-target loci
  - score_offtargets [offtarget, moderate cost | Prereq: spacer_sequence, candidates]: Calculate CFD specificity scores for off-target hits
  - predict_ontarget_efficiency [scoring, moderate cost | Prereq: context_sequence]: Predict on-target cleavage efficiency using Rule Set 3 / Doench 2014
  - rank_candidates [ranking, cheap cost | Prereq: guides]: Rank candidate guides deterministically using composite score
  - spcas9_gene_cutting [skill, moderate cost | Prereq: sequence_or_input_id]: Comprehensive pipeline skill
  - offtarget_toxicity_risk [skill, moderate cost | Prereq: spacer_sequence]: Audit and compute off-target toxicity risk combining CFD and thermodynamics
  - model_calibration [skill, moderate cost | Prereq: calibration_input_id]: Experimental model calibration skill on validated CSV/TSV
  ```

- **Dynamic Lazy Loading**:
  - If a model invokes a tool not in the active subset, the control plane dynamically expands `active_native_tools` and executes the backend tool seamlessly.

---

## 4. Quantitative Context & Token Reductions

| Query / Context Component | Unoptimized Tokens (Before) | Optimized Tokens (After) | Token Reduction (%) |
|---|---|---|---|
| **Calibration Task Tool Schemas** | 2,955 tokens | 525 tokens | **-82.2%** |
| **Off-target Task Tool Schemas** | 2,955 tokens | 653 tokens | **-77.9%** |
| **SpCas9 Guide Design Schemas** | 2,955 tokens | 2,362 tokens | **-20.1%** |
| **100-site PAM Evidence** | 2,573 tokens | 190 tokens | **-92.6%** |
| **350-hit Off-target Evidence** | 10,227 tokens | 206 tokens | **-98.0%** |
| **16-Turn Conversation History** | 411 tokens | 192 tokens | **-53.3%** |
| **FASTA Attachment Prompt Text** | ~2,500 tokens (raw buffer) | ~95 tokens (metadata + preview) | **-96.2%** |

---

## 5. Verification & Regression Results

- **Midend Integration & Unit Tests**: `52 / 52 passed` (100%).
- **Backend Deterministic Biology Tests**: `425 / 425 passed` (100%).
- **Frontend Quality Assurance**: `npm run lint` (0 errors), `npm run build` (Next.js 16 build succeeded).
- **Multi-turn Native Tool Calling**: Fully verified with parameter validation (`[default]` vs `[overridden]`), deterministic evidence feedback, and structured conversation summarization.

---

## 6. Remaining Limitations & Boundaries
- All biological calculations remain strictly in the frozen deterministic backend layer; no biological inference or math is delegated to LLMs.
- File uploads remain bounded at 50 MiB with strict UTF-8 / tabular schema validation.
