# Off-Target Search

VEYRA's off-target search supports two backends: BWA aln for mismatch-only search and Cas-OFFinder for full bulge-aware search. This document describes both backends, their differences, and how to use them.

## Overview

```
Spacer sequence (20nt)
        │
        ├─ allow_bulge=False (default)
        │       │
        │       ▼
        │   BWA aln (-n mismatch_fraction)
        │       │
        │       ▼
        │   Binary SAI → bwa samse → SAM
        │       │
        │       ▼
        │   Parse SAM → PAMSiteRow candidates
        │
        └─ allow_bulge=True OR backend="cas_offinder"
                │
                ▼
            Cas-OFFinder (OpenCL CPU/GPU)
                │
                ▼
            Parse output → PAMSiteRow candidates
        │
        ▼
    PAM extraction (samtools faidx)
        │
        ▼
    CFD scoring (score_offtargets)
        │
        ▼
    Candidate ranking (rank_candidates)
```

## Backend Selection

| Condition | Backend Used |
|-----------|--------------|
| `allow_bulge=False` AND `backend=None` or `backend="bwa"` | BWA aln |
| `allow_bulge=True` | Cas-OFFinder |
| `backend="cas_offinder"` | Cas-OFFinder |
| `backend="bwa"` AND `allow_bulge=True` | Cas-OFFinder (bulge takes precedence) |

## BWA aln Backend

### Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `-n` | `max_mismatches / len(spacer)` | Max fraction of quality-weighted mismatches |
| `-o` | `0` | No gap opens (gap-free alignment) |
| `-l` | `min(len(spacer), 32)` | Seed length |
| `-k` | `max_mismatches` | Max seed differences |

### Strand Behavior

- BWA aln aligns to both forward and reverse strands of the reference
- The SAM `flag` field indicates strand: bit 0x10 = reverse strand
- Both strands are reported in output

### Mismatch Handling

- Mismatches are extracted from the SAM `NM:i:` tag
- Candidates with `NM > max_mismatches` are filtered out
- Mismatch positions are computed by simple alignment comparison
- BWA uses quality-weighted scoring, so the `NM` tag may differ from simple base-by-base mismatch counting

## Cas-OFFinder Backend

### Overview

Cas-OFFinder is a GPU-accelerated tool for searching CRISPR off-target sites with DNA/RNA bulges. VEYRA integrates Cas-OFFinder 3.0.0 (built from source) for comprehensive off-target detection.

### Capabilities

- **Mismatch detection**: Up to N mismatches (configurable)
- **DNA bulge detection**: Up to N DNA bulges (configurable)
- **RNA bulge detection**: Up to N RNA bulges (configurable)
- **Combined search**: Simultaneous mismatch + bulge detection
- **Regional search**: Limit search to specific genomic regions

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `spacer_sequence` | (required) | 20-nt spacer sequence |
| `genome_id` | (required) | Reference genome ID |
| `pam_pattern` | "NGG" | PAM pattern (N = any base) |
| `max_mismatches` | 3 | Maximum number of mismatches |
| `max_dna_bulge` | 0 | Maximum DNA bulge size |
| `max_rna_bulge` | 0 | Maximum RNA bulge size |
| `search_scope` | "genome" | "genome" or "region" |
| `chrom` | None | Chromosome for regional search |
| `start` | None | Start position (1-based) for regional search |
| `end` | None | End position (1-based) for regional search |

### Output Fields

Cas-OFFinder output includes additional fields beyond standard mismatch search:

| Field | Description |
|-------|-------------|
| `bulge_type` | "X" (mismatch), "DNA", or "RNA" |
| `bulge_size` | Size of the bulge (0 for mismatches) |
| `bulge_position` | Position of bulge in the alignment (1-based) |
| `aligned_guide` | Guide sequence aligned with gaps |
| `aligned_candidate` | Candidate sequence aligned with gaps |
| `cfd_status` | "unsupported_bulge" for bulged candidates |

### CFD Scoring for Bulged Candidates

CFD scoring is designed for mismatch-only candidates. For candidates with DNA/RNA bulges:

- `cfd_status` is set to `"unsupported_bulge"`
- `cfd_score` and `cfd_weighted` are set to `None`
- These candidates should be evaluated using alternative scoring methods

### Provenance

- **Tool**: Cas-OFFinder 3.0.0
- **Source**: https://github.com/pinellolab/Cas-OFFinder
- **License**: BSD 3-Clause
- **Build**: CPU-only via POCL (AMD Ryzen 5 5600G)
- **Location**: `data/tools/cas-offinder/`

## Analyze Mismatch Seed Tool

The `analyze_mismatch_seed` tool provides alignment-aware seed region analysis for candidates with bulges.

### Features

- **Positional correspondence**: Handles indels/bulges in alignment
- **Seed region definition**: Configurable seed region (default: positions 11-20 from 5' end)
- **Mismatch classification**: Distinguishes seed vs. distal mismatches
- **Bulge-aware analysis**: Correctly maps positions after indels

### Usage

```python
from api import analyze_mismatch_seed

result = analyze_mismatch_seed(
    spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
    candidate_sequence="GCGCGCGCGCGCGCGCGCGC",
    bulge_type="DNA",
    bulge_size=1,
    aligned_guide="GCGCGCGCGCGCGCGCGCGC-",
    aligned_candidate="GCGCGCGCGCGCGCGCGCGCA",
)
```

## Limitations

### BWA Backend

- Bulges and indels are not detected (BWA is gap-free in this configuration)
- `max_mismatches > 5` may be slow or produce false negatives due to BWA seed heuristics
- PAM extraction may fail for reads near contig boundaries
- Quality scores from the original FASTQ are not used (BWA aln operates on sequence only)

### Cas-OFFinder Backend

- CFD scoring is not supported for bulged candidates
- Bulge position accuracy depends on alignment quality
- CPU-only mode is slower than GPU-accelerated mode
- Maximum bulge size is limited by tool constraints

## Post-Search Pipeline

After `offtarget_search`, candidates should be:

1. **Scored** with `score_offtargets(spacer, candidates, pam)` — adds CFD scores (see [cfd_scoring.md](cfd_scoring.md))
2. **Ranked** with `rank_candidates(guides, off_targets)` — aggregates evidence

## Provenance

- **BWA Backend**: BWA (bwa aln + bwa samse), samtools faidx
- **Cas-OFFinder Backend**: Cas-OFFinder 3.0.0 (BSD 3-Clause)
- **CFD scoring**: CRISPOR pickle resources (Doench et al. 2016) — see [cfd_scoring.md](cfd_scoring.md)
- All tool outputs include metadata indicating the source tool and version
