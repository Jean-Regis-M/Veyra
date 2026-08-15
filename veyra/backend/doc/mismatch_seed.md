# Mismatch/Seed Analysis

VEYRA's `analyze_mismatch_seed` tool provides alignment-aware seed region analysis for off-target candidates, including those with DNA/RNA bulges.

## Overview

```
Cas-OFFinder result
        │
        ▼
analyze_mismatch_seed
        │
        ├─ No bulge: Direct positional comparison
        │
        └─ Bulge: Alignment-aware normalization
                │
                ▼
        Seed/distal mismatch classification
```

## Seed Region Definition

The seed region is the PAM-proximal portion of the spacer:

- **Default**: Positions 11-20 from the 5' end (1-based biological positions)
- **Configurable**: `seed_region_length` parameter (default: 10)

Example for 20-nt spacer:
```
Position:  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20
Region:    |-- Distal (1-10) --|-- Seed (11-20) --|
```

## Usage

### Python API

```python
from api import analyze_mismatch_seed

# Mismatch-only candidate
result = analyze_mismatch_seed(
    spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
    candidate_sequence="GCGCGCGCGCGCGCGCGCGC",
)
print(result.summary["total_mismatches"])  # 0
print(result.summary["has_seed_mismatch"])  # False

# Bulged candidate with alignment
result = analyze_mismatch_seed(
    spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
    candidate_sequence="GCGCGCGtGCGCGCGGCGa",
    bulge_type="DNA",
    bulge_size=1,
    aligned_guide="GCGCGCGCGCGCGCG-CGCGC",
    aligned_candidate="GCGCGCGtGCGCGCGGCGa",
)
print(result.summary["bulge_type"])  # DNA
print(result.summary["total_mismatches"])  # 3
```

### MCP Tool

```json
{
  "tool": "analyze_mismatch_seed",
  "spacer_sequence": "GCGCGCGCGCGCGCGCGCGC",
  "candidate_sequence": "GCGCGCGtGCGCGCGGCGa",
  "bulge_type": "DNA",
  "bulge_size": 1,
  "aligned_guide": "GCGCGCGCGCGCGCG-CGCGC",
  "aligned_candidate": "GCGCGCGtGCGCGCGGCGa"
}
```

### HTTP API

```bash
curl -X POST http://localhost:8000/offtarget/analyze-seed \
  -H "Content-Type: application/json" \
  -d '{
    "spacer_sequence": "GCGCGCGCGCGCGCGCGCGC",
    "candidate_sequence": "GCGCGCGtGCGCGCGGCGa",
    "bulge_type": "DNA",
    "bulge_size": 1,
    "aligned_guide": "GCGCGCGCGCGCGCG-CGCGC",
    "aligned_candidate": "GCGCGCGtGCGCGCGGCGa"
  }'
```

## Output Fields

| Field | Description |
|-------|-------------|
| `total_mismatches` | Total mismatch count |
| `seed_mismatch_count` | Mismatches in seed region |
| `distal_mismatch_count` | Mismatches in distal region |
| `has_seed_mismatch` | Boolean: any seed mismatch |
| `bulge_type` | "X", "DNA", or "RNA" |
| `bulge_size` | Bulge size (0 for mismatches) |
| `seed_start_position` | 1-based start of seed region |
| `seed_end_position` | 1-based end of seed region |

## Bulge-Aware Analysis

For candidates with DNA/RNA bulges, the tool:

1. **Aligns sequences**: Uses provided alignment or infers from bulge parameters
2. **Normalizes positions**: Accounts for gaps in alignment
3. **Classifies mismatches**: Distinguishes seed vs. distal after normalization
4. **Preserves bulge info**: Reports bulge type and size

### Alignment Format

- `aligned_guide`: Guide sequence with `-` for gaps (bulges in candidate)
- `aligned_candidate`: Candidate sequence with `-` for gaps (bulges in guide)

Example:
```
Guide:      GCGCGCGCGCGCGCG-CGCGC
Candidate:  GCGCGCGtGCGCGCGGCGa
                  ^       ^
                  |       |
            Mismatch   DNA bulge
```

## Limitations

- Bulge position accuracy depends on alignment quality
- Multiple bulges may complicate positional mapping
- The tool does not re-align sequences; it uses provided alignments

## Provenance

- Tool: `analyze_mismatch_seed`
- Deterministic: Same input → same output every run
- No external dependencies beyond Python standard library
