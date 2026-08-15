# Development Guide

## Setup

```bash
cd /home/hrirake/Desktop/hck15/veyra/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Requires Python 3.10+, Biopython 1.83, numpy 1.26+.

System tools (for MCP tier-2 operations):
- `bwa` — off-target index and search
- `samtools` — FASTA indexing and region extraction

## Project Layout

```
veyra/backend/
├── __main__.py              # python -m veyra entry
├── veyra.py                 # Legacy CLI (ingestion)
├── requirements.txt
├── core/                    # Core services (unified logic)
│   ├── __init__.py
│   ├── pam.py               # PAM scanning service
│   ├── ingestion.py         # Ingestion service
│   ├── offtarget.py         # Off-target service
│   ├── ranking.py           # Ranking service
│   ├── genome.py            # Genome management
│   └── cache.py             # Cache management
├── schemas/                 # Canonical schemas
│   ├── __init__.py
│   ├── genomic_record.py    # GenomicRecord dataclass
│   └── canonical.py         # Request/response models
├── cli/                     # CLI adapter
│   ├── __init__.py
│   └── main.py              # Unified CLI
├── api/                     # Python API adapter
│   └── __init__.py
├── http_api/                # FastAPI HTTP adapter
│   ├── __init__.py
│   └── app.py
├── parsers/                 # File parsers
├── mcp/                     # MCP tools
├── references/              # Genome registry
├── cache/                   # SQLite cache
├── doc/                     # Documentation
└── tests/                   # Test suite
```

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Ingestion only
python -m pytest tests/test_ingestion.py -v

# MCP only
python -m pytest tests/test_mcp.py -v

# Interface parity tests
python -m pytest tests/test_interfaces.py -v

# Quick summary
python -m pytest tests/ -q
```

Expected baseline: 126 passed, 9 skipped, 1 failed (CFD resources missing).

## CLI Usage

### Unified CLI

```bash
# Get help
python -m cli.main --help

# Ingest files
python -m cli.main ingest --input file.fasta
python -m cli.main ingest --input file.fastq --pam
python -m cli.main ingest --input file.gb --output-format json

# PAM scanning
python -m cli.main pam scan --sequence "ATCGATCGAGG" --pam-pattern NGG
python -m cli.main pam scan --input file.fasta --pam-pattern NGG --strand both
python -m cli.main pam scan-region --genome-id GRCh38.p14 --chrom chr1 --start 1000000 --end 1001000

# Index building
python -m cli.main index build --genome-id GRCh38.p14
python -m cli.main index build --genome-id GRCh38.p14 --force

# Off-target analysis
python -m cli.main offtarget search --spacer "ATCGATCGATCGATCGATCG" --genome-id GRCh38.p14
python -m cli.main offtarget score --spacer "ATCGATCGATCGATCGATCG" --candidates-json candidates.json

# Ranking
python -m cli.main rank --guides-json guides.json --sort-by composite

# Genome management
python -m cli.main genome list
python -m cli.main genome info --genome-id GRCh38.p14

# Cache management
python -m cli.main cache status
python -m cli.main cache clear --confirm

# Tool introspection
python -m cli.main tools list
python -m cli.main tools describe pam_scan
```

### Legacy CLI

```bash
python veyra.py --input /path/to/file.fasta
python veyra.py --input /path/to/file.fastq --json
python veyra.py --input /path/to/file.fasta --pam
```

### MCP Server CLI

```bash
# List all tools
python -m mcp.server list

# PAM scan
python -m mcp.server pam-scan --sequence ATCGATCGATCGATCGATCGAGG

# Build off-target index
python -m mcp.server build-index --genome GRCh38.p14 --force

# Off-target search
python -m mcp.server offtarget-search --spacer ATCGATCGATCGATCGATCGAGG --genome GRCh38.p14

# Generic tool invocation
python -m mcp.server invoke <tool_name> --args-json '{"param": "value"}'
```

## Python API Usage

```python
import sys
sys.path.insert(0, '/home/hrirake/Desktop/hck15/veyra/backend')

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
result = pam_scan_raw("ATCGATCGAGG", pam_pattern="NGG")
print(result.rows[0].start)

# Get results as JSON/TSV/text
print(result.to_json())
print(result.to_tsv())
print(result.to_text())
```

## HTTP API Usage

```bash
# Start server
uvicorn http_api.app:app --host 0.0.0.0 --port 8000

# Or
python -m http_api.app
```

Interactive docs: `http://localhost:8000/docs`

## Adding a New MCP Tool

1. Create `mcp/tools/my_tool.py` with a function returning `ToolResult`:

```python
from mcp.schemas import ToolResult, PAMSiteRow

def my_tool(param: str) -> ToolResult:
    rows = [PAMSiteRow(chrom="chr1", start=1, end=10, strand="+")]
    return ToolResult(
        tool="my_tool",
        rows=rows,
        summary={"result": "value"},
    )
```

2. Register in `mcp/server.py`:

```python
from mcp.tools.my_tool import my_tool

TOOL_REGISTRY["my_tool"] = {
    "function": my_tool,
    "description": "My new tool",
    "cost": "moderate",
    "tier": 2,
}
```

3. Add CLI shortcut in `mcp/server.py` `main()` if desired.

4. Add tests in `tests/test_mcp.py`.

## Adding a New Parser

1. Create `parsers/newformat_parser.py` with `parse(filepath) -> Iterator[GenomicRecord]`
2. Register format in `schemas/genomic_record.py` (`VEYRAFormat` enum)
3. Add extension mappings in `parsers/detector.py`
4. Add content detection rules in `parsers/detector.py`
5. Register parser in `services/ingestion.py`
6. Add tests in `tests/test_ingestion.py`

## Adding a Reference Genome

1. Ensure the FASTA file exists on disk
2. Register in `references/__init__.py` inside `_register_defaults()`, or at runtime:

```python
from references import GenomeConfig, register_genome
register_genome(GenomeConfig(
    genome_id="my_genome",
    display_name="My Genome",
    fasta_path="/path/to/genome.fa",
))
```

3. Build indexes as needed:

```bash
samtools faidx /path/to/genome.fa
bwa index /path/to/genome.fa
```

## Code Conventions

- Python 3.10+ with type hints throughout
- Dataclasses for structured data (not Pydantic in core)
- Biopython for biological format parsing
- No global mutable state (except module-level CFD pickle cache)
- Structured error handling with `ToolResult.errors`
- Each tool is independently testable
- Coordinate convention: 1-based, half-open `[start, end)`
- Provenance preserved: tools cite their sources in `metadata`

## Provenance Policy

- BLAST/CRISPOR/BWA/CFD-derived values must not be presented as native VEYRA predictions
- Tool outputs include `metadata` with `scoring_source`, `reference`, `provenance` fields
- `rank_candidates` summary explicitly states: "NOT a validated predictive model"
- Future VEYRA reasoning layers will be clearly separated from baseline tool evidence

## Interface Architecture

All interfaces call the same core services:

```
CLI → core services → MCP tools (scientific logic)
Python API → core services → MCP tools
HTTP API → core services → MCP tools
MCP → core services → MCP tools
```

No logic is duplicated between interfaces.
