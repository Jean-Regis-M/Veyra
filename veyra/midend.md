# VEYRA Machine-Facing Midend Contract

Status: Verified against implementation
Source of truth: `veyra/backend/api/__init__.py`, `veyra/backend/core/*.py`, `veyra/backend/schemas/canonical.py`, `veyra/backend/mcp/server.py`, `veyra/backend/http_api/app.py`, `veyra/backend/cli/main.py`

## MIDEND upload validation

The public MIDEND accepts validated multipart uploads at `POST /inputs/file`.
The implemented backend ingestion formats are FASTA (`.fa`, `.fasta`, `.fna`,
`.faa`, `.fns`, `.frn`), FASTQ (`.fq`, `.fastq`, `.fqr`), and GenBank (`.gb`,
`.gbk`, `.gbff`, `.genbank`). GFF/GFF3 and plain DNA text files are not file
inputs until a corresponding backend parser exists. MIDEND validates extension,
content/MIME consistency, UTF-8 structure, records, nucleotide characters, a
50 MiB size limit, and filename safety before storing an input ID. Invalid
inputs return structured validation errors and cannot reach AI or backend
execution. See `midend/doc/input_validation.md`.

---

## 1. Purpose and scope

This document defines the authoritative machine-facing contract between the MIDEND / AI orchestration layer and the VEYRA backend. It enables an AI agent, router, or automated orchestrator to determine operation availability, parameter bounds, validation rules, runtime dependencies, cost profiles, error behaviors, returned structures, side effects, and next logical operation steps without reverse-engineering backend source code.

The backend is the source of truth for:

- public Python API surface (`from api import ...`)
- core service logic (`core.*`)
- canonical request and response schemas (`schemas.canonical`)
- MCP tool registry entries (`mcp.server.TOOL_REGISTRY`)
- FastAPI HTTP REST endpoints (`http_api/app.py`)
- CLI command wrappers (`cli/main.py`)
- isolated model runtime management (`core/model_runtime.py`)

---

## 2. Interface layers

| Layer | Purpose | Verified public access |
|-------|---------|------------------------|
| Python API | Primary programmatic surface | `from api import ...` |
| Core service layer | Business logic and validation | `from core import ...` |
| Canonical schemas | Unified data contracts | `schemas.canonical` |
| MCP tools | Agentic tool invocation registry | `mcp.server.TOOL_REGISTRY` |
| HTTP API | REST access for external clients/frontends | FastAPI routes in `http_api/app.py` |
| CLI | Shell/CLI wrapper | `python -m cli.main` / `veyra` |

The implementation is strictly layered: CLI, HTTP API, MCP tools, and Python API functions all delegate to the same underlying core services and canonical request/result schemas.

---

## 3. Canonical data contracts

### 3.1 Request dataclasses

The authoritative request types in `schemas/canonical.py` are:

- `IngestRequest`
- `PamScanRequest`
- `PamScanRegionRequest`
- `BuildIndexRequest`
- `OfftargetSearchRequest`
- `ScoreOfftargetsRequest`
- `RankCandidatesRequest`
- `GenomeListRequest`
- `GenomeInfoRequest`
- `CacheStatusRequest`
- `CacheClearRequest`
- `ComputeGCContentRequest`
- `CheckHomopolymerRunsRequest`
- `ComputeMeltingTempRequest`
- `ComputeSecondaryStructureRequest`
- `ComputePositionalFeaturesRequest`
- `ComputeDinucleotideCompositionRequest`
- `ComputeSeedGCRequest`
- `ComputeCutSiteRequest`
- `ComputeOnTargetEfficiencyRequest`

### 3.2 Result objects

The canonical response wrapper across core functions and API boundaries is `VeyraResult`:

```yaml
VeyraResult:
  tool: string
  rows: list[ResultRow]
  summary: dict
  errors: list[string]
  warnings: list[string]
  metadata: dict
```

`ResultRow` (and its internal alias `PAMSiteRow`) represents individual candidate hits or scanned sites:

```yaml
ResultRow:
  chrom: string | null
  start: int | null              # 1-based start (inclusive)
  end: int | null                # 1-based end (exclusive)
  strand: string | null           # "+" or "-"
  protospacer: string | null
  pam: string | null
  pam_type: string | null
  mismatch_count: int | null
  mismatch_positions: string | null  # comma-separated 0-based positions
  cfd_score: float | null
  rs2_score: float | null
  bulge_type: string | null     # "X", "DNA", or "RNA"
  bulge_size: int | null
  bulge_position: int | null
  aligned_guide: string | null  # aligned guide sequence with gaps
  aligned_candidate: string | null # aligned candidate sequence with gaps
  cfd_status: string | null     # e.g., "unsupported_bulge"
```

### 3.3 Coordinate conventions

The backend enforces uniform biological and genomic coordinate systems:

