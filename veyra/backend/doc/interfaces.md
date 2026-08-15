# VEYRA Interfaces

VEYRA provides four equivalent interfaces to the same core services:

```
                    ┌──────────────┐
                    │     CLI      │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │              │
                    │ VEYRA CORE   │
                    │   SERVICES   │
                    │              │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           HTTP API       MCP      Python API
```

All interfaces call the same underlying core services. No logic is duplicated.

## CLI

### Usage

```bash
# Activate virtual environment
source venv/bin/activate

# Run commands
python -m cli.main --help
python -m cli.main pam scan --sequence "ATCG..." --pam-pattern NGG
python -m cli.main genome list
python -m cli.main tools list
```

### Command Tree

```
veyra
├── ingest
│   --input FILE          Input file path
│   --pam                 Enable PAM scanning
│   --pam-types LIST      PAM types to scan
│   --output-format       json/tsv/text
│   --output FILE         Output file path
│
├── pam
│   ├── scan
│   │   --sequence SEQ    DNA sequence
│   │   --input FILE      Input file or - for stdin
│   │   --pam-pattern     PAM pattern (default: NGG)
│   │   --protospacer-len Protospacer length (default: 20)
│   │   --strand          both/fwd/rev
│   │   --chrom NAME      Chromosome name
│   │   --output-format   json/tsv/text
│   │   --output FILE     Output file path
│   │
│   └── scan-region
│       --genome-id ID    Genome identifier
│       --chrom NAME      Chromosome
│       --start N         Start position (1-based)
│       --end N           End position (exclusive)
│       --pam-pattern     PAM pattern
│       --protospacer-len Protospacer length
│       --strand          both/fwd/rev
│       --output-format   json/tsv/text
│
├── index
│   └── build
│       --genome-id ID    Genome identifier
│       --cas-variant     Cas variant (default: SpCas9)
│       --force           Force rebuild
│       --output-format   json/tsv/text
│
├── offtarget
│   ├── search
│   │   --spacer SEQ     Spacer sequence
│   │   --genome-id ID   Genome identifier
│   │   --pam-pattern    PAM pattern
│   │   --max-mismatches Max mismatches (default: 4)
│   │   --allow-bulge    Allow bulges
│   │   --cas-variant    Cas variant
│   │   --output-format  json/tsv/text
│   │
│   └── score
│       --spacer SEQ     Wild-type spacer
│       --candidates-json FILE  Candidates JSON
│       --pam-pattern    PAM pattern
│       --output-format  json/tsv/text
│
├── rank
│   --guides-json FILE   Guides JSON
│   --offtargets-json    Off-targets JSON
│   --on-target-json     On-target scores JSON
│   --sort-by            composite/cfd_max/offtarget_count/on_target
│   --output-format      json/tsv/text
│
├── genome
│   ├── list
│   │   --output-format  json/tsv/text
│   │
│   └── info
│       --genome-id ID   Genome identifier
│       --output-format  json/tsv/text
│
├── cache
│   ├── status
│   │   --tool-name      Filter by tool
│   │   --output-format  json/tsv/text
│   │
│   └── clear
│       --tool-name      Clear specific tool cache
│       --confirm        Confirm clearing
│
└── tools
    ├── list
    │   --output-format  json/tsv/text
    │
    └── describe TOOL_NAME
        --output-format  json/tsv/text
```

## Python API

### Usage

```python
from api import (
    pam_scan_raw,
    pam_scan_region,
    ingest_file,
    build_offtarget_index,
    search_offtargets,
    score_offtargets_cfd,
    rank_guides,
    get_genomes,
    get_genome_info,
    get_cache_info,
    clear_cache,
)

# PAM scan
result = pam_scan_raw("ATCG...", pam_pattern="NGG")
print(result.rows[0].start)

# Ingest file
result = ingest_file("genome.fasta", pam_scan=True)

# Get results as JSON
print(result.to_json())
```

### Functions

