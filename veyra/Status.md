# VEYRA Project Status

## Verification Metadata

- **Verification Date:** 2026-08-15
- **Workspace:** `/home/hrirake/Desktop/hck15/veyra/backend`
- **Python Version:** 3.12.3
- **Test Framework:** pytest 9.1.1
- **Test Command:** `python -m pytest tests/ -v`
- **Reference Environment:** `refrences.local/` is read-only reference data
- **Test Genome:** E. coli K-12 MG1655 (GCF_000005845.2, 4.6 Mbp) — downloaded, indexed, registered
- **CFD Resources:** CRISPOR CFD (Doench et al. 2016) — copied to `data/resources/crispor_cfd/`
- **Biopython:** 1.83 — MeltingTemp module used for Tm calculations
- **ViennaRNA:** 2.7.2 — Python bindings used for secondary structure / MFE calculations
- **Cas-OFFinder:** 3.0.0 — Built from source, CPU-only via POCL (AMD Ryzen 5 5600G)

## Overall Status Table

| Area | Status | Evidence | Tests | Known caveats |
|------|--------|----------|-------|---------------|
| Ingestion | COMPLETE | 60 tests pass | 60/60 | GenBank length warning |
| PAM Scanning | COMPLETE | 13 tests pass | 13/13 | None |
| MCP Tools | COMPLETE | 134 tests pass | 134/134 | 6 skipped (fixture deps) |
| Interface Parity | COMPLETE | 49 tests pass | 49/49 | None |
| CLI | COMPLETE | Verified | - | Legacy CLI preserved |
| HTTP API | COMPLETE | 15 endpoints verified | - | Deprecation warning |
| Python API | COMPLETE | 16 functions verified | - | None |
| Off-target Pipeline | COMPLETE | E. coli E2E verified | - | None |
| CFD Scoring | COMPLETE | CRISPOR resources loaded, E2E verified | 4/4 run | None |
| Sequence Properties | COMPLETE | All sequence features implemented | 75/75 | None |
| Documentation | COMPLETE | 18 files updated | - | None |
| Cas-OFFinder Integration | COMPLETE | Bulge-aware search implemented | 26/26 | CPU-only mode |
| Black-Box Verification | COMPLETE | All 4 interfaces verified | 10/10 PASS | Real engine execution |

## Detailed Subsystem Tables

### CFD Scoring

| Component | Status | Evidence | Test result | Notes |
|-----------|--------|----------|-------------|-------|
| Resource Discovery | COMPLETE | references/__init__.py | PASS | data/resources/crispor_cfd/ |
| Mismatch Loading | COMPLETE | score_offtargets.py | PASS | 240 entries loaded |
| PAM Loading | COMPLETE | score_offtargets.py | PASS | 16 entries loaded |
| calc_cfd() | COMPLETE | test_mcp.py::test_cfd_known_case | PASS | Matches upstream |
| score_offtargets() | COMPLETE | test_mcp.py::test_score_offtargets_tool | PASS | E. coli verified |
| CLI | COMPLETE | offtarget score | PASS | JSON output |
| HTTP API | COMPLETE | POST /offtarget/score | PASS | 200 OK |
| MCP | COMPLETE | score_offtargets tool | PASS | Real CFD scores |

### Off-target Analysis

| Component | Status | Implementation | Test | Dependencies | Caveats |
|-----------|--------|----------------|------|--------------|---------|
| BWA Index Build | COMPLETE | bwa index | PASS | bwa | Cached in SQLite |
| BWA Aln Search | COMPLETE | bwa aln + samse | PASS | bwa, .bwt | E. coli genome |
| Cas-OFFinder Search | COMPLETE | cas_offinder_search | PASS | cas-offinder, POCL | CPU-only mode |
| DNA Bulge Detection | COMPLETE | cas_offinder_search | PASS | cas-offinder | Up to N bulges |
| RNA Bulge Detection | COMPLETE | cas_offinder_search | PASS | cas-offinder | Up to N bulges |
| Regional Search | COMPLETE | cas_offinder_search + post-filter | PASS | cas-offinder | Region-scope mode |
| Analyze Mismatch Seed | COMPLETE | analyze_mismatch_seed | PASS | None | Alignment-aware |
| CFD Scoring | COMPLETE | pickle load + calc_cfd | PASS | CRISPOR pickles | Verified against upstream |
| Black-Box: Python API | COMPLETE | search_offtargets | PASS | All above | Real engine execution |
| Black-Box: HTTP API | COMPLETE | POST /offtarget/search | PASS | All above | 200 OK responses |
| Black-Box: MCP | COMPLETE | offtarget_search | PASS | All above | ToolResult format |
| Black-Box: CLI | COMPLETE | offtarget search | PASS | All above | JSON output |
| Canonical Parity | COMPLETE | All interfaces match | PASS | None | Identical results |

