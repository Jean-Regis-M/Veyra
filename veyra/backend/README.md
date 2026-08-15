# VEYRA Backend — Genomic Intelligence Backend

VEYRA is a modular genomic intelligence backend providing ingestion, PAM scanning, and CRISPR off-target analysis via an MCP tool layer.

**Status:** Working baseline — ingestion + PAM scanning + MCP analysis layer (v0.2).

## Architecture

```
FASTA / FASTQ / GenBank
        │
        ▼
    Biopython
        │
        ▼
  normalized GenomicRecord
        │
        ▼
      PAM scan
        │
        ▼
    MCP tool layer
    ├── pam_scan                  (Tier 1 — cheap)
    ├── pam_scan_region           (Tier 1 — cheap)
    ├── build_offtarget_index     (Tier 2 — expensive)
    ├── offtarget_search          (Tier 2 — expensive)
    ├── score_offtargets          (Tier 2 — moderate)
    └── rank_candidates           (Tier 2 — moderate)
```

The downstream VEYRA reasoning/scoring/model layer is still being developed.

## Project Structure

```
veyra/backend/
├── veyra.py                 # CLI entry point
├── requirements.txt
├── parsers/
│   ├── detector.py          # Format detection
│   ├── fasta_parser.py      # Biopython FASTA
│   ├── fastq_parser.py      # Biopython FASTQ
│   ├── genbank_parser.py    # Biopython GenBank
│   └── pam.py               # PAM scanning (regex + FM-index)
├── schemas/
│   └── genomic_record.py    # GenomicRecord dataclass
├── services/
│   └── ingestion.py         # Orchestration pipeline
├── mcp/
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
│   └── __init__.py          # Genome registry
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
└── tests/
    ├── test_ingestion.py    # 60 tests
    ├── test_mcp.py          # 52 tests
    └── fixtures/
```

## Installation

```bash
cd /home/hrirake/Desktop/hck15/veyra/backend
pip install -r requirements.txt
```

Requires Python 3.10+, Biopython 1.83, numpy 1.26+.

System tools (for MCP tier-2 operations): `bwa`, `samtools`.

## CLI Usage

### Ingestion

```bash
python veyra.py --input /path/to/file.fasta
python veyra.py --input /path/to/file.fastq --json
python veyra.py --input /path/to/file.gb --pam
```

### MCP Server

```bash
python -m mcp.server list                           # list all tools
python -m mcp.server pam-scan --sequence ATCGATCGATCGATCGATCGAGG
python -m mcp.server pam-scan-region --genome GRCh38.p14 --chrom chr1 --start 1000000 --end 1001000
python -m mcp.server build-index --genome GRCh38.p14 --force
python -m mcp.server offtarget-search --spacer ATCGATCGATCGATCGATCGAGG --genome GRCh38.p14
```

## MCP Tools

| Tool | Tier | Cost | Description |
|------|------|------|-------------|
| `pam_scan` | 1 | cheap | PAM scanning on input sequence |
| `pam_scan_region` | 1 | cheap | PAM scanning on genomic region |
| `build_offtarget_index` | 2 | expensive | BWA index creation (cached) |
| `offtarget_search` | 2 | expensive | Mismatch-tolerant off-target search |
| `score_offtargets` | 2 | moderate | CFD specificity scoring |
| `rank_candidates` | 2 | moderate | Candidate guide ranking |

See `doc/mcp_tools.md` for full tool reference.

## Testing

```bash
python -m pytest tests/ -v       # full suite
python -m pytest tests/ -q       # quick summary
```

## Supported Input Formats

| Format | Extensions |
|--------|-----------|
| FASTA | `.fa`, `.fasta`, `.fna`, `.faa` |
| FASTQ | `.fq`, `.fastq` |
| GenBank | `.gb`, `.gbk`, `.gbff` |

## Documentation

- `doc/architecture.md` — pipeline diagram
- `doc/data_model.md` — GenomicRecord specification
- `doc/input_formats.md` — format details
- `doc/development.md` — development guide
- `doc/mcp_tools.md` — MCP tool reference
- `doc/reference_genomes.md` — genome registry
- `doc/off_target_search.md` — BWA search methodology
- `doc/caching.md` — cache architecture