- **Genomic coordinates**: 1-based half-open range `[start, end)`, where `start` is inclusive (1-indexed) and `end` is exclusive.
- **Cleavage anchor coordinates**: `spacer_start` is 0-based in `compute_cut_site` for genomic calculation, while relative cut positions are 1-based biological spacer boundaries (e.g. between spacer positions 17 and 18 for SpCas9).
- **Spacer positions**: 1-based biological orientation (Position 1 = 5' end of spacer, Position 20 = 3' PAM-proximal nucleotide).
- **Strand values**: `"+"`, `"-"`, or `"both"`.
- **PAM position**: `"3prime"` (canonical 3' orientation for SpCas9).

---

## 4. Verified public APIs & Complete Tool Inventory

### 4.1 Complete Public Operation Inventory (Part 1)

The table below details EVERY operation exposed by VEYRA across Python API, CLI, HTTP API, and MCP layers.

| Operation Name | Category | Python API | CLI Command | HTTP Endpoint | MCP Tool | Cost Tier | Mutating Status | Prerequisite Status |
|----------------|----------|------------|-------------|---------------|----------|-----------|-----------------|---------------------|
| `ingest_file` | Ingestion | `api.ingest_file` | `veyra ingest` | `POST /ingest` | `N/A` | Tier 1 (cheap) | Read-only | Valid file path |
| `list_genomes` | Genome Registry | `api.get_genomes` | `veyra genome list` | `GET /genomes` | `N/A` | Tier 1 (cheap) | Read-only | None |
| `genome_info` | Genome Registry | `api.get_genome_info` | `veyra genome info` | `GET /genomes/{genome_id}` | `N/A` | Tier 1 (cheap) | Read-only | Registered `genome_id` |
| `pam_scan` | PAM Discovery | `api.pam_scan_raw` | `veyra pam scan` | `POST /pam/scan` | `pam_scan` | Tier 1 (cheap) | Read-only | None |
| `pam_scan_region` | PAM Discovery | `api.pam_scan_region` | `veyra pam scan-region` | `POST /pam/scan-region` | `pam_scan_region` | Tier 1 (cheap) | Read-only | Genome FASTA indexed (`.fai`) |
| `build_offtarget_index` | Indexing | `api.build_offtarget_index` | `veyra index build` | `POST /index/build` | `build_offtarget_index` | Tier 2 (expensive) | Mutating (disk write) | Registered `genome_id` |
| `offtarget_search` | Off-Target Search | `api.search_offtargets` | `veyra offtarget search` | `POST /offtarget/search` | `offtarget_search` | Tier 2 (expensive) | Read-only (cached) | BWA index or Cas-OFFinder setup |
| `cas_offinder_search` | Off-Target Search | `N/A` (direct import) | `veyra offtarget search --backend cas_offinder` | `N/A` (via `/offtarget/search`) | `cas_offinder_search` | Tier 2 (expensive) | Read-only (temp files) | Cas-OFFinder binary + POCL OpenCL |
| `score_offtargets` | Off-Target Scoring | `api.score_offtargets_cfd` | `veyra offtarget score` | `POST /offtarget/score` | `score_offtargets` | Tier 2 (moderate) | Read-only | Candidates list |
| `rank_candidates` | Guide Ranking | `api.rank_guides` | `veyra rank` | `POST /rank` | `rank_candidates` | Tier 2 (moderate) | Read-only | Guide candidate list |
| `analyze_mismatch_seed` | Off-Target Analysis | `api.analyze_mismatch_seed` | `N/A` | `POST /offtarget/analyze-seed` | `analyze_mismatch_seed` | Tier 1 (cheap) | Read-only | Spacer & candidate sequence |
| `compute_gc_content` | Sequence Features | `api.compute_gc_content` | `veyra sequence gc` | `POST /sequence/gc` | `compute_gc_content` | Tier 1 (cheap) | Read-only | None |
| `check_homopolymer_runs` | Sequence Features | `api.check_homopolymer_runs` | `veyra sequence homopolymer` | `POST /sequence/homopolymer` | `check_homopolymer_runs` | Tier 1 (cheap) | Read-only | None |
| `compute_melting_temp` | Sequence Features | `api.compute_melting_temp` | `veyra sequence tm` | `POST /sequence/tm` | `compute_melting_temp` | Tier 1 (cheap) | Read-only | None |
| `compute_secondary_structure` | Sequence Features | `api.compute_secondary_structure` | `veyra sequence secondary-structure` | `POST /sequence/secondary-structure` | `compute_secondary_structure` | Tier 1 (moderate) | Read-only | ViennaRNA optional |
| `compute_positional_features` | Sequence Features | `api.compute_positional_features` | `veyra sequence positional-features` | `POST /sequence/positional-features` | `compute_positional_features` | Tier 1 (cheap) | Read-only | None |
| `compute_dinucleotide_composition` | Sequence Features | `api.compute_dinucleotide_composition` | `veyra sequence dinucleotide-composition` | `POST /sequence/dinucleotide-composition` | `compute_dinucleotide_composition` | Tier 1 (cheap) | Read-only | None |
| `compute_seed_gc` | Sequence Features | `api.compute_seed_gc` | `veyra sequence seed-gc` | `POST /sequence/seed-gc` | `compute_seed_gc` | Tier 1 (cheap) | Read-only | None |
| `compute_cut_site` | Geometry & Cut Site | `api.compute_cut_site` | `veyra sequence cut-site` | `POST /sequence/cut-site` | `compute_cut_site` | Tier 1 (cheap) | Read-only | None |
| `predict_ontarget_efficiency` | On-Target Prediction | `api.predict_ontarget_efficiency` | `veyra score on-target` | `POST /score/ontarget` | `predict_ontarget_efficiency` | Tier 1 (cheap) | Read-only | Verified model runtime |
| `list_model_runtimes` | Model Management | `api.list_model_runtimes` | `veyra models list` | `GET /models` | `models_list_runtimes` | Tier 1 (cheap) | Read-only | None |
| `get_model_status` | Model Management | `api.get_model_status` | `veyra models describe` | `GET /models/{model_id}` | `model_status` | Tier 1 (cheap) | Read-only | Valid `model_id` |
| `provision_model` | Model Management | `api.provision_model` | `veyra models setup` | `POST /models/{model_id}/setup` | `setup_model` | Tier 2 (expensive) | Mutating (creates venv) | Valid `model_id` |
| `verify_model` | Model Management | `api.verify_model` | `veyra models verify` | `POST /models/{model_id}/verify` | `verify_model` | Tier 2 (moderate) | Read-only | Provisioned model runtime |
| `ensure_model_ready` / `get_model_spec` | Model Management | `api.ensure_model_ready` / `api.get_model_spec` | `veyra models check` | `N/A` | `N/A` | Tier 1-2 | Mutating if provisioned | Valid `model_id` |
| `cache_status` | System & Cache | `api.get_cache_info` | `veyra cache status` | `GET /cache/status` | `N/A` | Tier 1 (cheap) | Read-only | None |
| `clear_cache` | System & Cache | `api.clear_cache` | `veyra cache clear` | `POST /cache/clear` | `N/A` | Tier 1 (cheap) | Mutating (clears disk cache) | None |
| `list_tools` | System Info | `N/A` | `veyra tools list` | `GET /tools` | `veyra-mcp list` | Tier 1 (cheap) | Read-only | None |

### 4.2 Python API surface

Exposed top-level exports in `api/__init__.py`:

```python
from api import (
    ingest_file,
    pam_scan_raw,
    pam_scan_region,
    build_offtarget_index,
    search_offtargets,
    score_offtargets_cfd,
    rank_guides,
    get_genomes,
    get_genome_info,
    get_cache_info,
    clear_cache,
    compute_gc_content,
    check_homopolymer_runs,
    compute_melting_temp,
    compute_secondary_structure,
    compute_positional_features,
    compute_dinucleotide_composition,
    compute_seed_gc,
    analyze_mismatch_seed,
    compute_cut_site,
    predict_ontarget_efficiency,
    provision_model,
    verify_model,
    ensure_model_ready,
    get_model_status,
    list_model_runtimes,
    get_model_spec,
)
```

### 4.3 Core service layer

Exports in `core/__init__.py`:

```python
__all__ = [
    "pam_scan",
    "pam_scan_region",
    "ingest",
    "build_index",
    "offtarget_search",
    "score_offtargets",
    "rank_candidates",
    "list_genomes",
    "genome_info",
    "cache_status",
    "cache_clear",
]
```

### 4.4 MCP tool registry

Exposed tools in `mcp.server.TOOL_REGISTRY`:

```python
TOOL_REGISTRY = {
    "pam_scan": {"cost": "cheap / deterministic", "tier": 1},
    "pam_scan_region": {"cost": "cheap / reference lookup", "tier": 1},
    "build_offtarget_index": {"cost": "expensive / setup / cacheable", "tier": 2},
    "offtarget_search": {"cost": "expensive / genome-scale", "tier": 2},
    "score_offtargets": {"cost": "moderate", "tier": 2},
    "rank_candidates": {"cost": "moderate", "tier": 2},
    "compute_gc_content": {"cost": "cheap / deterministic", "tier": 1},
    "check_homopolymer_runs": {"cost": "cheap / deterministic", "tier": 1},
    "compute_melting_temp": {"cost": "moderate / deterministic", "tier": 1},
    "compute_secondary_structure": {"cost": "moderate / deterministic / optional dependency", "tier": 1},
    "compute_positional_features": {"cost": "cheap / deterministic", "tier": 1},
    "compute_dinucleotide_composition": {"cost": "cheap / deterministic", "tier": 1},
    "compute_seed_gc": {"cost": "cheap / deterministic", "tier": 1},
    "cas_offinder_search": {"cost": "expensive / genome-scale / bulge-aware", "tier": 2},
    "analyze_mismatch_seed": {"cost": "cheap / deterministic", "tier": 1},
    "compute_cut_site": {"cost": "cheap / deterministic", "tier": 1},
    "predict_ontarget_efficiency": {"cost": "cheap / deterministic", "tier": 1},
    "models_list_runtimes": {"cost": "cheap", "tier": 1},
    "model_status": {"cost": "cheap", "tier": 1},
    "setup_model": {"cost": "expensive / setup", "tier": 2},
    "verify_model": {"cost": "moderate", "tier": 2},
}
```

### 4.5 HTTP REST routes

Verified FastAPI endpoints in `http_api/app.py`:

```text
GET  /health
POST /ingest
POST /pam/scan
POST /pam/scan-region
POST /index/build
POST /offtarget/search
POST /offtarget/score
POST /rank
GET  /genomes
GET  /genomes/{genome_id}
GET  /cache/status
POST /cache/clear
GET  /tools
POST /sequence/gc
POST /sequence/homopolymer
POST /sequence/tm
POST /sequence/secondary-structure
POST /sequence/positional-features
POST /sequence/dinucleotide-composition
POST /sequence/seed-gc
POST /offtarget/analyze-seed
POST /sequence/cut-site
POST /score/ontarget
GET  /models
GET  /models/{model_id}
POST /models/{model_id}/setup
POST /models/{model_id}/verify
GET  /models/{model_id}/status
```

---

## 5. Comprehensive Per-Operation Specifications (Part 2)

Every operation exposed by VEYRA is fully specified below with tool identity, execution characteristics, per-argument YAML contracts, error conditions, return structures, side effects, and next logical tool calls.

---

### 5.1 Ingestion & Genome Registry Operations

#### 5.1.1 `ingest_file` / `ingest`

- **Identity**: `ingest_file` (Python) / `ingest` (Core, HTTP) / `veyra ingest` (CLI)
- **Category**: Ingestion & File Processing
- **Cost Tier**: Tier 1 (cheap to moderate depending on file size)
- **Mutating Status**: Read-only (parses file, returns summary)
- **Prerequisites**: Input file must exist at specified path

```yaml
tool: ingest_file

arguments:

  input_path:
    canonical_name: input_path
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Absolute or workspace-relative file path (.fa, .fasta, .gb, .gbk, .gff, .gff3)"
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "File must exist on disk and be a non-empty readable FASTA, GenBank, or GFF3 file"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "File not found: <input_path>"

  pam_scan:
    canonical_name: pam_scan
    type: boolean
    required: false
    default: false
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Boolean flag to trigger inline PAM scanning during file ingestion"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  pam_names:
    canonical_name: pam_names
    type: list[string]
    required: false
    default: null
    nullable: true
    allowed_values: ["SpCas9", "SaCas9", "AsCas12a", "LbCas12a", "custom"]
    minimum: null
    maximum: null
    units: null
    accepted_format: "List of PAM variant identifiers"
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Optional list of PAM names to scan when pam_scan=True"
    enforced_by: canonical validation
    conditional_requirements: "Evaluated only when pam_scan=True"
    side_effects: null
    errors: null

  output_format:
    canonical_name: output_format
    type: string
    required: false
    default: "json"
    nullable: false
    allowed_values: ["json", "tsv", "text"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Output serialization format"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null
```

- **Error behavior**: Returns `VeyraResult` with `errors=["File not found: ..."]` or invalid format message; HTTP returns 400.
- **Returned results**: `VeyraResult.summary` with file metadata, record counts, sequence length summary, and optional discovered PAM rows.
- **Side effects**: None.
- **Next logical tool**: `pam_scan`, `predict_ontarget_efficiency`, `build_offtarget_index`.

---

#### 5.1.2 `list_genomes` / `get_genomes`

- **Identity**: `get_genomes` (Python) / `list_genomes` (Core, HTTP) / `veyra genome list` (CLI)
- **Category**: Genome Registry Management
- **Cost Tier**: Tier 1 (cheap)
- **Mutating Status**: Read-only
- **Prerequisites**: None

```yaml
tool: list_genomes

arguments: {}
```

- **Error behavior**: None. Returns empty genome list if none registered.
- **Returned results**: `VeyraResult.summary["genomes"]` containing list of `GenomeInfo` objects (`genome_id`, `display_name`, `fasta_path`, `has_fai`, `has_bwa_index`).
- **Side effects**: None.
- **Next logical tool**: `genome_info`, `pam_scan_region`, `build_offtarget_index`, `offtarget_search`.

---

#### 5.1.3 `genome_info` / `get_genome_info`

- **Identity**: `get_genome_info` (Python) / `genome_info` (Core, HTTP) / `veyra genome info` (CLI)
- **Category**: Genome Registry Management
- **Cost Tier**: Tier 1 (cheap)
- **Mutating Status**: Read-only
- **Prerequisites**: `genome_id` must exist in registry

```yaml
tool: genome_info

arguments:

  genome_id:
    canonical_name: genome_id
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Registered genome identifier string (e.g. 'hg38', 'sacCer3')"
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Must match an existing registered genome in references registry"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Genome '<genome_id>' not found in registry"
```

- **Error behavior**: Returns `VeyraResult` with error message if genome is missing; HTTP 404.
- **Returned results**: `VeyraResult.summary` with genome details (`genome_id`, `display_name`, `fasta_path`, `has_fai`, `has_bwa_index`, `chromosomes`).
- **Side effects**: None.
- **Next logical tool**: `pam_scan_region`, `build_offtarget_index`, `offtarget_search`.

---

### 5.2 PAM Discovery Operations

#### 5.2.1 `pam_scan` / `pam_scan_raw`

- **Identity**: `pam_scan_raw` (Python) / `pam_scan` (Core, MCP, HTTP) / `veyra pam scan` (CLI)
- **Category**: PAM Discovery
- **Cost Tier**: Tier 1 (cheap / deterministic regex matching)
- **Mutating Status**: Read-only
- **Prerequisites**: None

```yaml
tool: pam_scan

arguments:

  sequence:
    canonical_name: sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: null
    units: "nucleotides"
    accepted_format: "Raw DNA string (IUPAC characters allowed)"
    alphabet: IUPAC
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Non-empty string containing valid IUPAC nucleotide codes (ACGTRYSWKMBDHVN)"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Sequence is empty | Invalid nucleotide characters: [...]"

  pam_pattern:
    canonical_name: pam_pattern
    type: string
    required: false
    default: "NGG"
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 10
    units: "nucleotides"
    accepted_format: "IUPAC PAM motif string"
    alphabet: IUPAC
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Non-empty string containing valid IUPAC nucleotide codes"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "PAM pattern is empty | Invalid IUPAC characters in PAM pattern: [...]"

  protospacer_len:
    canonical_name: protospacer_len
    type: integer
    required: false
    default: 20
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 100
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Integer between 1 and 100"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "protospacer_len must be 1-100, got <value>"

  strand:
    canonical_name: strand
    type: string
    required: false
    default: "both"
    nullable: false
    allowed_values: ["both", "fwd", "rev"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Must be 'both', 'fwd', or 'rev'"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Invalid strand: <strand>. Use 'both', 'fwd', or 'rev'"

  chrom:
    canonical_name: chrom
    type: string
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Chromosome name string"
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Optional label attached to output rows"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null
```

- **Error behavior**: Input errors populate `VeyraResult.errors`; HTTP returns 400.
- **Returned results**: `VeyraResult.rows` containing `ResultRow` list (with `chrom`, `start`, `end`, `strand`, `protospacer`, `pam`, `pam_type`). `VeyraResult.summary` includes `total_sites`, `forward_sites`, `reverse_sites`, `sequence_length`.
- **Side effects**: None.
- **Next logical tool**: `predict_ontarget_efficiency`, `compute_gc_content`, `compute_melting_temp`, `compute_secondary_structure`, `offtarget_search`.

---

#### 5.2.2 `pam_scan_region`

- **Identity**: `pam_scan_region` (Python, Core, MCP, HTTP) / `veyra pam scan-region` (CLI)
- **Category**: PAM Discovery
- **Cost Tier**: Tier 1 (cheap / reference FASTA lookup)
- **Mutating Status**: Read-only
- **Prerequisites**: Genome ID must exist in registry and FASTA must have `.fai` index

```yaml
tool: pam_scan_region

arguments:

  genome_id:
    canonical_name: genome_id
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Registered genome identifier"
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Must match registered genome in reference library"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Genome '<genome_id>' not found in registry"

  chrom:
    canonical_name: chrom
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Chromosome or contig identifier"
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Non-empty chromosome name present in reference FASTA"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Chromosome name is empty | Chromosome '<chrom>' not found in FASTA"

  start:
    canonical_name: start
    type: integer
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: null
    units: "1-based genomic coordinate"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: "1-based half-open [start, end)"
    validation: "Integer >= 1"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Start position must be >= 1, got <start>"

  end:
    canonical_name: end
    type: integer
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: null
    units: "1-based genomic coordinate (exclusive boundary)"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: "1-based half-open [start, end)"
    validation: "Integer >= start"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "End position (<end>) must be >= start (<start>)"

  pam_pattern:
    canonical_name: pam_pattern
    type: string
    required: false
    default: "NGG"
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 10
    units: "nucleotides"
    accepted_format: "IUPAC PAM motif"
    alphabet: IUPAC
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Valid IUPAC PAM pattern"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Invalid IUPAC characters in PAM pattern"

  protospacer_len:
    canonical_name: protospacer_len
    type: integer
    required: false
    default: 20
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 100
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Integer between 1 and 100"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "protospacer_len must be 1-100"

  strand:
    canonical_name: strand
    type: string
    required: false
    default: "both"
    nullable: false
    allowed_values: ["both", "fwd", "rev"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Must be 'both', 'fwd', or 'rev'"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Invalid strand"
```

- **Error behavior**: Invalid range, missing FASTA, or missing chromosome populates `errors`.
- **Returned results**: `VeyraResult.rows` containing discovered PAM sites in genomic range; `summary` contains region metadata.
- **Side effects**: None.
- **Next logical tool**: `predict_ontarget_efficiency`, `offtarget_search`, `compute_cut_site`.

---

### 5.3 Off-Target Search, Scoring, & Ranking Operations

#### 5.3.1 `build_offtarget_index` / `build_index`

- **Identity**: `build_offtarget_index` (Python, MCP) / `build_index` (Core) / `POST /index/build` (HTTP) / `veyra index build` (CLI)
- **Category**: Off-Target Indexing
- **Cost Tier**: Tier 2 (expensive / setup operation)
- **Mutating Status**: Mutating (writes BWA index files to disk under reference directory)
- **Prerequisites**: Genome FASTA must exist in registry

```yaml
tool: build_offtarget_index

arguments:

  genome_id:
    canonical_name: genome_id
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Registered genome identifier"
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Must exist in registered genome database"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: "Generates BWA index files (.amb, .ann, .bwt, .pac, .sa) alongside genome FASTA"
    errors: "Genome '<genome_id>' not found in registry"

  cas_variant:
    canonical_name: cas_variant
    type: string
    required: false
    default: "SpCas9"
    nullable: false
    allowed_values: ["SpCas9", "SaCas9", "AsCas12a", "LbCas12a"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Cas variant identifier for indexing context"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  force_rebuild:
    canonical_name: force_rebuild
    type: boolean
    required: false
    default: false
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "If true, overwrites existing BWA index files"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: "Deletes and rebuilds BWA index files on disk"
    errors: null
```

- **Error behavior**: FASTA missing or `bwa index` failure writes stderr to `errors`.
- **Returned results**: `VeyraResult.summary` with indexing status, output paths, and execution time.
- **Side effects**: Disk write of BWA binary index files.
- **Next logical tool**: `offtarget_search`.

---

#### 5.3.2 `offtarget_search` / `search_offtargets`

- **Identity**: `search_offtargets` (Python) / `offtarget_search` (Core, MCP, HTTP) / `veyra offtarget search` (CLI)
- **Category**: Off-Target Search
- **Cost Tier**: Tier 2 (expensive / genome-scale search)
- **Mutating Status**: Read-only (may populate disk execution cache)
- **Prerequisites**: BWA index present for genome (if `backend="bwa"`) or Cas-OFFinder binary available (if `backend="cas_offinder"`)

```yaml
tool: offtarget_search

arguments:

  spacer_sequence:
    canonical_name: spacer_sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 15
    maximum: 30
    units: "nucleotides"
    accepted_format: "DNA sequence string"
    alphabet: ACGT
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Valid DNA sequence matching guide/spacer length"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Invalid nucleotide characters: [...]"

  genome_id:
    canonical_name: genome_id
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Registered genome identifier"
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Must match registered genome in reference library"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Genome '<genome_id>' not found in registry | No BWA index for <genome_id>"

  pam_pattern:
    canonical_name: pam_pattern
    type: string
    required: false
    default: "NGG"
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 10
    units: "nucleotides"
    accepted_format: "IUPAC PAM pattern string"
    alphabet: IUPAC
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Valid IUPAC PAM pattern"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Invalid IUPAC characters in PAM pattern"

  max_mismatches:
    canonical_name: max_mismatches
    type: integer
    required: false
    default: 4
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 10
    units: "mismatches"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Integer between 0 and 10"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "max_mismatches must be 0-10, got <max_mismatches>"

  allow_bulge:
    canonical_name: allow_bulge
    type: boolean
    required: false
    default: false
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "If true, requires backend='cas_offinder'"
    enforced_by: canonical validation
    conditional_requirements: "If true and backend='bwa', triggers validation failure"
    side_effects: null
    errors: "BWA backend does not support bulge detection. Use backend='cas_offinder'."

  cas_variant:
    canonical_name: cas_variant
    type: string
    required: false
    default: "SpCas9"
    nullable: false
    allowed_values: ["SpCas9", "SaCas9", "AsCas12a", "LbCas12a"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Cas variant identifier"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  backend:
    canonical_name: backend
    type: string
    required: false
    default: "bwa"
    nullable: false
    allowed_values: ["bwa", "cas_offinder"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Must be 'bwa' or 'cas_offinder'"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "backend must be 'bwa' or 'cas_offinder', got '<backend>'"

  max_dna_bulge:
    canonical_name: max_dna_bulge
    type: integer
    required: false
    default: 0
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 5
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Integer 0-5 (effective when backend='cas_offinder')"
    enforced_by: canonical validation
    conditional_requirements: "Used when backend='cas_offinder' and allow_bulge=True"
    side_effects: null
    errors: "max_dna_bulge must be 0-5, got <max_dna_bulge>"

  max_rna_bulge:
    canonical_name: max_rna_bulge
    type: integer
    required: false
    default: 0
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 5
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Integer 0-5 (effective when backend='cas_offinder')"
    enforced_by: canonical validation
    conditional_requirements: "Used when backend='cas_offinder' and allow_bulge=True"
    side_effects: null
    errors: "max_rna_bulge must be 0-5, got <max_rna_bulge>"

  search_scope:
    canonical_name: search_scope
    type: string
    required: false
    default: "genome"
    nullable: false
    allowed_values: ["genome", "region"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Must be 'genome' or 'region'"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "search_scope must be 'genome' or 'region', got '<search_scope>'"

  chrom:
    canonical_name: chrom
    type: string
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Chromosome name string"
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Required when search_scope='region'"
    enforced_by: canonical validation
    conditional_requirements: "Required when search_scope='region'"
    side_effects: null
    errors: "chrom, start, and end are required when search_scope='region'"

  start:
    canonical_name: start
    type: integer
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: 1
    maximum: null
    units: "1-based genomic coordinate"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: "1-based half-open [start, end)"
    validation: "Required when search_scope='region'; must be >= 1"
    enforced_by: canonical validation
    conditional_requirements: "Required when search_scope='region'"
    side_effects: null
    errors: "invalid region coordinates: <chrom>:<start>-<end>"

  end:
    canonical_name: end
    type: integer
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: 1
    maximum: null
    units: "1-based genomic coordinate"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: "1-based half-open [start, end)"
    validation: "Required when search_scope='region'; must be > start"
    enforced_by: canonical validation
    conditional_requirements: "Required when search_scope='region'"
    side_effects: null
    errors: "invalid region coordinates: <chrom>:<start>-<end>"

  strand_search:
    canonical_name: strand_search
    type: string
    required: false
    default: "both"
    nullable: false
    allowed_values: ["both", "fwd", "rev"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Filter results by strand"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "strand_search must be 'both', 'fwd', or 'rev', got '<strand_search>'"

  max_results:
    canonical_name: max_results
    type: integer
    required: false
    default: 1000
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 100000
    units: "candidate rows"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Integer >= 1"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "max_results must be >= 1, got <max_results>"

  device:
    canonical_name: device
    type: string
    required: false
    default: "auto"
    nullable: false
    allowed_values: ["auto", "cpu"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Execution device ('auto' or 'cpu'); 'gpu' is rejected"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "device must be 'cpu' or 'auto', got '<device>'"
```

- **Error behavior**: Validation errors or missing index populate `errors`; HTTP 400.
- **Returned results**: `VeyraResult.rows` containing off-target candidate rows (`chrom`, `start`, `end`, `strand`, `protospacer`, `pam`, `mismatch_count`, `mismatch_positions`, `bulge_type`, `bulge_size`); `summary` includes `total_candidates`, `mismatch_distribution`, `results_truncated`.
- **Side effects**: Temporary alignment file creation during execution.
- **Next logical tool**: `score_offtargets_cfd`, `analyze_mismatch_seed`, `rank_guides`.

---

#### 5.3.3 `cas_offinder_search`

- **Identity**: `cas_offinder_search` (MCP tool, direct module import) / invoked via `offtarget_search(..., backend="cas_offinder")`
- **Category**: Off-Target Search (Bulge-aware)
- **Cost Tier**: Tier 2 (expensive / genome-scale OpenCL search)
- **Mutating Status**: Read-only (writes temporary input/output files)
- **Prerequisites**: Built Cas-OFFinder 3.0.0 binary at `data/tools/cas-offinder/build/cas-offinder` and POCL OpenCL runtime

```yaml
tool: cas_offinder_search

arguments:

  spacer_sequence:
    canonical_name: spacer_sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 15
    maximum: 30
    units: "nucleotides"
    accepted_format: "DNA sequence string"
    alphabet: ACGT
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Valid DNA sequence"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Invalid nucleotide characters"

  genome_id:
    canonical_name: genome_id
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Registered genome identifier"
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Must match registered genome"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Genome '<genome_id>' not found in registry"

  pam_pattern:
    canonical_name: pam_pattern
    type: string
    required: false
    default: "NGG"
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 10
    units: "nucleotides"
    accepted_format: "IUPAC PAM pattern"
    alphabet: IUPAC
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Valid IUPAC pattern"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Invalid IUPAC characters in PAM pattern"

  max_mismatches:
    canonical_name: max_mismatches
    type: integer
    required: false
    default: 4
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 10
    units: "mismatches"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Integer 0-10"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "max_mismatches must be 0-10, got <max_mismatches>"

  max_dna_bulge:
    canonical_name: max_dna_bulge
    type: integer
    required: false
    default: 1
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 5
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Integer 0-5"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "max_dna_bulge must be 0-5, got <max_dna_bulge>"

  max_rna_bulge:
    canonical_name: max_rna_bulge
    type: integer
    required: false
    default: 1
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 5
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Integer 0-5"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "max_rna_bulge must be 0-5, got <max_rna_bulge>"

  search_scope:
    canonical_name: search_scope
    type: string
    required: false
    default: "genome"
    nullable: false
    allowed_values: ["genome", "region"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Scope of search"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "search_scope must be 'genome' or 'region', got '<search_scope>'"

  chrom:
    canonical_name: chrom
    type: string
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Chromosome name"
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Required when search_scope='region'"
    enforced_by: canonical validation
    conditional_requirements: "Required when search_scope='region'"
    side_effects: null
    errors: "chrom is required when search_scope='region'"

  start:
    canonical_name: start
    type: integer
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: 1
    maximum: null
    units: "1-based genomic coordinate"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: "1-based half-open [start, end)"
    validation: "Required when search_scope='region'; must be >= 1"
    enforced_by: canonical validation
    conditional_requirements: "Required when search_scope='region'"
    side_effects: null
    errors: "start must be >= 1, got <start>"

  end:
    canonical_name: end
    type: integer
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: 1
    maximum: null
    units: "1-based genomic coordinate"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: "1-based half-open [start, end)"
    validation: "Required when search_scope='region'; must be > start"
    enforced_by: canonical validation
    conditional_requirements: "Required when search_scope='region'"
    side_effects: null
    errors: "end (<end>) must be > start (<start>)"

  cas_variant:
    canonical_name: cas_variant
    type: string
    required: false
    default: "SpCas9"
    nullable: false
    allowed_values: ["SpCas9", "SaCas9", "AsCas12a", "LbCas12a"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Cas variant identifier"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  strand_search:
    canonical_name: strand_search
    type: string
    required: false
    default: "both"
    nullable: false
    allowed_values: ["both", "fwd", "rev"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Filter by strand"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "strand_search must be 'both', 'fwd', or 'rev', got '<strand_search>'"

  max_results:
    canonical_name: max_results
    type: integer
    required: false
    default: 1000
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 100000
    units: "candidate rows"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Integer >= 1"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "max_results must be >= 1, got <max_results>"
```

- **Error behavior**: Binary missing or OpenCL runtime failure writes stderr details to `errors`.
- **Returned results**: `VeyraResult.rows` containing bulged alignment rows (`aligned_guide`, `aligned_candidate`, `bulge_type`, `bulge_size`, `cfd_status`); `summary` includes `bulge_distribution`, `opencl_runtime`.
- **Side effects**: Temporary input and output files created in system tempdir during execution; POCL kernel cache saved under `cache/pocl`.
- **Next logical tool**: `score_offtargets_cfd`, `analyze_mismatch_seed`, `rank_guides`.

---

#### 5.3.4 `score_offtargets_cfd` / `score_offtargets`

- **Identity**: `score_offtargets_cfd` (Python) / `score_offtargets` (Core, MCP, HTTP) / `veyra offtarget score` (CLI)
- **Category**: Off-Target Scoring
- **Cost Tier**: Tier 2 (moderate / deterministic matrix scoring)
- **Mutating Status**: Read-only
- **Prerequisites**: List of candidate off-target dicts from `offtarget_search` or `cas_offinder_search`

```yaml
tool: score_offtargets

arguments:

  spacer_sequence:
    canonical_name: spacer_sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 15
    maximum: 30
    units: "nucleotides"
    accepted_format: "Wild-type spacer sequence string"
    alphabet: ACGT
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Valid DNA sequence matching wild-type spacer"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Invalid nucleotide characters"

  candidates:
    canonical_name: candidates
    type: list[dict]
    required: true
    default: []
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 100000
    units: "candidate dicts"
    accepted_format: "JSON array of candidate objects containing protospacer/mismatch info"
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "List of candidate dictionary objects"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  pam_pattern:
    canonical_name: pam_pattern
    type: string
    required: false
    default: "NGG"
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 10
    units: "nucleotides"
    accepted_format: "IUPAC PAM motif"
    alphabet: IUPAC
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Valid IUPAC pattern"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null
```

- **Error behavior**: Invalid spacer sequence populates `errors`. Bulged candidates are flagged with `cfd_status="unsupported_bulge"`.
- **Returned results**: `VeyraResult.rows` with calculated `cfd_score` (0.0 to 1.0, lower is generally more specific); `summary` includes `mean_cfd`, `min_cfd`, `total_cfd_score`, `scored_candidates_count`.
- **Side effects**: None.
- **Next logical tool**: `rank_guides`.

---

#### 5.3.5 `rank_guides` / `rank_candidates`

- **Identity**: `rank_guides` (Python) / `rank_candidates` (Core, MCP, HTTP) / `veyra rank` (CLI)
- **Category**: Guide Ranking
- **Cost Tier**: Tier 2 (moderate / aggregation & sorting)
- **Mutating Status**: Read-only
- **Prerequisites**: Candidate guide objects with off-target or on-target score dictionaries

```yaml
tool: rank_candidates

arguments:

  guides:
    canonical_name: guides
    type: list[dict]
    required: true
    default: []
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 10000
    units: "guide dicts"
    accepted_format: "JSON array of guide candidate dictionaries"
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "List of guide dictionaries containing sequence/location fields"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  off_targets:
    canonical_name: off_targets
    type: list[dict]
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: null
    maximum: null
    units: "off-target dicts"
    accepted_format: "JSON array of scored off-target candidate objects"
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Optional off-target hits associated with guides"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  on_target_scores:
    canonical_name: on_target_scores
    type: dict
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Dict mapping guide sequence string -> float score"
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Optional mapping of guide sequence to on-target efficiency score"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  sort_by:
    canonical_name: sort_by
    type: string
    required: false
    default: "composite"
    nullable: false
    allowed_values: ["composite", "offtarget", "ontarget"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Ranking criterion"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Invalid sort_by option"
```

- **Error behavior**: Missing guides list or invalid sort option populates `errors`.
- **Returned results**: `VeyraResult.summary["ranked_guides"]` containing sorted list of guide objects with rank metrics and composite score breakdown.
- **Side effects**: None.
- **Next logical tool**: Output serialization / decision reporting.

---

#### 5.3.6 `analyze_mismatch_seed`

- **Identity**: `analyze_mismatch_seed` (Python, MCP, HTTP)
- **Category**: Off-Target Analysis
- **Cost Tier**: Tier 1 (cheap / deterministic alignment parsing)
- **Mutating Status**: Read-only
- **Prerequisites**: Alignment strings or candidate sequences from off-target search

```yaml
tool: analyze_mismatch_seed

arguments:

  spacer_sequence:
    canonical_name: spacer_sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 15
    maximum: 30
    units: "nucleotides"
    accepted_format: "Wild-type spacer sequence string"
    alphabet: ACGT
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Valid DNA sequence"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Sequence is empty | Invalid nucleotide characters"

  candidate_sequence:
    canonical_name: candidate_sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 15
    maximum: 35
    units: "nucleotides"
    accepted_format: "Off-target candidate sequence string"
    alphabet: ACGT
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Valid DNA sequence"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Sequence is empty | Invalid nucleotide characters"

  bulge_type:
    canonical_name: bulge_type
    type: string
    required: false
    default: "X"
    nullable: false
    allowed_values: ["X", "DNA", "RNA"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: uppercased
    coordinate_system: null
    validation: "Must be 'X' (no bulge), 'DNA', or 'RNA'"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "bulge_type must be 'X', 'DNA', or 'RNA', got '<bulge_type>'"

  bulge_size:
    canonical_name: bulge_size
    type: integer
    required: false
    default: 0
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 5
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Integer >= 0"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "bulge_size must be >= 0, got <bulge_size>"

  bulge_position:
    canonical_name: bulge_position
    type: integer
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: 0
    maximum: 35
    units: "0-based alignment index"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: "0-based alignment position"
    validation: "Optional 0-based index of bulge position in alignment"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  aligned_guide:
    canonical_name: aligned_guide
    type: string
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Aligned guide sequence string with gap characters '-'"
    alphabet: "ACGT-"
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Optional gap-aligned guide string from Cas-OFFinder"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  aligned_candidate:
    canonical_name: aligned_candidate
    type: string
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Aligned candidate sequence string with gap characters '-'"
    alphabet: "ACGTacgt-"
    normalization: stripped
    coordinate_system: null
    validation: "Optional gap-aligned candidate string (lowercase indicates mismatch)"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  seed_region_length:
    canonical_name: seed_region_length
    type: integer
    required: false
    default: 10
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 20
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Integer between 1 and length of spacer"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "seed_region_length must be 1-<spacer_len>, got <seed_region_length>"

  pam_pattern:
    canonical_name: pam_pattern
    type: string
    required: false
    default: "NGG"
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 10
    units: "nucleotides"
    accepted_format: "IUPAC PAM pattern"
    alphabet: IUPAC
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Valid IUPAC pattern"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null
```

- **Error behavior**: Invalid sequence or out-of-range seed length populates `errors`.
- **Returned results**: `VeyraResult.summary` with `seed_mismatch_count`, `distal_mismatch_count`, `has_seed_mismatch`, `bulge_in_seed`, `mismatch_positions_0based`, `events`.
- **Side effects**: None.
- **Next logical tool**: `score_offtargets_cfd`, `rank_guides`.

---

### 5.4 Sequence Feature Extraction Operations

#### 5.4.1 `compute_gc_content`

- **Identity**: `compute_gc_content` (Python, Core, MCP, HTTP) / `veyra sequence gc` (CLI)
- **Category**: Sequence Feature Analysis
- **Cost Tier**: Tier 1 (cheap / deterministic)
- **Mutating Status**: Read-only
- **Prerequisites**: None

```yaml
tool: compute_gc_content

arguments:

  sequence:
    canonical_name: sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 10000
    units: "nucleotides"
    accepted_format: "DNA sequence string (IUPAC allowed)"
    alphabet: IUPAC
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Non-empty DNA sequence string"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Sequence is empty | Invalid nucleotide characters"

  gc_window_size:
    canonical_name: gc_window_size
    type: integer
    required: false
    default: 5
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 100
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Sliding window size in nucleotides"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  gc_split_ratio:
    canonical_name: gc_split_ratio
    type: float
    required: false
    default: 0.5
    nullable: false
    allowed_values: null
    minimum: 0.0
    maximum: 1.0
    units: "fraction"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Fraction of sequence allocated to 5' half"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  gc_min_threshold:
    canonical_name: gc_min_threshold
    type: float
    required: false
    default: 0.20
    nullable: false
    allowed_values: null
    minimum: 0.0
    maximum: 1.0
    units: "fraction"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Minimum GC content for pass filter"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  gc_max_threshold:
    canonical_name: gc_max_threshold
    type: float
    required: false
    default: 0.80
    nullable: false
    allowed_values: null
    minimum: 0.0
    maximum: 1.0
    units: "fraction"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Maximum GC content for pass filter"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  include_sliding_window:
    canonical_name: include_sliding_window
    type: boolean
    required: false
    default: true
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Whether to compute sliding-window GC profile"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  include_half_split:
    canonical_name: include_half_split
    type: boolean
    required: false
    default: true
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Whether to compute 5'/3' split GC content"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  round_decimals:
    canonical_name: round_decimals
    type: integer
    required: false
    default: 3
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 6
    units: "decimal places"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Decimal places for output rounding"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null
```

- **Error behavior**: Invalid sequence populates `errors`.
- **Returned results**: `VeyraResult.summary` with `gc_content`, `gc_5prime`, `gc_3prime`, `passes_filter`, `sliding_window_gc`.
- **Side effects**: None.
- **Next logical tool**: `predict_ontarget_efficiency`, `rank_guides`.

---

#### 5.4.2 `check_homopolymer_runs`

- **Identity**: `check_homopolymer_runs` (Python, Core, MCP, HTTP) / `veyra sequence homopolymer` (CLI)
- **Category**: Sequence Feature Analysis
- **Cost Tier**: Tier 1 (cheap / deterministic)
- **Mutating Status**: Read-only
- **Prerequisites**: None

```yaml
tool: check_homopolymer_runs

arguments:

  sequence:
    canonical_name: sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 10000
    units: "nucleotides"
    accepted_format: "DNA sequence string"
    alphabet: IUPAC
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Non-empty DNA sequence string"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Sequence is empty | Invalid nucleotide characters"

  homopolymer_min_run:
    canonical_name: homopolymer_min_run
    type: integer
    required: false
    default: 4
    nullable: false
    allowed_values: null
    minimum: 2
    maximum: 20
    units: "consecutive nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Minimum consecutive run length to flag (>= 2)"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  polyT_strict:
    canonical_name: polyT_strict
    type: boolean
    required: false
    default: true
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "If true, poly-T runs (>= min_run) set passes_filter=False (Pol III terminator risk)"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  polyG_strict:
    canonical_name: polyG_strict
    type: boolean
    required: false
    default: false
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "If true, poly-G runs set passes_filter=False"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  check_bases:
    canonical_name: check_bases
    type: string
    required: false
    default: "ACGT"
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 4
    units: null
    accepted_format: "Subset string of ACGT"
    alphabet: ACGT
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Bases to scan for runs"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  return_run_positions:
    canonical_name: return_run_positions
    type: boolean
    required: false
    default: false
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Whether to include detailed run start/end positions"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null
```

- **Error behavior**: Invalid sequence populates `errors`.
- **Returned results**: `VeyraResult.summary` with `has_homopolymer_run`, `max_run_length`, `passes_filter`, `polyT_run_detected`, `run_details`.
- **Side effects**: None.
- **Next logical tool**: `rank_guides`.

---

#### 5.4.3 `compute_melting_temp`

- **Identity**: `compute_melting_temp` (Python, Core, MCP, HTTP) / `veyra sequence tm` (CLI)
- **Category**: Sequence Feature Analysis
- **Cost Tier**: Tier 1 (cheap / deterministic thermodynamic calculation)
- **Mutating Status**: Read-only
- **Prerequisites**: None

```yaml
tool: compute_melting_temp

arguments:

  sequence:
    canonical_name: sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 1000
    units: "nucleotides"
    accepted_format: "Standard DNA sequence string"
    alphabet: ACGT
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Non-empty ACGT DNA string"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Sequence is empty | Invalid nucleotide characters"

  tm_method:
    canonical_name: tm_method
    type: string
    required: false
    default: "nearest_neighbor"
    nullable: false
    allowed_values: ["nearest_neighbor", "wallace", "gc_percent"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Method for duplex Tm calculation"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Invalid tm_method"

  na_conc:
    canonical_name: na_conc
    type: float
    required: false
    default: 50.0
    nullable: false
    allowed_values: null
    minimum: 0.0
    maximum: 5000.0
    units: "mM"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Sodium ion concentration in mM"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  mg_conc:
    canonical_name: mg_conc
    type: float
    required: false
    default: 0.0
    nullable: false
    allowed_values: null
    minimum: 0.0
    maximum: 500.0
    units: "mM"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Magnesium ion concentration in mM"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  primer_conc:
    canonical_name: primer_conc
    type: float
    required: false
    default: 250.0
    nullable: false
    allowed_values: null
    minimum: 0.1
    maximum: 10000.0
    units: "nM"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Primer concentration in nM"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  seed_region_length:
    canonical_name: seed_region_length
    type: integer
    required: false
    default: 10
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 20
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Length of seed region for optional seed Tm"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  compute_seed_tm:
    canonical_name: compute_seed_tm
    type: boolean
    required: false
    default: false
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Whether to calculate seed region Tm separately"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  round_decimals:
    canonical_name: round_decimals
    type: integer
    required: false
    default: 2
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 6
    units: "decimal places"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Decimal places for rounding"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null
```

- **Error behavior**: Invalid sequence populates `errors`.
- **Returned results**: `VeyraResult.summary` with `melting_temperature_celsius`, `tm_method`, `seed_melting_temperature_celsius`.
- **Side effects**: None.
- **Next logical tool**: `predict_ontarget_efficiency`, `rank_guides`.

---

#### 5.4.4 `compute_secondary_structure`

- **Identity**: `compute_secondary_structure` (Python, Core, MCP, HTTP) / `veyra sequence secondary-structure` (CLI)
- **Category**: Sequence Feature Analysis
- **Cost Tier**: Tier 1 (moderate / deterministic folding calculation)
- **Mutating Status**: Read-only
- **Prerequisites**: ViennaRNA / RNAfold optional (uses heuristic fallback if absent)

```yaml
tool: compute_secondary_structure

arguments:

  sequence:
    canonical_name: sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 500
    units: "nucleotides"
    accepted_format: "DNA sequence string"
    alphabet: ACGT
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Non-empty ACGT DNA string"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Sequence is empty | Invalid nucleotide characters"

  mfe_include_scaffold:
    canonical_name: mfe_include_scaffold
    type: boolean
    required: false
    default: false
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "If true, folds guide + scaffold sequence together"
    enforced_by: canonical validation
    conditional_requirements: "If true, scaffold_sequence must non-empty"
    side_effects: null
    errors: "scaffold_sequence is required when mfe_include_scaffold=True"

  scaffold_sequence:
    canonical_name: scaffold_sequence
    type: string
    required: false
    default: ""
    nullable: false
    allowed_values: null
    minimum: null
    maximum: 200
    units: "nucleotides"
    accepted_format: "RNA/DNA scaffold sequence string"
    alphabet: ACGTU
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Scaffold sequence string"
    enforced_by: canonical validation
    conditional_requirements: "Required when mfe_include_scaffold=True"
    side_effects: null
    errors: "scaffold_sequence is required when mfe_include_scaffold=True"

  temperature_celsius:
    canonical_name: temperature_celsius
    type: float
    required: false
    default: 37.0
    nullable: false
    allowed_values: null
    minimum: 0.0
    maximum: 100.0
    units: "°C"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Folding temperature in °C"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  return_structure_string:
    canonical_name: return_structure_string
    type: boolean
    required: false
    default: false
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Whether to include dot-bracket structure string"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  mfe_threshold:
    canonical_name: mfe_threshold
    type: float
    required: false
    default: -5.0
    nullable: false
    allowed_values: null
    minimum: -100.0
    maximum: 0.0
    units: "kcal/mol"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "MFE threshold for passes_filter determination"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null
```

- **Error behavior**: Missing scaffold when required or invalid sequence populates `errors`.
- **Returned results**: `VeyraResult.summary` with `mfe_kcal_mol`, `structure_dot_bracket`, `passes_filter`, `vienna_available`.
- **Side effects**: None.
- **Next logical tool**: `predict_ontarget_efficiency`, `rank_guides`.

---

#### 5.4.5 `compute_positional_features`

- **Identity**: `compute_positional_features` (Python, Core, MCP, HTTP) / `veyra sequence positional-features` (CLI)
- **Category**: Sequence Feature Analysis
- **Cost Tier**: Tier 1 (cheap / deterministic)
- **Mutating Status**: Read-only
- **Prerequisites**: None

```yaml
tool: compute_positional_features

arguments:

  sequence:
    canonical_name: sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 15
    maximum: 30
    units: "nucleotides"
    accepted_format: "Spacer sequence in scoring orientation"
    alphabet: ACGT
    normalization: stripped + uppercased
    coordinate_system: "1-based biological positions (1 = 5' end)"
    validation: "Non-empty DNA sequence"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Sequence is empty | Invalid nucleotide characters"

  spacer_length:
    canonical_name: spacer_length
    type: integer
    required: false
    default: 20
    nullable: false
    allowed_values: null
    minimum: 15
    maximum: 30
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Expected spacer length"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  return_onehot:
    canonical_name: return_onehot
    type: boolean
    required: false
    default: true
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Whether to return per-position one-hot encoding array"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  check_position20_bias:
    canonical_name: check_position20_bias
    type: boolean
    required: false
    default: true
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Check position 20 G/C bias (PAM-proximal requirement)"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  custom_check_positions:
    canonical_name: custom_check_positions
    type: list[int]
    required: false
    default: []
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 30
    units: "1-based positions"
    accepted_format: "JSON array of integers"
    alphabet: null
    normalization: null
    coordinate_system: "1-based biological positions"
    validation: "List of 1-based positions to extract"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  onehot_alphabet:
    canonical_name: onehot_alphabet
    type: string
    required: false
    default: "ACGT"
    nullable: false
    allowed_values: null
    minimum: 4
    maximum: 4
    units: null
    accepted_format: "4-character alphabet string"
    alphabet: ACGT
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Alphabet for one-hot encoding"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null
```

- **Error behavior**: Invalid sequence populates `errors`.
- **Returned results**: `VeyraResult.summary` with `positional_nucleotides`, `onehot_encoding`, `pos20_base`, `pos20_bias_favorable`.
- **Side effects**: None.
- **Next logical tool**: `predict_ontarget_efficiency`.

---

#### 5.4.6 `compute_dinucleotide_composition`

- **Identity**: `compute_dinucleotide_composition` (Python, Core, MCP, HTTP) / `veyra sequence dinucleotide-composition` (CLI)
- **Category**: Sequence Feature Analysis
- **Cost Tier**: Tier 1 (cheap / deterministic)
- **Mutating Status**: Read-only
- **Prerequisites**: None

```yaml
tool: compute_dinucleotide_composition

arguments:

  sequence:
    canonical_name: sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 15
    maximum: 30
    units: "nucleotides"
    accepted_format: "Spacer sequence string"
    alphabet: ACGT
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Non-empty DNA sequence"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Sequence is empty | Invalid nucleotide characters"

  spacer_length:
    canonical_name: spacer_length
    type: integer
    required: false
    default: 20
    nullable: false
    allowed_values: null
    minimum: 15
    maximum: 30
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Expected spacer length"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  window_size:
    canonical_name: window_size
    type: integer
    required: false
    default: 2
    nullable: false
    allowed_values: null
    minimum: 2
    maximum: 4
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "k-mer window size (default 2 for dinucleotides)"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  return_full_matrix:
    canonical_name: return_full_matrix
    type: boolean
    required: false
    default: false
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Whether to return full position-anchored dinucleotide matrix"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  normalize_counts:
    canonical_name: normalize_counts
    type: boolean
    required: false
    default: false
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Whether to return normalized dinucleotide frequencies"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  target_dinucleotides:
    canonical_name: target_dinucleotides
    type: list[string]
    required: false
    default: []
    nullable: false
    allowed_values: null
    minimum: null
    maximum: 16
    units: null
    accepted_format: "JSON array of 2-character strings (e.g. ['GC', 'GG'])"
    alphabet: ACGT
    normalization: uppercased
    coordinate_system: null
    validation: "Optional subset of dinucleotides to filter"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null
```

- **Error behavior**: Invalid sequence populates `errors`.
- **Returned results**: `VeyraResult.summary` with `dinucleotide_counts`, `dinucleotide_frequencies`, `matrix`.
- **Side effects**: None.
- **Next logical tool**: `predict_ontarget_efficiency`.

---

#### 5.4.7 `compute_seed_gc`

- **Identity**: `compute_seed_gc` (Python, Core, MCP, HTTP) / `veyra sequence seed-gc` (CLI)
- **Category**: Sequence Feature Analysis
- **Cost Tier**: Tier 1 (cheap / deterministic)
- **Mutating Status**: Read-only
- **Prerequisites**: None

```yaml
tool: compute_seed_gc

arguments:

  sequence:
    canonical_name: sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 15
    maximum: 30
    units: "nucleotides"
    accepted_format: "Spacer sequence string"
    alphabet: ACGT
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Non-empty DNA sequence"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Sequence is empty | Invalid nucleotide characters"

  seed_region_length:
    canonical_name: seed_region_length
    type: integer
    required: false
    default: 10
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 20
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Length of seed region"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  seed_anchor:
    canonical_name: seed_anchor
    type: string
    required: false
    default: "pam_proximal"
    nullable: false
    allowed_values: ["pam_proximal"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Anchor orientation for seed extraction"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  seed_min_threshold:
    canonical_name: seed_min_threshold
    type: float
    required: false
    default: 0.20
    nullable: false
    allowed_values: null
    minimum: 0.0
    maximum: 1.0
    units: "fraction"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Minimum seed GC fraction for pass filter"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  seed_max_threshold:
    canonical_name: seed_max_threshold
    type: float
    required: false
    default: 0.80
    nullable: false
    allowed_values: null
    minimum: 0.0
    maximum: 1.0
    units: "fraction"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Maximum seed GC fraction for pass filter"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  compute_seed_distal_delta:
    canonical_name: compute_seed_distal_delta
    type: boolean
    required: false
    default: false
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Whether to calculate distal GC fraction and seed-distal GC delta"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  round_decimals:
    canonical_name: round_decimals
    type: integer
    required: false
    default: 3
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 6
    units: "decimal places"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Decimal places for rounding"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null
```

- **Error behavior**: Invalid sequence populates `errors`.
- **Returned results**: `VeyraResult.summary` with `seed_gc_content`, `distal_gc_content`, `seed_distal_delta`, `passes_filter`.
- **Side effects**: None.
- **Next logical tool**: `predict_ontarget_efficiency`, `rank_guides`.

---

### 5.5 Cleavage Site & Geometry Operations

#### 5.5.1 `compute_cut_site`

- **Identity**: `compute_cut_site` (Python, Core, MCP, HTTP) / `veyra sequence cut-site` (CLI)
- **Category**: Coordinate & Geometry Analysis
- **Cost Tier**: Tier 1 (cheap / deterministic coordinate transformation)
- **Mutating Status**: Read-only
- **Prerequisites**: Protospacer start coordinate

```yaml
tool: compute_cut_site

arguments:

  spacer_start:
    canonical_name: spacer_start
    type: integer
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: null
    units: "0-based genomic coordinate"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: "0-based half-open [start, end)"
    validation: "Non-negative integer representing 0-based start coordinate of protospacer"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "spacer_start must be a non-negative integer, got <spacer_start>"

  spacer_length:
    canonical_name: spacer_length
    type: integer
    required: false
    default: 20
    nullable: false
    allowed_values: null
    minimum: 1
    maximum: 50
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Positive integer spacer length"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "spacer_length must be a positive integer, got <spacer_length>"

  strand:
    canonical_name: strand
    type: string
    required: false
    default: "+"
    nullable: false
    allowed_values: ["+", "-"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Must be '+' or '-'"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "strand must be '+' or '-', got '<strand>'"

  pam_position:
    canonical_name: pam_position
    type: string
    required: false
    default: "3prime"
    nullable: false
    allowed_values: ["3prime"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Must be '3prime' (only SpCas9 currently supported)"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "pam_position must be '3prime' (only SpCas9 supported), got '<pam_position>'"

  cut_offset_from_pam:
    canonical_name: cut_offset_from_pam
    type: integer
    required: false
    default: -3
    nullable: false
    allowed_values: null
    minimum: -20
    maximum: 0
    units: "base pairs from PAM start"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Integer offset from PAM start (canonical SpCas9 default is -3)"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "cut_offset_from_pam must be an integer, got <offset>"

  return_genomic_coord:
    canonical_name: return_genomic_coord
    type: boolean
    required: false
    default: true
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Whether to calculate absolute genomic coordinate"
    enforced_by: canonical validation
    conditional_requirements: "When true, chrom parameter is required"
    side_effects: null
    errors: "chrom is required when return_genomic_coord=True"

  return_relative_coord:
    canonical_name: return_relative_coord
    type: boolean
    required: false
    default: true
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Whether to calculate spacer-relative cut position"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  chrom:
    canonical_name: chrom
    type: string
    required: false
    default: ""
    nullable: false
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Chromosome name string"
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Required when return_genomic_coord=True"
    enforced_by: canonical validation
    conditional_requirements: "Required when return_genomic_coord=True"
    side_effects: null
    errors: "chrom is required when return_genomic_coord=True"
```

- **Error behavior**: Negative `spacer_start` or missing `chrom` populates `errors`.
- **Returned results**: `VeyraResult.summary` with `cut_site_genomic`, `cut_site_relative`, `cut_site_relative_boundary`, `relative_coordinate_semantics`.
- **Side effects**: None.
- **Next logical tool**: Output reporting / genomic feature intersection.

---

### 5.6 On-Target Efficiency Prediction Operations

#### 5.6.1 `predict_ontarget_efficiency`

- **Identity**: `predict_ontarget_efficiency` (Python, Core, MCP, HTTP) / `veyra score on-target` (CLI)
- **Category**: On-Target Efficiency Prediction
- **Cost Tier**: Tier 1 (cheap / deterministic model inference)
- **Mutating Status**: Read-only
- **Prerequisites**: Model runtime provisioned and verified (for `rule_set_2` / `rule_set_3`). Auto mode selects highest priority verified model.

```yaml
tool: predict_ontarget_efficiency

arguments:

  context_sequence:
    canonical_name: context_sequence
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: null
    minimum: 30
    maximum: 50
    units: "nucleotides"
    accepted_format: "Full context DNA string (upstream + spacer + PAM + downstream)"
    alphabet: ACGT
    normalization: stripped + uppercased
    coordinate_system: null
    validation: "Must match context length (upstream + spacer_length + pam_len + downstream, default 30 nt: 4 up + 20 spacer + 3 PAM + 3 down)"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Invalid context_sequence: [...] | Context length mismatch: expected 30 nt (...), got <len> nt"

  model:
    canonical_name: model
    type: string
    required: false
    default: "auto"
    nullable: false
    allowed_values: ["auto", "both", "rule_set_3", "rule_set_2", "doench_2014"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Model selection strategy ('both' is an alias for 'auto')"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Model '<model>' is not available: [...] | No verified on-target model available"

  context_upstream:
    canonical_name: context_upstream
    type: integer
    required: false
    default: 4
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 20
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Nucleotides upstream of spacer (default 4)"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  context_downstream:
    canonical_name: context_downstream
    type: integer
    required: false
    default: 3
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 20
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Nucleotides downstream of PAM (default 3)"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  spacer_length:
    canonical_name: spacer_length
    type: integer
    required: false
    default: 20
    nullable: false
    allowed_values: null
    minimum: 15
    maximum: 30
    units: "nucleotides"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Spacer length (default 20 for SpCas9)"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  normalize_score:
    canonical_name: normalize_score
    type: boolean
    required: false
    default: false
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Whether to normalize output score to [0,1]. Rule Set 3 emits warning (native activity scale)"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  round_decimals:
    canonical_name: round_decimals
    type: integer
    required: false
    default: 3
    nullable: false
    allowed_values: null
    minimum: 0
    maximum: 6
    units: "decimal places"
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Decimal places for output rounding"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null

  precomputed_features:
    canonical_name: precomputed_features
    type: dict
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: "Dictionary of precomputed sequence feature arrays"
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "Optional feature dictionary to bypass featurization step"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null
```

- **Error behavior**: Sequence mismatch or unavailable explicit model populates `errors` with `confidence_flag="model_unavailable"`.
- **Returned results**: `VeyraResult.summary` with `ontarget_score`, `raw_score`, `model_used`, `model_source`, `selection_status`, `fallback_used`, `confidence_flag`.
- **Side effects**: None (does NOT provision runtimes implicitly).
- **Next logical tool**: `rank_guides`.

---

### 5.7 Model Runtime & Lifecycle Operations

#### 5.7.1 `list_model_runtimes` / `models_list_runtimes`

- **Identity**: `list_model_runtimes` (Python) / `models_list_runtimes` (MCP) / `GET /models` (HTTP) / `veyra models list` (CLI)
- **Category**: Model Runtime Management
- **Cost Tier**: Tier 1 (cheap)
- **Mutating Status**: Read-only
- **Prerequisites**: None

```yaml
tool: models_list_runtimes

arguments: {}
```

- **Error behavior**: None.
- **Returned results**: `VeyraResult.summary["runtimes"]` containing status objects for all model IDs (`rule_set_3`, `rule_set_2`, `doench_2014`).
- **Side effects**: None.
- **Next logical tool**: `get_model_status`, `provision_model`, `verify_model`.

---

#### 5.7.2 `get_model_status` / `model_status`

- **Identity**: `get_model_status` (Python) / `model_status` (MCP) / `GET /models/{model_id}` (HTTP) / `veyra models describe` (CLI)
- **Category**: Model Runtime Management
- **Cost Tier**: Tier 1 (cheap)
- **Mutating Status**: Read-only
- **Prerequisites**: Valid `model_id`

```yaml
tool: model_status

arguments:

  model_id:
    canonical_name: model_id
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: ["rule_set_3", "rule_set_2", "doench_2014"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Must match a valid model ID"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Unknown model: <model_id>"
```

- **Error behavior**: Unknown model populates `errors`; HTTP 404.
- **Returned results**: `VeyraResult.summary` with `state` (`not_provisioned`, `provisioned`, `verified`, `incompatible`, `failed`), `runtime_path`, `python_version`, `dependency_status`, `verification_status`.
- **Side effects**: None.
- **Next logical tool**: `provision_model`, `verify_model`, `predict_ontarget_efficiency`.

---

#### 5.7.3 `provision_model` / `setup_model`

- **Identity**: `provision_model` (Python) / `setup_model` (MCP) / `POST /models/{model_id}/setup` (HTTP) / `veyra models setup` (CLI)
- **Category**: Model Runtime Management
- **Cost Tier**: Tier 2 (expensive / setup operation)
- **Mutating Status**: Mutating (creates virtualenv under `data/model_envs/<model_id>/`, installs PyPI dependencies)
- **Prerequisites**: Valid `model_id`, disk and network access

```yaml
tool: setup_model

arguments:

  model_id:
    canonical_name: model_id
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: ["rule_set_3", "rule_set_2", "doench_2014"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Must match a provisionable model ID"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: "Creates virtualenv under data/model_envs/<model_id>/ and installs required wheels/packages"
    errors: "Unknown model: <model_id> | Environment creation failed | Python version incompatible"

  force:
    canonical_name: force
    type: boolean
    required: false
    default: false
    nullable: false
    allowed_values: [true, false]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: null
    coordinate_system: null
    validation: "If true, deletes and recreates virtualenv"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: "Deletes existing data/model_envs/<model_id>/ directory before recreating"
    errors: null
```

- **Error behavior**: Creation/pip failure writes details to `errors` and sets `state="failed"` or `state="incompatible"`.
- **Returned results**: `VeyraResult.summary` with provisioning outcome (`action`, `runtime_status`, `runtime_path`, `pip_output`).
- **Side effects**: Disk write under `data/model_envs/<model_id>/`. Does NOT modify main environment.
- **Next logical tool**: `verify_model`.

---

#### 5.7.4 `verify_model`

- **Identity**: `verify_model` (Python, Core, MCP, HTTP) / `veyra models verify` (CLI)
- **Category**: Model Runtime Management
- **Cost Tier**: Tier 2 (moderate / execution test case)
- **Mutating Status**: Read-only (runs execution check in isolated runtime)
- **Prerequisites**: Model runtime must be provisioned

```yaml
tool: verify_model

arguments:

  model_id:
    canonical_name: model_id
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: ["rule_set_3", "rule_set_2", "doench_2014"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Must match a provisioned model ID"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: "Unknown model: <model_id> | Runtime not provisioned | Health check assertion failed"
```

- **Error behavior**: Failed health check sets `verification_status="fail"` and lists failure output in `errors`.
- **Returned results**: `VeyraResult.summary` with `verification_status` (`pass`/`fail`), `test_score`, `expected_score`, `error_details`.
- **Side effects**: None.
- **Next logical tool**: `predict_ontarget_efficiency`.

---

#### 5.7.5 `ensure_model_ready` / `get_model_spec`

- **Identity**: `ensure_model_ready` / `get_model_spec` (Python API)
- **Category**: Model Runtime Management
- **Cost Tier**: Tier 1 (cheap check) / Tier 2 if auto-provisioning triggered
- **Mutating Status**: Mutating if auto-provisioning occurs
- **Prerequisites**: Valid `model_id`

```yaml
tool: ensure_model_ready

arguments:

  model_id:
    canonical_name: model_id
    type: string
    required: true
    default: null
    nullable: false
    allowed_values: ["rule_set_3", "rule_set_2", "doench_2014"]
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: lowercased
    coordinate_system: null
    validation: "Target model ID"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: "Triggers provision_model and verify_model if runtime is not ready"
    errors: "Unknown model: <model_id>"
```

- **Error behavior**: Returns `(None, status_dict)` if model cannot be made ready.
- **Returned results**: Tuple `(ready_model_id_or_none, status_dict)`.
- **Side effects**: Creates venv if necessary.
- **Next logical tool**: `predict_ontarget_efficiency`.

---

### 5.8 System & Cache Operations

#### 5.8.1 `cache_status` / `get_cache_info`

- **Identity**: `get_cache_info` (Python) / `cache_status` (Core, HTTP) / `veyra cache status` (CLI)
- **Category**: System & Cache Management
- **Cost Tier**: Tier 1 (cheap)
- **Mutating Status**: Read-only
- **Prerequisites**: None

```yaml
tool: cache_status

arguments:

  tool_name:
    canonical_name: tool_name
    type: string
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Optional tool name filter"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: null
    errors: null
```

- **Error behavior**: None.
- **Returned results**: `VeyraResult.summary` with `total_entries`, `by_tool` entry count dict.
- **Side effects**: None.
- **Next logical tool**: `clear_cache`.

---

#### 5.8.2 `cache_clear` / `clear_cache`

- **Identity**: `clear_cache` (Python) / `cache_clear` (Core, HTTP) / `veyra cache clear` (CLI)
- **Category**: System & Cache Management
- **Cost Tier**: Tier 1 (cheap)
- **Mutating Status**: Mutating (deletes cached index/result files from cache directory)
- **Prerequisites**: None

```yaml
tool: cache_clear

arguments:

  tool_name:
    canonical_name: tool_name
    type: string
    required: false
    default: null
    nullable: true
    allowed_values: null
    minimum: null
    maximum: null
    units: null
    accepted_format: null
    alphabet: null
    normalization: stripped
    coordinate_system: null
    validation: "Optional tool name to target for clearing"
    enforced_by: canonical validation
    conditional_requirements: null
    side_effects: "Removes cached files on disk under cache/"
    errors: null
```

- **Error behavior**: None.
- **Returned results**: `VeyraResult.summary` with `entries_cleared`, `tool_name`.
- **Side effects**: Deletes disk cache files.
- **Next logical tool**: Diagnostic re-execution.

---

#### 5.8.3 `list_tools`

- **Identity**: `GET /tools` (HTTP) / `veyra tools list` (CLI) / `veyra-mcp list` (MCP)
- **Category**: System Info
- **Cost Tier**: Tier 1 (cheap)
- **Mutating Status**: Read-only
- **Prerequisites**: None

```yaml
tool: list_tools

arguments: {}
```

- **Error behavior**: None.
- **Returned results**: List of registered tools with name, tier, and cost.
- **Side effects**: None.
- **Next logical tool**: Tool invocation.

---

## 6. Validation, Error Taxonomy, and Failure Semantics

### 6.1 Unified Failure Signal

The backend returns errors via uniform structures across all interfaces:

- **Python API & Core**: Returns `VeyraResult` with `errors` containing descriptive strings.
- **HTTP REST API**: Translates non-empty `VeyraResult.errors` or missing resource exceptions to HTTP status codes:
  - `400 Bad Request`: Validation failure, sequence format error, invalid parameter value/range.
  - `404 Not Found`: Genome ID not in registry, model ID unknown.
  - `500 Internal Server Error`: Unhandled external tool binary crash or runtime exception.
- **CLI Interface**: Returns non-zero exit code (`1`) when `VeyraResult.errors` is non-empty.
- **MCP Tools**: Returns `ToolResult` with populated `errors` list.

### 6.2 Common Error Patterns & Interpretations

| Error Pattern / Message | Cause | Corrective Action |
|-------------------------|-------|-------------------|
| `Sequence is empty` | `sequence` argument was empty or whitespace | Provide non-empty DNA string |
| `Invalid nucleotide characters: [...]` | Sequence contains illegal bases for mode | Strip non-IUPAC/non-ACGT bases |
| `Genome '<id>' not found in registry` | `genome_id` is unregistered | Call `list_genomes` to select valid ID |
| `No BWA index for <id>` | Index missing for BWA search | Call `build_offtarget_index(genome_id)` |
| `BWA backend does not support bulge detection` | `allow_bulge=True` with `backend="bwa"` | Change `backend` to `"cas_offinder"` |
| `chrom, start, and end are required when search_scope='region'` | Missing region coords | Provide `chrom`, `start`, and `end` |
| `Model '<id>' is not available: [...]` | Explicitly requested model runtime not verified | Call `setup_model(id)` then `verify_model(id)` |
| `Context length mismatch: expected 30 nt (...)` | `context_sequence` is wrong length | Format 30-mer: 4 up + 20 spacer + 3 PAM + 3 down |
| `Cas-OFFinder executable not found` | Binary missing | Rebuild Cas-OFFinder executable |

---

## 7. Score and Model Semantics

The MIDEND router must distinguish between specificity and efficiency metrics:

1. **Off-target specificity (`cfd_score`)**:
   - Evaluates mismatch/bulge severity against off-target candidates.
   - Scale: 0.0 to 1.0 (1.0 = identical to wild-type, lower score = reduced cutting activity at off-target).
   - Higher specificity guide = lower overall off-target CFD scores across genome.

2. **On-target efficiency (`ontarget_score`)**:
   - Evaluates cutting efficacy at intended target site.
   - `rule_set_2`: AdaBoost model output (0.0 to 1.0 scale).
   - `rule_set_3`: LightGBM model output (native activity scale; not guaranteed 0-1 bounded).
   - `doench_2014`: Pure Python linear regression probability (0.0 to 1.0 scale).

3. **Canonical Result Keys**:
   - `ontarget_score`
   - `raw_score`
   - `ontarget_score_rule_set_2`
   - `ontarget_score_rule_set_3`
   - `ontarget_score_doench_2014`
   - `cfd_score`
   - `confidence_flag`
   - `selection_status`

---

## 8. Parameter Dependency and Conditional Rules

| Parameter / Condition | Required Dependent Parameters | Enforced Constraint / Behavior |
|-----------------------|--------------------------------|--------------------------------|
| `search_scope="region"` | `chrom`, `start`, `end` | Must all be non-null and valid range |
| `allow_bulge=True` | `backend="cas_offinder"` | `backend="bwa"` causes validation error |
| `mfe_include_scaffold=True` | `scaffold_sequence` | `scaffold_sequence` must be non-empty |
| `return_genomic_coord=True` | `chrom` | `chrom` must be non-empty string |
| `model="both"` | `model="auto"` | Accepted as alias for `auto` |
| Explicit `model="rule_set_2"` | Isolated runtime provisioned | Fails if runtime not verified; no silent fallback |
| Explicit `model="rule_set_3"` | Isolated runtime provisioned | Fails if runtime not verified; no silent fallback |

Model auto-selection hierarchy for `model="auto"`:

```text
model="auto" -> rule_set_3 (if verified) -> rule_set_2 (if verified) -> doench_2014 (fallback)
```

Auto-selection strictly requires model runtimes to be pre-verified.

---

## 9. Non-Negotiable Rules for MIDEND Callers

1. **Implementation Primacy**: Use this contract and backend implementation as ground truth over older documentation or prompts.
2. **Explicit Verification**: Do not attempt on-target predictions with unverified model runtimes. Call `setup_model` and `verify_model` explicitly when needed.
3. **Engine-Backend Matching**: Always pair `allow_bulge=True` with `backend="cas_offinder"`.
4. **Structured Error Handling**: Inspect `VeyraResult.errors` or HTTP status code rather than parsing unstructured stdout text.
5. **No Implicit Fallback on Explicit Model Requests**: Explicit model requests (`rule_set_2`, `rule_set_3`) must fail cleanly if unavailable; auto fallback applies ONLY when `model="auto"`.
6. **AI Interpretations**: Machine orchestration decisions and LLM summaries must clearly separate deterministic tool output (coordinates, scores, fold energies) from speculative interpretation.

---

## 10. Machine-Readable Snapshot

```json
{
  "version": "1.2.0",
  "contract_status": "verified_against_implementation",
  "python_api": [
    "ingest_file",
    "pam_scan_raw",
    "pam_scan_region",
    "build_offtarget_index",
    "search_offtargets",
    "score_offtargets_cfd",
    "rank_guides",
    "get_genomes",
    "get_genome_info",
    "get_cache_info",
    "clear_cache",
    "compute_gc_content",
    "check_homopolymer_runs",
    "compute_melting_temp",
    "compute_secondary_structure",
    "compute_positional_features",
    "compute_dinucleotide_composition",
    "compute_seed_gc",
    "analyze_mismatch_seed",
    "compute_cut_site",
    "predict_ontarget_efficiency",
    "provision_model",
    "verify_model",
    "ensure_model_ready",
    "get_model_status",
    "list_model_runtimes",
    "get_model_spec"
  ],
  "mcp_registry": [
    "pam_scan",
    "pam_scan_region",
    "build_offtarget_index",
    "offtarget_search",
    "score_offtargets",
    "rank_candidates",
    "compute_gc_content",
    "check_homopolymer_runs",
    "compute_melting_temp",
    "compute_secondary_structure",
    "compute_positional_features",
    "compute_dinucleotide_composition",
    "compute_seed_gc",
    "cas_offinder_search",
    "analyze_mismatch_seed",
    "compute_cut_site",
    "predict_ontarget_efficiency",
    "models_list_runtimes",
    "model_status",
    "setup_model",
    "verify_model"
  ],
  "http_routes": [
    "GET /health",
    "POST /ingest",
    "POST /pam/scan",
    "POST /pam/scan-region",
    "POST /index/build",
    "POST /offtarget/search",
    "POST /offtarget/score",
    "POST /rank",
    "GET /genomes",
    "GET /genomes/{genome_id}",
    "GET /cache/status",
    "POST /cache/clear",
    "GET /tools",
    "POST /sequence/gc",
    "POST /sequence/homopolymer",
    "POST /sequence/tm",
    "POST /sequence/secondary-structure",
    "POST /sequence/positional-features",
    "POST /sequence/dinucleotide-composition",
    "POST /sequence/seed-gc",
    "POST /offtarget/analyze-seed",
    "POST /sequence/cut-site",
    "POST /score/ontarget",
    "GET /models",
    "GET /models/{model_id}",
    "POST /models/{model_id}/setup",
    "POST /models/{model_id}/verify",
    "GET /models/{model_id}/status"
  ],
  "cli_commands": [
    "veyra ingest",
    "veyra pam scan",
    "veyra pam scan-region",
    "veyra index build",
    "veyra offtarget search",
    "veyra offtarget score",
    "veyra rank",
    "veyra score on-target",
    "veyra models list",
    "veyra models describe",
    "veyra models check",
    "veyra models setup",
    "veyra models verify",
    "veyra genome list",
    "veyra genome info",
    "veyra cache status",
    "veyra cache clear",
    "veyra tools list",
    "veyra tools describe",
    "veyra sequence gc",
    "veyra sequence homopolymer",
    "veyra sequence tm",
    "veyra sequence secondary-structure",
    "veyra sequence positional-features",
    "veyra sequence dinucleotide-composition",
    "veyra sequence seed-gc",
    "veyra sequence cut-site"
  ],
  "result_wrapper": "VeyraResult",
  "error_semantics": "string list in errors; HTTP layer maps to 400/404/500 status codes",
  "coordinate_convention": "1-based half-open [start, end) genomic coordinates; 1-based biological spacer positions",
  "model_ids": ["rule_set_3", "rule_set_2", "doench_2014"]
}
```