### Sequence Properties

| Component | Status | Implementation | Test | Notes |
|-----------|--------|----------------|------|-------|
| GC Content | COMPLETE | mcp/tools/compute_gc_content.py | 24/24 PASS | Overall, 5'/3' split, sliding window |
| GC 5'/3' Split | COMPLETE | compute_gc_content | PASS | floor(len * ratio) split |
| Sliding Window GC | COMPLETE | compute_gc_content | PASS | O(n) rolling window |
| Basic GC Filter | COMPLETE | compute_gc_content | PASS | Configurable min/max thresholds |
| Homopolymer Detection | COMPLETE | mcp/tools/check_homopolymer_runs.py | 20/20 PASS | poly-T, poly-G, configurable strictness |
| Poly-T Detection | COMPLETE | check_homopolymer_runs | PASS | Strict/non-strict modes |
| Poly-G Detection | COMPLETE | check_homopolymer_runs | PASS | Strict/non-strict modes |
| Tm Calculation | COMPLETE | mcp/tools/compute_melting_temp.py | 15/15 PASS | Nearest-neighbor, Wallace, GC-percent |
| Seed Tm | COMPLETE | compute_melting_temp | PASS | 3' region Tm calculation |
| MFE/Secondary Structure | COMPLETE | mcp/tools/compute_secondary_structure.py | 15/15 PASS | ViennaRNA 2.7.2, DNA→RNA conversion |
| Scaffold Folding | COMPLETE | compute_secondary_structure | PASS | Caller-provided scaffold |
| Structure String | COMPLETE | compute_secondary_structure | PASS | Dot-bracket notation |
| Positional Features | COMPLETE | mcp/tools/compute_positional_features.py | 25/25 PASS | 1-based biological positions, one-hot encoding |
| One-hot Encoding | COMPLETE | compute_positional_features | PASS | Configurable alphabet, ambiguous base handling |
| Position-20 Bias | COMPLETE | compute_positional_features | PASS | G=favored, T=disfavored, A/C=neutral |
| Custom Position Checks | COMPLETE | compute_positional_features | PASS | Arbitrary 1-based positions |
| Dinucleotide Composition | COMPLETE | mcp/tools/compute_dinucleotide_composition.py | 20/20 PASS | Position-anchored, configurable window size |
| Aggregate Counts | COMPLETE | compute_dinucleotide_composition | PASS | Raw k-mer counts |
| Normalized Frequencies | COMPLETE | compute_dinucleotide_composition | PASS | count / total_windows |
| Full Position Matrix | COMPLETE | compute_dinucleotide_composition | PASS | Per-position anchored rows |
| Target Filtering | COMPLETE | compute_dinucleotide_composition | PASS | Specific k-mer reporting with zero-count |
| Seed GC | COMPLETE | mcp/tools/compute_seed_gc.py | 20/20 PASS | PAM-proximal seed GC, configurable length |
| Seed/Distal GC Delta | COMPLETE | compute_seed_gc | PASS | Optional seed-vs-distal comparison |
| Seed Threshold Filter | COMPLETE | compute_seed_gc | PASS | Configurable min/max thresholds |

## Test Summary

```
Total:    346
Passed:   340
Failed:   0
Skipped:  6
Warnings: 7
```

**Skipped:**
- 4 `pam_scan_region` tests — missing genome with .fai index in test fixtures
- 2 `offtarget_search` tests — missing genome with BWA index in test fixtures
- (Previously skipped CFD tests are now passing)

**Note:** Previous `test_full_pipeline` failure is now FIXED.

## End-to-End Verification

