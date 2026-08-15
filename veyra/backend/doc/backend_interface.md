# Backend Interface Reference

Complete reference for VEYRA backend input arguments, function signatures, and data flow.

---

## 1. CLI Interface (veyra.py)

### Basic Usage

```bash
python veyra.py --input <filepath> [options]
```

### Arguments

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `--input` | str | Yes | — | Path to the input genomic file |
| `--json` | flag | No | `False` | Output full record data as JSON |
| `--quiet` | flag | No | `False` | Suppress summary output |
| `--validate-only` | flag | No | `False` | Parse and validate only (exit code) |
| `--pam` | flag | No | `False` | Enable PAM scanning |
| `--pam-types` | list[str] | No | `None` | PAM types to scan (default: SpCas9) |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | File not found or ingestion error |
| 2 | Validation failed (with `--validate-only`) |
| 130 | Interrupted (Ctrl+C) |

### Examples

```bash
# Human-readable summary
python veyra.py --input data/genomes/test_genome.fa

# JSON output
python veyra.py --input data/sequences/test_sequences.fastq --json

# Validate only
python veyra.py --input data/sequences/test_genbank.gb --validate-only

# PAM scanning with multiple types
python veyra.py --input data/genomes/test_genome.fa --pam --pam-types SpCas9 Cas12a

# Quiet JSON (no summary header)
python veyra.py --input data/genomes/test_genome.fa --json --quiet
```

---

## 2. Ingestion Service

### ingest_file()

```python
def ingest_file(
    filepath: str,
    *,
    pam_scan: bool = False,
    pam_names: list[str] | None = None,
) -> Iterator[GenomicRecord]:
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filepath` | str | required | Path to input genomic file |
| `pam_scan` | bool | `False` | Run PAM detection on each record |
| `pam_names` | list[str] | `None` | PAM types to scan (default: `["SpCas9"]`) |

**Returns:** Iterator of `GenomicRecord` instances.

**Raises:**
- `FileNotFoundError` — file does not exist
- `IngestionError` — format detection or parsing failure

### get_ingestion_summary()

```python
def get_ingestion_summary(
    filepath: str,
    *,
    pam_scan: bool = False,
    pam_names: list[str] | None = None,
) -> dict:
```

**Returns:** Dict with keys:
- `input_file` (str)
- `detected_format` (str: "fasta", "fastq", "genbank")
- `num_records` (int)
- `total_bases` (int)
- `records` (list[dict]) — summary of each record

---

## 3. Parsers

All parsers share the same signature:

```python
def parse(filepath: str) -> Iterator[GenomicRecord]:
```

### FASTA Parser

```python
from parsers.fasta_parser import parse
records = list(parse("data/genomes/test_genome.fa"))
```

**Input:** FASTA file (`.fa`, `.fasta`, `.fna`, `.faa`)

**Output fields per record:**
- `id` — sequence ID (first word of header)
- `sequence` — nucleotide sequence (uppercased)
- `length` — sequence length
- `description` — full header text
- `accession` — accession number (if present)
- `provenance.source_filename` — input file path
- `provenance.input_format` — `VEYRAFormat.FASTA`
- `provenance.parser_name` — `"fasta"`

### FASTQ Parser

```python
from parsers.fastq_parser import parse
records = list(parse("data/sequences/test_sequences.fastq"))
```

**Input:** FASTQ file (`.fq`, `.fastq`)

**Additional output fields:**
- `quality.scores` — list of Phred quality scores
- `quality.mean_quality` — mean quality score
- `quality.min_quality` — minimum quality score
- `quality.max_quality` — maximum quality score

### GenBank Parser

```python
from parsers.genbank_parser import parse
records = list(parse("data/sequences/test_genbank.gb"))
```

**Input:** GenBank file (`.gb`, `.gbk`, `.gbff`)

**Additional output fields:**
- `annotations` — key-value metadata
- `features` — list of `GenomicFeature`:
  - `type` — feature type (gene, CDS, source, etc.)
  - `location` — `GenomicCoordinate` (start, end, strand)
  - `qualifiers` — dict of feature qualifiers

---

## 4. PAM Scanner

### scan_pam()

```python
from parsers.pam import scan_pam, PAMSite, PAMScanResult

result: PAMScanResult = scan_pam(
    sequence: str,
    pam_type: str = "SpCas9",
    strand: str = "both",
) -> PAMScanResult
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sequence` | str | required | DNA sequence to scan |
| `pam_type` | str | `"SpCas9"` | PAM type name (see PAM_DATABASE) |
| `strand` | str | `"both"` | `"both"`, `"fwd"`, or `"rev"` |

