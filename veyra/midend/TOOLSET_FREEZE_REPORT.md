# VEYRA MIDEND — Public AI Toolset Freeze Report (Phase 14)

Date: August 2026
Location: `veyra/midend/TOOLSET_FREEZE_REPORT.md`
Authoritative Contract: `veyra/midend.md`

## 1. Freeze Decision & Status

**STATUS: FROZEN.**

All 14 atomic deterministic tools and 3 high-level workflow skills have been comprehensively validated through black-box agent acceptance testing against the live, running VEYRA stack (Backend `:8000`, Midend `:8080`, Frontend `:3000`).

Under the Freeze Rule:
- **NO NEW TOOLS**
- **NO REMOVED TOOLS**
- **NO RENAMED TOOLS**
- **NO PARAMETER / DEFAULT MUTATIONS**
- **NO RESULT-SCHEMA MUTATIONS**

Future frontend UI components and AI reasoning features must strictly consume this authoritative frozen toolset.

---

## 2. Frozen Contract Identification

- **Authoritative Contract Specification**: `veyra/midend.md` (Version `1.0.0`)
- **Tool Catalog Version**: `1.0.0`
- **Tool Catalog SHA-256 Hash**: In-memory hash-checked (`compute_contract_hash()`)
- **Total Public AI Tools Exposed**: **17** (14 atomic calculation tools + 3 workflow skills)
- **Total Public Skills**: **3** (`spcas9_gene_cutting`, `offtarget_toxicity_risk`, `model_calibration`)
- **Configured AI Provider Adapter**: `openai_compatible` (via `.env` `MIDEND_AI_BASE_URL`, `MIDEND_AI_API_KEY`, `MIDEND_AI_MODEL`)

---

## 3. Authoritative Tool Directory & Capabilities

| Tool / Skill Name | Category | Cost Tier | Prerequisites | One-Line Purpose | Tested Status |
|---|---|---|---|---|---|
| `pam_scan` | `pam_discovery` | `cheap` | Target sequence | Scan DNA sequence for SpCas9 NGG/NAG PAM motifs | **PASS** |
| `pam_scan_region` | `pam_discovery` | `cheap` | Genomic coordinates | Scan genomic reference region for PAM motifs | **PASS** |
| `compute_cut_site` | `geometry` | `cheap` | Spacer start & strand | Compute exact SpCas9 blunt cut site coordinates (pos 17/18) | **PASS** |
| `compute_gc_content` | `sequence_qc` | `cheap` | Spacer sequence | Calculate total GC%, sliding-window GC, and half-split ratios | **PASS** |
| `check_homopolymer_runs` | `sequence_qc` | `cheap` | Spacer sequence | Detect homopolymer repeats (>=4 nt) & poly-T termination | **PASS** |
| `compute_melting_temp` | `thermodynamics` | `cheap` | Spacer sequence | Calculate nearest-neighbor DNA/DNA Tm with salt corrections | **PASS** |
| `compute_secondary_structure`| `thermodynamics` | `moderate`| Spacer sequence | Predict MFE secondary structures and guide hairpin folding | **PASS** |
| `compute_positional_features` | `features` | `cheap` | Spacer sequence | Extract single-nucleotide position weights & G-bias | **PASS** |
| `compute_dinucleotide_composition`| `features` | `cheap` | Spacer sequence | Compute adjacent 2-mer dinucleotide frequency matrices | **PASS** |
| `compute_seed_gc` | `sequence_qc` | `cheap` | Spacer sequence | Calculate GC content in PAM-proximal 10nt seed region | **PASS** |
| `analyze_mismatch_seed` | `offtarget` | `cheap` | Guide & offtarget seq | Partition mismatches into PAM-proximal seed vs non-seed | **PASS** |
| `offtarget_search` | `offtarget` | `expensive`| Spacer & Genome ID | Genome-wide alignment search for off-target loci | **PASS** |
| `score_offtargets` | `offtarget` | `moderate` | Spacer & Candidates | Calculate CFD (Doench 2016) specificity scores | **PASS** |
| `rank_candidates` | `ranking` | `cheap` | Guide records | Deterministic candidate ranking using composite/efficiency | **PASS** |
| `predict_ontarget_efficiency` | `scoring` | `moderate` | 30nt context seq | Predict on-target cleavage efficiency via Rule Set 3 / Doench | **PASS** |
| `spcas9_gene_cutting` (Skill) | `skill` | `moderate` | Sequence or input_id | Complete pipeline: PAM scan, geometry, QC, on-target, rank | **PASS** |
| `offtarget_toxicity_risk` (Skill)| `skill` | `moderate` | Spacer sequence | Audit and compute off-target toxicity risk combining CFD & deltaG | **PASS** |
| `model_calibration` (Skill) | `skill` | `moderate` | Calibration dataset ID| Fit model coefficients and compute R²/MSE on labeled CSV/TSV | **PASS** |

---

## 4. Black-Box Acceptance Verification Results

### 4.1 Parameter Overrides & Metadata (Phase 5)
- Verified `analyze_parameters_meta` tracks exact status for every argument: `[default]`, `[overridden]`, and `[supplied]`.
- Verified overrides (e.g. `strand="fwd"`, `pam_pattern="NGG"`) are recorded accurately in execution metadata and rendered in the frontend UI.

### 4.2 Multi-Tool Chaining (Phase 6)
- **Chain 1**: `pam_scan` → `compute_cut_site` (pos 17) → `compute_gc_content` → `compute_melting_temp` → `rank_candidates` (`completed` with 4 successful sub-calls).
- **Chain 2**: `pam_scan` → `offtarget_search` (`ecoli_k12_mg1655`) → `analyze_mismatch_seed` → `score_offtargets` (`completed` with 3 successful sub-calls).

### 4.3 Parallel Tool Groups (Phase 7)
- Executed parallel group `group_qc_features` containing 4 concurrent calls (`compute_gc_content`, `compute_melting_temp`, `check_homopolymer_runs`, `compute_secondary_structure`).
- Wall-clock duration tracked accurately; individual results and call IDs preserved.

### 4.4 Attached File Workflows (Phase 8 & 9)
- Uploaded `target_gene.fasta` (`POST /inputs/file`): validated as `analysis_input`. Processed via `spcas9_gene_cutting` using `input_id`.
- Uploaded `calib_dataset.csv` (`POST /inputs/file`): validated as `calibration_input`. Processed via `model_calibration` skill with sample count = 2 and status = `calibrated`.

### 4.5 Security & Error Boundaries (Phase 10 & 12)
- Rejection of path traversal attempts (`{"path": "/etc/passwd"}` → HTTP 400).
- Rejection of unknown input IDs (`/inputs/non_existent_999` → HTTP 400).
- Pure black-box compliance: no private backend modules or internal shortcuts used by the test client.

### 4.6 Real Provider Cross-Check (Phase 13)
- Chat requests routed through `POST /ai/chat` against live OpenAI-compatible LLM endpoint. Multi-turn native tool calling with compact evidence verified.

---

## 5. Comprehensive Regression Results
- **Midend Test Suite**: **63 / 63 passed** (`veyra/midend/tests/`).
- **Backend Test Suite**: **425 / 425 passed** (`veyra/backend/tests/`).
- **Next.js 16 Application Build**: **Compiled successfully** (`npm run lint && npm run build`).