| Step | Tool | Input | Result | Status |
|------|------|-------|--------|--------|
| 1 | ingest | test.fasta | 3 records, 64 bases | ✅ |
| 2 | pam scan | ATCGATCGAGG | 1 site (AGG at pos 9) | ✅ |
| 3 | pam scan-region | ecoli_k12_mg1655:NC_000913.3:100000-100100 | 12 PAM sites | ✅ |
| 4 | rank | PAM results | 1 candidate | ✅ |
| 5 | build index | ecoli_k12_mg1655 | Index built (2.2s) | ✅ |
| 6 | offtarget search | ecoli_k12_mg1655, GATTGCCACCAAAGTGATGC | 1 exact match | ✅ |
| 7 | CFD score | exact match, AGG PAM | CFD = 1.0 | ✅ |
| 8 | ranking | scored candidates | 1 ranked guide | ✅ |
| 9 | homopolymer | ACGTTTTACGT | polyT=True, passes=False | ✅ |
| 10 | melting temp | GCGCGCGCGCGCGCGCGCGC | Tm=79.21°C | ✅ |
| 11 | secondary structure | GCGCGCGCGCGCGCGCGCGC | MFE=-16.7 kcal/mol | ✅ |
| 12 | scaffold folding | spacer + scaffold | MFE=-33.2 kcal/mol | ✅ |
| 13 | positional features | GCGCGCGCGCGCGCGCGCGG | pos20=G, favored | ✅ |
| 14 | one-hot encoding | ACGTACGTACGTACGTACGT | 20x4 matrix | ✅ |
| 15 | dinucleotide composition | GCGCGCGCGCGCGCGCGCGG | GC=9, CG=9, GG=1 | ✅ |
| 16 | full matrix | ACGT (4nt) | 3 anchored rows | ✅ |
| 17 | seed GC | GCGCGCGCGCGCGCGCGCGG | seed_gc=0.5, passes=True | ✅ |
| 18 | seed distal delta | GCGCGCGCGCGCGCGCGCGG | delta=0.0 | ✅ |
| 19 | Cas-OFFinder search | GCGCGCGCGCGCGCGCGCGC, E. coli | Bulge candidates found | ✅ |
| 20 | DNA bulge detection | GCGCGCGCGCGCGCGCGCGC, bulge=1 | DNA bulges detected | ✅ |
| 21 | RNA bulge detection | GCGCGCGCGCGCGCGCGCGC, bulge=1 | RNA bulges detected | ✅ |
| 22 | Analyze mismatch seed | alignment-aware analysis | Seed/distal classified | ✅ |

## Known Limitations

1. **CFD scoring not supported for bulged candidates** — `cfd_status = "unsupported_bulge"` for DNA/RNA bulge candidates
2. **BWA aln uses quality-weighted mismatches** — not pure CRISPR mismatch counting
3. **GRCh38.p14 not available** — full human genome not at expected path (E. coli used for testing)
4. **DNA→RNA conversion** — ViennaRNA folds RNA; DNA sequences converted to RNA (T→U) before folding
5. **Seed anchor** — Only `pam_proximal` anchor currently supported
6. **CPU-only Cas-OFFinder** — Slower than GPU-accelerated mode

## Next Recommended Work

1. **Add more E2E tests** — Test full pipeline with real genomes
2. **Add input validation** — More explicit bounds on numeric parameters
3. **Implement GPU-accelerated Cas-OFFinder** — When OpenCL GPU runtime available

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Biopython | 1.83 | Tm calculations (MeltingTemp module) |
| ViennaRNA | 2.7.2 | Secondary structure / MFE calculations |
| bwa | 0.7.17 | Off-target search (BWA aln) |
| samtools | 1.19.2 | FASTA indexing (.fai files) |
| Cas-OFFinder | 3.0.0 | Bulge-aware off-target search |
| POCL | 2.3+ | OpenCL CPU runtime for Cas-OFFinder |

## Files Changed This Session

- `backend/mcp/tools/compute_seed_gc.py` — New seed GC MCP tool
- `backend/core/seed_gc.py` — Core seed GC service wrapper
- `backend/schemas/canonical.py` — Added ComputeSeedGCRequest
- `backend/mcp/server.py` — Registered compute_seed_gc in TOOL_REGISTRY (now 15 tools)
- `backend/api/__init__.py` — Added compute_seed_gc to Python API
- `backend/http_api/app.py` — Added POST /sequence/seed-gc endpoint
- `backend/cli/main.py` — Added `sequence seed-gc` subcommand
- `backend/tests/test_mcp.py` — Added 20 seed GC tests + 26 Cas-OFFinder tests
- `backend/tests/test_interfaces.py` — Added 6 interface parity tests + 8 Cas-OFFinder parity tests
- `backend/doc/seed_gc.md` — New seed GC documentation
- `backend/mcp/tools/cas_offinder_search.py` — New Cas-OFFinder MCP tool
- `backend/mcp/tools/analyze_mismatch_seed.py` — New alignment-aware seed analysis tool
- `backend/mcp/tools/offtarget_search.py` — Extended with backend selection + bulge routing
- `backend/core/offtarget.py` — Updated with bulge field mapping + new params
- `backend/api/__init__.py` — Extended search_offtargets + added analyze_mismatch_seed
- `backend/cli/main.py` — Extended offtarget search with bulge params
- `backend/http_api/app.py` — Extended offtarget/search + added /offtarget/analyze-seed
- `backend/schemas/canonical.py` — Extended ResultRow + OfftargetSearchRequest with bulge fields
- `backend/doc/off_target_search.md` — Updated with Cas-OFFinder integration
- `backend/doc/cas_offinder.md` — New Cas-OFFinder documentation
- `veyra/Status.md` — This file