| Function | Description |
|----------|-------------|
| `pam_scan_raw(sequence, pam_pattern, protospacer_len, strand, chrom)` | Scan raw DNA for PAM sites |
| `pam_scan_region(genome_id, chrom, start, end, ...)` | Scan genomic region |
| `ingest_file(input_path, pam_scan, pam_names)` | Ingest genomic file |
| `build_offtarget_index(genome_id, cas_variant, force_rebuild)` | Build BWA index |
| `search_offtargets(spacer_sequence, genome_id, ...)` | Search for off-targets |
| `score_offtargets_cfd(spacer_sequence, candidates, pam_pattern)` | Score with CFD |
| `rank_guides(guides, off_targets, on_target_scores, sort_by)` | Rank candidates |
| `get_genomes()` | List registered genomes |
| `get_genome_info(genome_id)` | Get genome details |
| `get_cache_info(tool_name)` | Get cache status |
| `clear_cache(tool_name)` | Clear cache entries |

## HTTP API

### Usage

```bash
# Start server
source venv/bin/activate
uvicorn http_api.app:app --host 0.0.0.0 --port 8000

# Or
python -m http_api.app
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/ingest` | Ingest genomic file |
| POST | `/pam/scan` | Scan sequence for PAM sites |
| POST | `/pam/scan-region` | Scan genomic region |
| POST | `/index/build` | Build BWA index |
| POST | `/offtarget/search` | Search for off-targets |
| POST | `/offtarget/score` | Score with CFD |
| POST | `/rank` | Rank candidates |
| GET | `/genomes` | List genomes |
| GET | `/genomes/{genome_id}` | Get genome info |
| GET | `/cache/status` | Get cache status |
| POST | `/cache/clear` | Clear cache |
| GET | `/tools` | List available tools |

### Interactive Documentation

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## MCP

### Usage

```bash
# List tools
python -m mcp.server list

# Invoke tool
python -m mcp.server invoke pam_scan --args-json '{"sequence": "ATCG..."}'

# Quick shortcuts
python -m mcp.server pam-scan --sequence "ATCG..."
python -m mcp.server build-index --genome GRCh38.p14
python -m mcp.server offtarget-search --spacer "ATCG..." --genome GRCh38.p14
```

### Tools

| Tool | Tier | Cost |
|------|------|------|
| `pam_scan` | 1 | cheap / deterministic |
| `pam_scan_region` | 1 | cheap / reference lookup |
| `build_offtarget_index` | 2 | expensive / setup / cacheable |
| `offtarget_search` | 2 | expensive / genome-scale |
| `score_offtargets` | 2 | moderate |
| `rank_candidates` | 2 | moderate |

## Canonical Schemas

All interfaces use shared request/response schemas defined in `schemas/canonical.py`.

### Request Models

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

### Response Models

- `VeyraResult` — standard result wrapper
- `ResultRow` — single result row
- `VeyraError` — structured error
- `GenomeInfo` — genome information
- `CacheStatus` — cache statistics

## Output Formats

All interfaces support:

- **JSON** — machine-readable, full data
- **TSV** — shell-friendly, pipeable to `grep`, `awk`, `sort`
- **Text** — human-readable

## Configuration Precedence

1. Explicit CLI/API/MCP parameter
2. Configuration file / environment variable
3. Documented default

## Error Handling

| Interface | Error Format |
|-----------|--------------|
| CLI | Human-readable message, non-zero exit code |
| HTTP API | Structured JSON error, appropriate HTTP status |
| MCP | Structured tool error |
| Python | Typed exception/result |

## Parameter Passthrough

All parameter values are preserved exactly. No silent transformation unless documented.

Example:
```bash
python -m cli.main pam scan \
    --input target.fasta \
    --pam-pattern NGG \
    --protospacer-len 20 \
    --strand both
```

Reaches core service with:
```python
pam_pattern = "NGG"
protospacer_len = 20
strand = "both"
```
