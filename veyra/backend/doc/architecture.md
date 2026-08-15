# VEYRA Architecture

## Ingestion Pipeline (v0.1)

```
Input File
    │
    ▼
Format Detection (extension + content inspection)
    │
    ▼
Biopython Parser (FASTA / FASTQ / GenBank)
    │
    ▼
Record Validation (sequence integrity, completeness)
    │
    ▼
Normalized GenomicRecord (dataclass instances)
    │
    ▼
Summary / JSON Output
```

## Planned Full Pipeline (future)

```
Input File
    │
    ▼
Format Detection
    │
    ▼
Biopython Parsing
    │
    ▼
Validation
    │
    ▼
Normalized GenomicRecord
    │
    ▼
Context / Feature Extraction
    │
    ├──▶ BLAST (sequence similarity)
    ├──▶ CRISPOR (CRISPR guide design)
    ├──▶ CCLMoff (off-target prediction)
    ├──▶ Local ML Models
    ├──▶ LLMs / Featherless APIs
    └──▶ MCP Tools
         │
         ▼
    VEYRA Reasoning Layer
         │
         ▼
    Final Analysis Output
```

## Module Responsibilities

| Module          | Responsibility                                        |
|-----------------|-------------------------------------------------------|
| `parsers/`      | Format detection + Biopython-based parsing             |
| `schemas/`      | Normalized data model definitions                     |
| `services/`     | Orchestration: detect → parse → validate → normalize  |
| `utils/`        | Validation, helper functions                          |
| `veyra.py`      | CLI interface                                         |

## Design Principles

1. **Model-agnostic** – No hard dependencies on specific AI/ML models
2. **Modular** – Each component is independently testable and replaceable
3. **Extensible** – New parsers, tools, and models plug in without modifying core
4. **Deterministic** – Same input produces same output
5. **Informative** – Structured errors and summaries at every stage
