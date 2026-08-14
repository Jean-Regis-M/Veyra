# Development Guide

## Setup

```bash
cd /home/hrirake/Desktop/hck15/veyra/backend
pip install -r requirements.txt
```

Requires Python 3.10+, Biopython 1.83, numpy 1.26+.

System tools (for MCP tier-2 operations):
- `bwa` — off-target index and search
- `samtools` — FASTA indexing and region extraction

## Project Layout

```
veyra/backend/
├── veyra.py                 # CLI entry point (ingestion)
├── requirements.txt
├── parsers/
│   ├── __init__.py
│   ├── detector.py          # Format detection
│   ├── fasta_parser.py      # Biopython FASTA
│   ├── fastq_parser.py      # Biopython FASTQ
│   ├── genbank_parser.py    # Biopython GenBank
│   └── pam.py               # PAM scanning (regex + FM-index)
├── schemas/
│   ├── __init__.py
│   └── genomic_record.py    # GenomicRecord dataclass
├── services/
│   ├── __init__.py
│   └── ingestion.py         # Orchestration pipeline
├── utils/
│   ├── __init__.py
│   └── validation.py
├── mcp/
│   ├── __init__.py
│   ├── schemas.py           # PAMSiteRow, ToolResult
│   ├── server.py            # MCP tool registry + CLI
│   └── tools/
│       ├── pam_scan.py
│       ├── pam_scan_region.py
│       ├── build_offtarget_index.py
│       ├── offtarget_search.py
│       ├── score_offtargets.py
│       └── rank_candidates.py
├── references/
│   └── __init__.py          # Genome registry, CFD paths
├── cache/
│   └── __init__.py          # SQLite cache layer
├── doc/
│   ├── architecture.md
│   ├── data_model.md
│   ├── input_formats.md
│   ├── development.md
│   ├── mcp_tools.md
│   ├── reference_genomes.md
│   ├── off_target_search.md
│   └── caching.md
├── tests/
│   ├── __init__.py
│   ├── test_ingestion.py    # 60 tests
│   ├── test_mcp.py          # 52 tests
│   └── fixtures/
│       ├── test.fasta
│       ├── test.fastq
│       ├── test.gb
│       ├── test_genome.fa   # Small test genome for MCP tests
│       └── ...
```

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Ingestion only
python -m pytest tests/test_ingestion.py -v

# MCP only
python -m pytest tests/test_mcp.py -v

# Quick summary
python -m pytest tests/ -q
```

Expected baseline: ~106 passed, ~6 skipped, 0 failed.

## CLI Usage

### Ingestion CLI

```bash
# Human-readable summary
python veyra.py --input /path/to/file.fasta

# JSON output
python veyra.py --input /path/to/file.fastq --json

# PAM scanning on ingest
python veyra.py --input /path/to/file.fasta --pam

# Custom PAM
python veyra.py --input /path/to/file.fasta --pam --pam-type Cas12a
```

### MCP Server CLI

```bash
# List all tools
python -m mcp.server list

# PAM scan
python -m mcp.server pam-scan --sequence ATCGATCGATCGATCGATCGAGG

# PAM scan a region
python -m mcp.server pam-scan-region --genome GRCh38.p14 --chrom chr1 --start 1000000 --end 1001000

# Build off-target index
python -m mcp.server build-index --genome GRCh38.p14 --force

# Off-target search
python -m mcp.server offtarget-search --spacer ATCGATCGATCGATCGATCGAGG --genome GRCh38.p14

# Generic tool invocation
python -m mcp.server invoke <tool_name> --args-json '{"param": "value"}'
```

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
- Dataclasses for structured data (not Pydantic)
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
