# Seed GC Content

## Purpose

`compute_seed_gc` is a deterministic sequence-analysis tool that computes GC content specifically over the PAM-proximal seed region of SpCas9 guide candidates.

**This tool produces seed-region GC features for downstream VEYRA reasoning/ranking.** It does NOT directly predict Cas9 specificity, cleavage, or replace mismatch analysis.

## Position Convention

VEYRA's biological 1-based position convention:

- Position 1 = 5' end of spacer
- Position N = PAM-proximal nucleotide

For a default 20-nt SpCas9 spacer with `seed_region_length = 10`:

- **Seed region**: positions 11-20 (PAM-proximal 10 nt)
- **Distal region**: positions 1-10

This is consistent with `compute_positional_features` and all other VEYRA tools.

## Parameters

| Parameter | Type | Default | Valid values/range | Description |
|-----------|------|---------|-------------------|-------------|
| `sequence` | string | required | IUPAC characters | DNA sequence to analyze |
| `seed_region_length` | int | 10 | > 0, <= sequence length | Length of the seed region |
| `seed_anchor` | string | "pam_proximal" | "pam_proximal" | Anchor point for seed extraction |
| `seed_min_threshold` | float | 0.20 | [0, 1] | Minimum GC fraction for pass filter |
| `seed_max_threshold` | float | 0.80 | [0, 1] | Maximum GC fraction for pass filter |
| `compute_seed_distal_delta` | bool | false | true/false | Whether to compute distal GC and delta |
| `round_decimals` | int | 3 | >= 0 | Decimal places for rounding output |

## Seed Extraction

For `seed_anchor = "pam_proximal"`:

```
seed_start = sequence_length - seed_region_length + 1  (1-based)
seed_end = sequence_length                              (1-based)
```

Example for 20-nt spacer, 10-nt seed:

```
positions 1-10:   distal region
positions 11-20:  seed region
```

Example for 20-nt spacer, 6-nt seed:

```
positions 1-14:   distal region
positions 15-20:  seed region
```

## GC Calculation

```
seed_gc_content = (G + C) / seed_length
```

Returns a fraction in [0, 1], not a percentage.

### Ambiguity Policy

Consistent with `compute_gc_content`:

- IUPAC ambiguous bases (N, R, Y, etc.) are NOT counted as G or C in the numerator
- Ambiguous bases ARE counted in the denominator

This ensures consistent GC semantics across all VEYRA tools.

## Threshold Filter

```
passes_seed_filter = seed_min_threshold <= seed_gc_content <= seed_max_threshold
```

Uses full-precision GC for the comparison, NOT the rounded value.

Example:

- Raw seed GC = 0.1996
- Threshold = 0.20
- round_decimals = 3

The filter uses 0.1996, so it FAILS (0.1996 < 0.20), even though 0.1996 rounds to 0.200.

## Distal GC and Delta

When `compute_seed_distal_delta = true`:

```
distal_gc_content = GC of non-seed portion
seed_distal_gc_delta = seed_gc_content - distal_gc_content
```

Positive delta: seed is more GC-rich than distal region
Negative delta: seed is less GC-rich than distal region

When distal region is empty (seed spans entire sequence):

- `distal_gc_content = null`
- `seed_distal_gc_delta = null`
- Warning returned

When `compute_seed_distal_delta = false`:

- `distal_gc_content = null`
- `seed_distal_gc_delta = null`

## Rounding

Calculations at full precision internally. `round_decimals` applied only to returned floating-point values. Threshold decisions always use full precision.

## Output Schema

```json
{
  "tool": "compute_seed_gc",
  "rows": [...],
  "summary": {
    "sequence_length": 20,
    "seed_region_length": 10,
    "seed_anchor": "pam_proximal",
    "seed_start_position": 11,
    "seed_end_position": 20,
    "seed_gc_content": 0.5,
    "passes_seed_filter": true,
    "distal_gc_content": 0.5,
    "seed_distal_gc_delta": 0.0
  },
  "metadata": {
    "seed_min_threshold": 0.20,
    "seed_max_threshold": 0.80,
    "compute_seed_distal_delta": true,
    "round_decimals": 3,
    "position_convention": "1-based biological positions",
    "gc_ambiguity_policy": "IUPAC ambiguous bases counted in denominator but not GC numerator",
    "scoring_note": "Seed GC feature for downstream VEYRA reasoning/ranking. NOT a specificity or efficacy prediction."
  }
}
```

## Usage

### CLI

```bash
# Basic usage
python -m cli.main sequence seed-gc --sequence GCGCGCGCGCGCGCGCGCGG

# With distal delta
python -m cli.main sequence seed-gc \
    --sequence GCGCGCGCGCGCGCGCGCGG \
    --compute-seed-distal-delta

# Custom seed length and thresholds
python -m cli.main sequence seed-gc \
    --sequence GCGCGCGCGCGCGCGCGCGG \
    --seed-region-length 6 \
    --seed-min-threshold 0.3 \
    --seed-max-threshold 0.7
```

### Python API

```python
from api import compute_seed_gc

result = compute_seed_gc("GCGCGCGCGCGCGCGCGCGG")
print(result.summary["seed_gc_content"])  # 0.5
print(result.summary["passes_seed_filter"])  # True
```

### HTTP API

```bash
curl -X POST http://localhost:8000/sequence/seed-gc \
    -H "Content-Type: application/json" \
    -d '{"sequence": "GCGCGCGCGCGCGCGCGCGG", "compute_seed_distal_delta": true}'
```

### MCP

```python
from mcp.tools.compute_seed_gc import compute_seed_gc

result = compute_seed_gc("GCGCGCGCGCGCGCGCGCGG")
print(result.summary["seed_gc_content"])  # 0.5
```

## Computational Cost

Cheap / deterministic — O(n) where n is the sequence length. Suitable for agent workflows.

## Limitations

- This tool is a raw feature extractor, NOT a specificity predictor
- Thresholds are configurable heuristics, not universal biological limits
- Does not replace mismatch analysis or CFD scoring
- Only `pam_proximal` anchor is currently supported
- For very short sequences, the distal region may be empty
