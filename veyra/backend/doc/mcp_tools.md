# MCP Tools Reference

VEYRA provides six MCP (Model Context Protocol) tools for genomic/CRISPR analysis.
All tools return a uniform `ToolResult` with `PAMSiteRow` entries, serialized as JSON or TSV.

**Coordinate convention:** All coordinates are 1-based, half-open `[start, end)`.
`start` is inclusive, `end` is exclusive. Consistent with samtools/BLAST convention.

---

## Tool Overview

| Tool | Tier | Cost | Description |
|------|------|------|-------------|
| `pam_scan` | 1 | cheap / deterministic | PAM scanning on an input sequence |
| `pam_scan_region` | 1 | cheap / reference lookup | PAM scanning on a genomic region |
| `build_offtarget_index` | 2 | expensive / cacheable | BWA index creation |
| `offtarget_search` | 2 | expensive / genome-scale | Mismatch-tolerant off-target search |
| `score_offtargets` | 2 | moderate | CFD specificity scoring |
| `rank_candidates` | 2 | moderate | Candidate guide ranking |

---

## 1. pam_scan

**Purpose:** Fast PAM/protospacer discovery within a raw DNA sequence using regex/IUPAC matching.

**Tier:** 1 — cheap / deterministic

**Python signature:**

```python
pam_scan(
    sequence: str,
    pam_pattern: str = "NGG",
    protospacer_len: int = 20,
    strand: str = "both",
    chrom: str | None = None,
) -> ToolResult
```

