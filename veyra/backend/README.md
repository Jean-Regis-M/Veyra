# VEYRA Backend – Genomic Intelligence Ingestion Module

VEYRA (Genomic Intelligence Backend) accepts genomic files from NCBI and other sources, parses them into a normalized internal representation, and provides structured output for downstream analysis modules.

**Status:** Initial ingestion/parsing foundation (v0.1).

## Project Structure

```
veyra/backend/
├── veyra.py              # CLI entry point
├── requirements.txt      # Pinned dependencies
├── README.md
├── doc/
│   ├── architecture.md
│   ├── input_formats.md
│   ├── data_model.md
│   └── development.md
├── parsers/
│   ├── __init__.py       # Parser exports
│   ├── detector.py       # Format detection (extension + content)
│   ├── fasta_parser.py   # Biopython FASTA parser
│   ├── fastq_parser.py   # Biopython FASTQ parser
│   └── genbank_parser.py # Biopython GenBank parser
├── schemas/
│   ├── __init__.py
│   └── genomic_record.py # Normalized data model (dataclasses)
├── services/
│   ├── __init__.py
│   └── ingestion.py      # Orchestration: detect → parse → validate
├── utils/
│   ├── __init__.py
│   └── validation.py     # Record validation utilities
└── tests/
    ├── __init__.py
    ├── test_ingestion.py  # Unit + integration tests
    └── fixtures/
        ├── test.fasta
        ├── test.fastq
        ├── test.gb
        ├── multi.fasta
        ├── multi.fastq
        ├── empty.fasta
        └── malformed.fasta
```

## Installation

```bash
# From the veyra/backend directory
pip install -r requirements.txt
```

Requires Python 3.10+ and Biopython 1.83.

## CLI Usage

```bash
# Human-readable summary (default)
python veyra.py --input /path/to/file.fasta

# JSON output
python veyra.py --input /path/to/file.fastq --json

# Validate only (exit code)
python veyra.py --input /path/to/file.gb --validate-only

# Quiet mode (suppress output)
python veyra.py --input /path/to/file.fasta --json --quiet

# Help
python veyra.py --help
```

## Supported Input Formats

| Format   | Extensions                          | Notes                     |
|----------|-------------------------------------|---------------------------|
| FASTA    | `.fa`, `.fasta`, `.fna`, `.faa`     | Single/multi-record       |
| FASTQ    | `.fq`, `.fastq`                     | With Phred quality scores |
| GenBank  | `.gb`, `.gbk`, `.gbff`             | Features, annotations     |

Format detection uses file extension as a hint, then confirms by inspecting file content headers.

## Normalized Data Representation

All parsed data is converted to `GenomicRecord` dataclass instances containing:

- `id` – sequence/record identifier
- `sequence` – nucleotide sequence (uppercased)
- `length` – sequence length in bases
- `description` – full header/description text
- `accession` – accession number where available
- `annotations` – key-value metadata (GenBank)
- `features` – list of `GenomicFeature` (gene, CDS, source, etc.)
- `coordinate` – `GenomicCoordinate` (start, end, strand, scaffold)
- `quality` – `QualityData` for FASTQ (Phred scores, mean/min/max)
- `provenance` – source filename, format, parser name/version
- `validation` – validation status, errors, warnings

## Error Handling

VEYRA produces structured errors for:

- Missing input files
- Unsupported/undetectable formats
- Empty files
- Malformed FASTA/FASTQ/GenBank
- Missing required sequence data

Errors are reported as `IngestionError` with clear messages rather than raw tracebacks.

## Extension Points

The architecture is designed for future modules:

1. **New parsers** – Add files to `parsers/` and register in `services/ingestion.py`
2. **Downstream tools** – Consume `GenomicRecord` lists in new service modules
3. **BLAST/CRISPOR/CCLMoff** – Wrap as services that accept GenomicRecord
4. **Reasoning layer** – Model-agnostic; no hard dependencies on specific AI/ML
5. **MCP tools / Featherless APIs** – Add as separate integration modules

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Or with unittest
python -m unittest discover tests/ -v
```

## Architecture

See `doc/architecture.md` for the full ingestion pipeline diagram.

See `doc/data_model.md` for the normalized data model specification.

See `doc/input_formats.md` for supported format details.

See `doc/development.md` for development and contribution guidelines.