**Returns:** `PAMScanResult` with:
- `total_sites` — count of PAM sites found
- `forward_sites` — count on + strand
- `reverse_sites` — count on - strand
- `pam_types` — dict of `{pam_type_name: count}`
- `sites` — list of `PAMSite` objects

### scan_pam_multi()

```python
from parsers.pam import scan_pam_multi

result = scan_pam_multi(
    sequence: str,
    pam_names: list[str],
) -> PAMScanResult
```

Scans for multiple PAM types in a single pass.

### Available PAM Types

| Name | Motif | Spacer | Position | Description |
|------|-------|--------|----------|-------------|
| `SpCas9` | NGG | 20 | 3' | Streptococcus pyogenes Cas9 |
| `SaCas9` | NNGRRT | 20 | 3' | Staphylococcus aureus Cas9 |
| `Cas12a` | TTTV | 20 | 5' | Cas12a/Cpf1 |
| `Cas12b` | TTTN | 20 | 5' | Cas12b/C2c1 |
| `Cas9_NG` | NG | 20 | 3' | SpCas9-NG (relaxed) |
| `SpRY_NRN` | NRN | 20 | 3' | SpRY (near-PAMless) |
| `SpRY_NYN` | NYN | 20 | 3' | SpRY (near-PAMless) |

---

## 5. MCP Tools

### pam_scan()

```python
from mcp.tools.pam_scan import pam_scan

result: ToolResult = pam_scan(
    sequence: str,                    # Required: DNA sequence
    pam_pattern: str = "NGG",         # IUPAC PAM motif
    protospacer_len: int = 20,        # Protospacer length (1-100)
    strand: str = "both",             # "both", "fwd", or "rev"
    chrom: str | None = None,         # Optional chromosome name
) -> ToolResult
```

### pam_scan_region()

```python
from mcp.tools.pam_scan_region import pam_scan_region

result: ToolResult = pam_scan_region(
    genome_id: str,                   # Required: genome ID
    chrom: str,                       # Required: chromosome name
    start: int,                       # Required: 1-based start (inclusive)
    end: int,                         # Required: 1-based end (exclusive)
    pam_pattern: str = "NGG",         # IUPAC PAM motif
    protospacer_len: int = 20,        # Protospacer length
    strand: str = "both",             # "both", "fwd", or "rev"
) -> ToolResult
```

**Prerequisites:** `.fai` index for the genome.

### build_offtarget_index()

```python
from mcp.tools.build_offtarget_index import build_offtarget_index

result: ToolResult = build_offtarget_index(
    genome_id: str,                   # Required: genome ID
    cas_variant: str = "SpCas9",      # Cas variant (cache key)
    force_rebuild: bool = False,      # Force rebuild
) -> ToolResult
```

**Prerequisites:** `bwa` on PATH, genome FASTA registered.

### offtarget_search()

```python
from mcp.tools.offtarget_search import offtarget_search

result: ToolResult = offtarget_search(
    spacer_sequence: str,             # Required: 20nt guide sequence
    genome_id: str,                   # Required: genome ID
    pam_pattern: str = "NGG",         # PAM pattern
    max_mismatches: int = 4,          # Max mismatches (0-10)
    allow_bulge: bool = False,        # Not implemented
    cas_variant: str = "SpCas9",      # Cas variant name
) -> ToolResult
```

**Prerequisites:** BWA index (from `build_offtarget_index`).

### score_offtargets()

```python
from mcp.tools.score_offtargets import score_offtargets

result: ToolResult = score_offtargets(
    spacer_sequence: str,             # Required: wild-type spacer (20nt)
    candidates: list[PAMSiteRow],     # Required: off-target candidates
    pam_pattern: str = "NGG",         # PAM pattern
) -> ToolResult
```

**IMPORTANT:** First argument is the spacer string, not the candidates list.

**Prerequisites:** CFD pickle files at `references/CFD_Scoring/`.

### rank_candidates()

```python
from mcp.tools.rank_candidates import rank_candidates

result: ToolResult = rank_candidates(
    guides: list[PAMSiteRow],         # Required: candidate guides
    off_targets: list[PAMSiteRow] | None = None,  # Off-target rows
    on_target_scores: dict[str, float] | None = None,  # {spacer: score}
    sort_by: str = "composite",       # Sort criterion
) -> ToolResult
```

**sort_by options:** `"composite"`, `"cfd_max"`, `"offtarget_count"`, `"on_target"`

---

## 6. MCP Server CLI

```bash
# List all tools
python -m mcp.server list

# Generic invocation
python -m mcp.server invoke <tool_name> --args-json '{"param": "value"}'

# Quick shortcuts
python -m mcp.server pam-scan --sequence <seq> [--pam NGG] [--spacer-len 20] [--strand both]
python -m mcp.server pam-scan-region --genome <id> --chrom <chr> --start <n> --end <n> [--pam NGG]
python -m mcp.server build-index --genome <id> [--cas SpCas9] [--force]
python -m mcp.server offtarget-search --spacer <seq> --genome <id> [--pam NGG] [--max-mismatches 4]
```

