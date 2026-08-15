# Dinucleotide Composition

## Purpose

`compute_dinucleotide_composition` is a deterministic sequence-analysis tool that extracts position-anchored k-mer/dinucleotide features for SpCas9 candidate spacer sequences.

**This tool produces raw features for downstream ML/scoring systems.** It does NOT predict guide efficacy, reproduce Azimuth, or reproduce Rule Set 2/3.

## Windowing Convention

For `spacer_length = 20` and `window_size = 2`:

```
total_windows = spacer_length - window_size + 1
              = 20 - 2 + 1
              = 19
```

Anchored windows (1-based biological positions):

- positions 1-2 → dinucleotide at [1,2]
- positions 2-3 → dinucleotide at [2,3]
- ...
- positions 19-20 → dinucleotide at [19,20]

**Public API uses 1-based biological positions.** Internally uses 0-based Python indexes.

## Parameters

| Parameter | Type | Default | Valid values/range | Description |
|-----------|------|---------|-------------------|-------------|
| `sequence` | string | required | IUPAC characters | DNA sequence to analyze |
| `spacer_length` | int | 20 | > 0 | Expected spacer length |
| `window_size` | int | 2 | >= 1, <= spacer_length | k-mer window size |
| `return_full_matrix` | bool | false | true/false | Include per-position anchored rows |
| `normalize_counts` | bool | false | true/false | Include normalized frequencies |
| `target_dinucleotides` | list[str] | [] | length == window_size | Specific k-mers to report |

## Aggregate Counts

When `return_full_matrix = false`:

```json
{
  "window_size": 2,
  "total_windows": 19,
  "counts": {
    "GC": 9,
    "CG": 9,
    "GG": 1
  },
  "frequencies": {
    "GC": 0.4737,
    "CG": 0.4737,
    "GG": 0.0526
  }
}
```

When `normalize_counts = false`:

- `counts` contains raw integer counts
- `frequencies` is NOT included

When `normalize_counts = true`:

- `counts` contains raw integer counts
- `frequencies` contains `count / total_windows` for each observed k-mer

## Target Filter

When `target_dinucleotides = ["GC", "TT"]`:

- Only report GC and TT in `counts`/`frequencies`
- If a target has zero occurrences, include it with `count = 0`
- Do NOT silently omit zero-count targets

## Full Position-Anchored Matrix

When `return_full_matrix = true`:

```json
{
  "full_matrix": [
    {"position_start": 1, "position_end": 2, "kmer": "GC", "occurrence_index": 1},
    {"position_start": 2, "position_end": 3, "kmer": "CG", "occurrence_index": 1},
    ...
  ]
}
```

Each row represents a single positional occurrence. `occurrence_index` tracks which occurrence of that k-mer this is (1-based).

When `return_full_matrix = false`: `full_matrix = null`

## Ambiguous Bases

IUPAC ambiguous characters are allowed in input (validated with `allow_iupac=True`).

If a k-mer contains an ambiguous base (e.g., "NG"):

- The literal k-mer is preserved and counted
- It is NOT silently mapped to A/C/G/T

This is consistent with the positional-feature behavior in `compute_positional_features`.

## Validation

- `sequence`: non-empty, IUPAC characters allowed
- `spacer_length`: positive integer, sequence must be >= spacer_length
- `window_size`: positive integer, must be <= spacer_length
- `target_dinucleotides`: list of strings, each with length == window_size, valid IUPAC characters only
- Duplicate targets are automatically deduplicated with a warning

## Output Schema

### Summary Mode (`return_full_matrix = false`)

```json
{
  "tool": "compute_dinucleotide_composition",
  "rows": [...],
  "summary": {
    "sequence_length": 20,
    "spacer_length": 20,
    "window_size": 2,
    "total_windows": 19,
    "counts": {"GC": 9, "CG": 9, "GG": 1},
    "frequencies": {"GC": 0.4737, "CG": 0.4737, "GG": 0.0526},
    "target_dinucleotides": ["CG", "GC", "GG"],
    "normalize_counts": true,
    "return_full_matrix": false,
    "full_matrix": null
  },
  "metadata": {
    "position_convention": "1-based biological positions",
    "window_formula": "total_windows = spacer_length - window_size + 1 = 19",
    "scoring_note": "Dinucleotide composition features for downstream ML/scoring. NOT an efficacy prediction."
  }
}
```

### Full Matrix Mode (`return_full_matrix = true`)

```json
{
  "summary": {
    "full_matrix": [
      {"position_start": 1, "position_end": 2, "kmer": "GC", "occurrence_index": 1},
      {"position_start": 2, "position_end": 3, "kmer": "CG", "occurrence_index": 1},
      ...
    ]
  }
}
```

## Usage

### CLI

```bash
# Basic usage
python -m cli.main sequence dinucleotide-composition --sequence GCGCGCGCGCGCGCGCGCGG

# With normalized frequencies
python -m cli.main sequence dinucleotide-composition \
    --sequence GCGCGCGCGCGCGCGCGCGG \
    --normalize-counts

# With full matrix
python -m cli.main sequence dinucleotide-composition \
    --sequence GCGCGCGCGCGCGCGCGCGG \
    --return-full-matrix

# With target filtering
python -m cli.main sequence dinucleotide-composition \
    --sequence GCGCGCGCGCGCGCGCGCGG \
    --target-dinucleotides GC CG
```

### Python API

```python
from api import compute_dinucleotide_composition

result = compute_dinucleotide_composition("GCGCGCGCGCGCGCGCGCGG")
print(result.summary["counts"])  # {"GC": 9, "CG": 9, "GG": 1}
```

### HTTP API

```bash
curl -X POST http://localhost:8000/sequence/dinucleotide-composition \
    -H "Content-Type: application/json" \
    -d '{"sequence": "GCGCGCGCGCGCGCGCGCGG", "normalize_counts": true}'
```

### MCP

```python
from mcp.tools.compute_dinucleotide_composition import compute_dinucleotide_composition

result = compute_dinucleotide_composition("GCGCGCGCGCGCGCGCGCGG")
print(result.summary["counts"])  # {"GC": 9, "CG": 9, "GG": 1}
```

## Computational Cost

Cheap / deterministic — O(n) where n is the spacer length. Suitable for agent workflows.

## Limitations

- This tool is a raw feature extractor, NOT an efficacy predictor
- Does not reproduce Rule Set 2/3 or Azimuth
- Ambiguous bases in k-mers are counted as-is, not resolved
- For very large window sizes, the number of possible k-mers grows exponentially
- The `window_size` parameter exists for future extensibility; currently optimized for dinucleotides (window_size=2)