**Inputs:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sequence` | str | required | Raw DNA string (may contain IUPAC ambiguity codes) |
| `pam_pattern` | str | `"NGG"` | IUPAC PAM motif |
| `protospacer_len` | int | `20` | Protospacer length (1–100) |
| `strand` | str | `"both"` | `"both"`, `"fwd"`, or `"rev"` |
| `chrom` | str | `None` | Optional chromosome/contig name for output |

**Output:** `ToolResult` with `PAMSiteRow` entries. Each row contains:

| Field | Description |
|-------|-------------|
| `chrom` | Chromosome name (if provided) |
| `start` | 1-based start of PAM |
| `end` | Exclusive end of PAM |
| `strand` | `+` or `-` |
| `protospacer` | 20nt sequence upstream/downstream of PAM |
| `pam` | Matched PAM sequence |
| `pam_type` | Resolved Cas name or `custom:<pattern>` |

**Summary fields:** `total_sites`, `forward_sites`, `reverse_sites`, `sequence_length`, `pam_pattern`, `protospacer_len`, `strand_filter`, `coordinates`

**Dependencies:** None (pure Python regex).

**Cache behavior:** None (stateless).

**Errors:** Empty sequence, invalid DNA characters, invalid PAM pattern, invalid strand value, protospacer length out of range.

**CLI:**

```bash
python -m mcp.server pam-scan --sequence ATCGATCGATCGATCGATCGAGG --pam NGG
```

**Known limitations:**
- For sequences ≥ 100 kbp, `parsers/pam.py` uses an FM-index internally, but `pam_scan` (MCP tool) always uses regex. Use the underlying `parsers.pam.scan_pam()` directly for FM-index mode.
- Does not perform off-target scoring.

---

## 2. pam_scan_region

**Purpose:** PAM scanning against a genomic region using indexed FASTA access (`samtools faidx`). Does NOT load the entire genome into memory.

**Tier:** 1 — cheap / reference lookup

**Python signature:**

```python
pam_scan_region(
    genome_id: str,
    chrom: str,
    start: int,
    end: int,
    pam_pattern: str = "NGG",
    protospacer_len: int = 20,
    strand: str = "both",
) -> ToolResult
```

**Inputs:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `genome_id` | str | required | Registered genome ID (e.g. `"GRCh38.p14"`) |
| `chrom` | str | required | Chromosome/contig name |
| `start` | int | required | 1-based start (inclusive) |
| `end` | int | required | 1-based end (exclusive) |
| `pam_pattern` | str | `"NGG"` | IUPAC PAM motif |
| `protospacer_len` | int | `20` | Protospacer length |
| `strand` | str | `"both"` | `"both"`, `"fwd"`, or `"rev"` |

**Output:** Same as `pam_scan`, but coordinates are in genome space.

**Summary fields:** Same as `pam_scan` plus `genome_id`, `region`.

**Dependencies:** `samtools faidx` on PATH, `.fai` index for the genome.

**Cache behavior:** None (stateless per call).

**Errors:** Unknown genome, no `.fai` index, invalid coordinates, `samtools` not found, empty region.

**CLI:**

```bash
python -m mcp.server pam-scan-region --genome GRCh38.p14 --chrom chr1 --start 1000000 --end 1001000
```

**Known limitations:**
- Requires `.fai` index. Build with: `samtools faidx <fasta>`
- Region size limited by `samtools faidx` performance (practical limit ~10 Mbp per call).

---

## 3. build_offtarget_index

**Purpose:** Build or retrieve a cached BWA index for off-target searching. This is an expensive operation; indexes are cached by genome + checksum.

**Tier:** 2 — expensive / cacheable

**Python signature:**

```python
build_offtarget_index(
    genome_id: str,
    cas_variant: str = "SpCas9",
    force_rebuild: bool = False,
) -> ToolResult
```

**Inputs:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `genome_id` | str | required | Registered genome ID |
| `cas_variant` | str | `"SpCas9"` | Cas variant (used in cache key) |
| `force_rebuild` | bool | `False` | Force rebuild even if cache exists |

**Output:** `ToolResult` with summary containing `status`, `genome_id`, `cas_variant`, `index_path`, `build_time_seconds`, `cache_key`.

**Dependencies:** `bwa` on PATH. Also builds `.fai` index via `samtools faidx` if missing.

**Cache behavior:**
- Cache key = SHA256 of `build_offtarget_index:{genome_id, cas_variant, checksum}`
- Cached in SQLite (`cache/veyra_cache.db`) with 30-day TTL
- On cache hit, verifies `.bwt` file exists on disk before returning cached result
- `force_rebuild=True` bypasses cache and rebuilds

**Errors:** Unknown genome, FASTA not found, `bwa` not found, `bwa index` timeout (2h limit).

**CLI:**

```bash
python -m mcp.server build-index --genome GRCh38.p14 --force
```

---

## 4. offtarget_search

**Purpose:** Search a genome for approximate matches to a guide/spacer using BWA aln with mismatch tolerance.

**Tier:** 2 — expensive / genome-scale

**Python signature:**

```python
offtarget_search(
    spacer_sequence: str,
    genome_id: str,
    pam_pattern: str = "NGG",
    max_mismatches: int = 4,
    allow_bulge: bool = False,
    cas_variant: str = "SpCas9",
) -> ToolResult
```

**Inputs:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `spacer_sequence` | str | required | 20nt guide/spacer sequence |
| `genome_id` | str | required | Registered genome ID |
| `pam_pattern` | str | `"NGG"` | IUPAC PAM pattern |
| `max_mismatches` | int | `4` | Max mismatches (0–10) |
| `allow_bulge` | bool | `False` | Not yet implemented (BWA limitation) |
| `cas_variant` | str | `"SpCas9"` | Cas variant name |

**Output:** `ToolResult` with `PAMSiteRow` entries. Each row contains `chrom`, `start`, `end`, `strand`, `protospacer`, `pam`, `mismatch_count`, `mismatch_positions`.

**Summary fields:** `total_candidates`, `spacer_length`, `max_mismatches`, `genome_id`, `pam_pattern`, `mismatch_distribution`, `backend` (`"bwa-aln"`).

**Dependencies:** `bwa` (aln + samse), `samtools` (for PAM extraction). Requires BWA index from `build_offtarget_index`.

**Cache behavior:** None (each search runs BWA aln).

**Errors:** Invalid DNA, invalid PAM, genome not found, no BWA index, `bwa aln` failure, `bwa samse` failure.

**CLI:**

```bash
python -m mcp.server offtarget-search --spacer ATCGATCGATCGATCGATCGAGG --genome GRCh38.p14 --max-mismatches 3
```

**Known limitations:**
- BWA uses quality-weighted mismatches and seed-based heuristics. Results are **approximate candidates**, not exact CRISPOR/Cas-OFFinder semantics.
- BWA does not support bulges/indels.
- `max_mismatches > 5` may be slow or miss candidates due to BWA seed heuristics.
- PAM extraction requires `samtools faidx` index.

---

## 5. score_offtargets

**Purpose:** Calculate CFD-style specificity scores for off-target candidates using CRISPOR's CFD scoring resources.

**Tier:** 2 — moderate

**Python signature:**

```python
score_offtargets(
    spacer_sequence: str,
    candidates: list[PAMSiteRow],
    pam_pattern: str = "NGG",
) -> ToolResult
```

**IMPORTANT:** The correct argument order is `(spacer, candidates, pam)`. The first argument is the wild-type spacer string, not the candidates list.

**Inputs:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `spacer_sequence` | str | required | Wild-type 20nt spacer sequence |
| `candidates` | list[PAMSiteRow] | required | Off-target candidates (from `offtarget_search`) |
| `pam_pattern` | str | `"NGG"` | PAM pattern (for PAM scoring context) |

**Output:** `ToolResult` with `cfd_score` added to each `PAMSiteRow`.

**Summary fields:** `total_scored`, `spacer_length`, `scoring_method`, `scoring_note`, `mean_cfd`, `max_cfd`, `min_cfd`.

**Dependencies:** CFD pickle files at `refrences/data/benchmarks/crisporPaper/CFD_Scoring/`:
- `mismatch_score.pkl`
- `pam_scores.pkl`

**Cache behavior:** CFD pickle data is loaded once at module level and cached in memory (`_mm_scores`, `_pam_scores`).

**Errors:** Spacer too short (< 15nt), CFD resources not found, scoring failure on individual candidates.

**CLI:**

```bash
python -m mcp.server invoke score_offtargets --args-json '{"spacer_sequence": "ATCGATCGATCGATCGATCGAGG", "candidates": [...]}'
```

**Known limitations:**
- CFD scoring is derived from Doench et al. 2016. It is **NOT experimentally validated by VEYRA**.
- PAM score uses the 2nt adjacent to the protospacer on the 3' end (for SpCas9).
- Mismatch positions are 1-based in the CFD key format.

---

## 6. rank_candidates

**Purpose:** Aggregate off-target evidence per candidate guide and produce a ranked table. Uses transparent evidence aggregation, NOT a validated predictive model.

**Tier:** 2 — moderate

**Python signature:**

```python
rank_candidates(
    guides: list[PAMSiteRow],
    off_targets: list[PAMSiteRow] | None = None,
    on_target_scores: dict[str, float] | None = None,
    sort_by: str = "composite",
) -> ToolResult
```

**Inputs:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `guides` | list[PAMSiteRow] | required | Candidate guide rows |
| `off_targets` | list[PAMSiteRow] | `None` | Off-target rows (scored) |
| `on_target_scores` | dict | `None` | `{protospacer: score}` mapping |
| `sort_by` | str | `"composite"` | `"composite"`, `"cfd_max"`, `"offtarget_count"`, `"on_target"` |

**Output:** `ToolResult` with ranked rows. `mismatch_count` field holds `total_offtargets`; `cfd_score` field holds `max_cfd`.

**Summary fields:** `total_candidates`, `sort_by`, `ranking_note`, `evidence_sources`.

**Dependencies:** None.

**Cache behavior:** None.

**Errors:** No candidates provided, unknown sort criterion.

**CLI:**

```bash
python -m mcp.server invoke rank_candidates --args-json '{"guides": [...], "off_targets": [...]}'
```

**Known limitations:**
- Ranking is evidence aggregation only — not a validated prediction.
- Off-targets are assigned to guides by simple group (single-guide queries assign all to that guide).
- Future VEYRA reasoning layers will refine rankings.

---

## Shared Schemas

### PAMSiteRow

All tools output `PAMSiteRow` entries:

```python
@dataclass
class PAMSiteRow:
    chrom: str | None = None
    start: int | None = None       # 1-based
    end: int | None = None         # exclusive
    strand: str | None = None      # "+" or "-"
    protospacer: str | None = None
    pam: str | None = None
    pam_type: str | None = None
    mismatch_count: int | None = None
    mismatch_positions: str | None = None  # comma-separated 0-based positions
    cfd_score: float | None = None
    rs2_score: float | None = None
```

### ToolResult

```python
@dataclass
class ToolResult:
    tool: str
    rows: list[PAMSiteRow]
    summary: dict[str, Any]
    errors: list[str]
    warnings: list[str]
    metadata: dict[str, Any]
```

Methods: `to_json(indent=None)`, `to_tsv()`

---

## MCP Server CLI

```bash
# List all tools
python -m mcp.server list

# Generic invocation
python -m mcp.server invoke <tool_name> --args-json '{"param": "value"}'

# Quick shortcuts
python -m mcp.server pam-scan --sequence <seq>
python -m mcp.server pam-scan-region --genome <id> --chrom <chr> --start <n> --end <n>
python -m mcp.server build-index --genome <id> [--force]
python -m mcp.server offtarget-search --spacer <seq> --genome <id>
```