---

## 7. Data Models

### GenomicRecord

```python
@dataclass
class GenomicRecord:
    id: str
    sequence: str
    length: int
    description: str = ""
    accession: str | None = None
    annotations: dict[str, str] = field(default_factory=dict)
    features: list[GenomicFeature] = field(default_factory=list)
    coordinate: GenomicCoordinate | None = None
    quality: QualityData | None = None
    provenance: Provenance = field(default_factory=Provenance)
    validation: ValidationResult = field(default_factory=ValidationResult)
    pam_scan: PAMScanResult | None = None
```

### PAMSiteRow (MCP)

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
    mismatch_positions: str | None = None  # comma-separated 0-based
    cfd_score: float | None = None
    rs2_score: float | None = None
```

### ToolResult (MCP)

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

---

## 8. Reference Genome Registry

```python
from references import get_genome, list_genomes, register_genome, GenomeConfig

# List all genomes
genomes = list_genomes()

# Get a genome
genome = get_genome("GRCh38.p14")

# Register a custom genome
register_genome(GenomeConfig(
    genome_id="my_genome",
    display_name="My Genome",
    fasta_path="/path/to/genome.fa",
))
```

### GenomeConfig Fields

| Field | Type | Description |
|-------|------|-------------|
| `genome_id` | str | Unique identifier |
| `display_name` | str | Human-readable name |
| `fasta_path` | str | Absolute path to FASTA |
| `fai_path` | str | Path to `.fai` index (optional) |
| `bwa_index_prefix` | str | BWA index prefix (optional) |
| `metadata` | dict | Additional metadata |

---

## 9. Cache API

```python
from cache import make_cache_key, cache_get, cache_set, cache_invalidate, cache_clear

# Generate cache key
key = make_cache_key("tool_name", param1="value1", param2="value2")

# Get/set
entry = cache_get(key)
cache_set(key, tool_name="tool_name", index_path="/path/to/index", ...)

# Invalidate
cache_invalidate(key)
cache_clear(tool_name="tool_name")  # or cache_clear() for all
```

---

## 10. Coordinate Convention

All VEYRA coordinates are **1-based, half-open `[start, end)`**:

- `start` — 1-based, inclusive
- `end` — exclusive (not included in the range)

This is consistent with samtools and BLAST conventions.

Example: A 20bp sequence at position 100-119 in 1-based coordinates:
- `start = 100`
- `end = 120` (exclusive)
- Length = `end - start` = 20

---

## 11. File Format Requirements

### FASTA

```
>sequence_id description
ACGTACGTACGT...
```

- Headers start with `>`
- Sequence lines can be wrapped
- Multiple records allowed
- IUPAC ambiguity codes supported

### FASTQ

```
@sequence_id description
ACGTACGTACGT...
+
IIIIIIIIIIII...
```

- 4 lines per record
- Quality scores: Phred+33 encoding
- Must have `+` separator line

### GenBank

```
LOCUS       ID              length bp    DNA     linear   UNK
DEFINITION  ...
ACCESSION   ...
FEATURES    ...
ORIGIN
    1 acgtacgtac gtacgtacgt ...
//
```

- Standard GenBank flat file format
- Features section optional but recommended
- ORIGIN section required

---

## 12. Error Handling

### Ingestion Errors

```python
from services.ingestion import IngestionError

try:
    records = list(ingest_file("file.fasta"))
except IngestionError as e:
    print(f"Ingestion failed: {e}")
except FileNotFoundError as e:
    print(f"File not found: {e}")
```

### MCP Tool Errors

All MCP tools return `ToolResult` with an `errors` list:

```python
result = pam_scan("invalid_sequence")
if result.errors:
    print(f"Errors: {result.errors}")
```

---

## 13. Dependencies

### Python Packages

| Package | Version | Purpose |
|---------|---------|---------|
| biopython | 1.83 | FASTA/FASTQ/GenBank parsing |
| numpy | 1.26+ | CFD scoring computation |

### System Tools

| Tool | Purpose | Required For |
|------|---------|--------------|
| `samtools` | FASTA indexing, region extraction | `pam_scan_region`, `offtarget_search` |
| `bwa` | Genome indexing, alignment | `build_offtarget_index`, `offtarget_search` |

### CFD Scoring Resources

| File | Location | Purpose |
|------|----------|---------|
| `mismatch_score.pkl` | `references/CFD_Scoring/` | Mismatch penalty scores |
| `pam_scores.pkl` | `references/CFD_Scoring/` | PAM efficiency scores |

Source: CRISPOR (Doench et al. 2016)
