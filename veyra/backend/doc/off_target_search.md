# Off-Target Search

VEYRA's off-target search uses BWA aln for mismatch-tolerant alignment against a reference genome. This document describes the search methodology, its limitations, and how it differs from dedicated CRISPR off-target tools.

## Overview

```
Spacer sequence (20nt)
        │
        ▼
  BWA aln (-n mismatch_fraction)
        │
        ▼
  Binary SAI → bwa samse → SAM
        │
        ▼
  Parse SAM → PAMSiteRow candidates
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

## BWA aln Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `-n` | `max_mismatches / len(spacer)` | Max fraction of quality-weighted mismatches |
| `-o` | `0` | No gap opens (gap-free alignment) |
| `-l` | `min(len(spacer), 32)` | Seed length |
| `-k` | `max_mismatches` | Max seed differences |

## Strand Behavior

- BWA aln aligns to both forward and reverse strands of the reference
- The SAM `flag` field indicates strand: bit 0x10 = reverse strand
- Both strands are reported in output

## Mismatch Handling

- Mismatches are extracted from the SAM `NM:i:` tag
- Candidates with `NM > max_mismatches` are filtered out
- Mismatch positions are computed by simple alignment comparison
- BWA uses quality-weighted scoring, so the `NM` tag may differ from simple base-by-base mismatch counting

## Output Schema

Each candidate is a `PAMSiteRow`:

| Field | Source |
|-------|--------|
| `chrom` | SAM RNAME |
| `start` | SAM POS (1-based) |
| `end` | POS + reference length from CIGAR |
| `strand` | SAM flag (0x10 → `-`) |
| `protospacer` | SAM SEQ (reverse-complemented if `-` strand) |
| `pam` | Extracted from genome via samtools faidx |
| `mismatch_count` | SAM NM tag |
| `mismatch_positions` | Computed positions (0-based, comma-separated) |

## PAM Extraction

After alignment, the PAM is extracted from the reference genome:

- **3' PAMs (SpCas9):** PAM is downstream of the protospacer on the + strand
- **5' PAMs (Cas12a):** PAM is upstream of the protospacer on the + strand

PAM extraction uses `samtools faidx` on a 3nt window adjacent to the aligned read.

## Limitations

### BWA vs CRISPOR/Cas-OFFinder

| Feature | BWA aln | CRISPOR/Cas-OFFinder |
|---------|---------|----------------------|
| Mismatch tolerance | Quality-weighted | Simple base-by-base |
| Seed heuristics | May miss some high-mismatch sites | Exhaustive enumeration |
| Bulge/indel support | No | Yes (Cas-OFFinder) |
| PAM-aware ranking | No (post-hoc extraction) | Built-in |
| Speed | Fast (BWA) | Moderate |

**BWA results are approximate candidates.** They should be validated against CRISPOR or other dedicated tools for publication-quality analysis.

### Known Gaps

- Bulges and indels are not detected (BWA is gap-free in this configuration)
- `max_mismatches > 5` may be slow or produce false negatives due to BWA seed heuristics
- PAM extraction may fail for reads near contig boundaries
- Quality scores from the original FASTQ are not used (BWA aln operates on sequence only)

## Post-Search Pipeline

After `offtarget_search`, candidates should be:

1. **Scored** with `score_offtargets(spacer, candidates, pam)` — adds CFD scores (see [cfd_scoring.md](cfd_scoring.md))
2. **Ranked** with `rank_candidates(guides, off_targets)` — aggregates evidence

## Provenance

- Alignment: BWA (bwa aln + bwa samse)
- PAM extraction: samtools faidx
- CFD scoring: CRISPOR pickle resources (Doench et al. 2016) — see [cfd_scoring.md](cfd_scoring.md)
- All tool outputs include metadata indicating the source tool and version
