# GC Content Computation

## Purpose

`compute_gc_content` is a deterministic, cheap sequence-analysis tool that computes GC content and optional derived features for a DNA sequence.

**This tool produces sequence features.** It does NOT determine CRISPR efficacy, toxicity, off-target cleavage, biological safety, or therapeutic suitability.

## Formula

```
GC content = (count of G + count of C) / sequence_length
```

Returns a fraction in **[0, 1]**, NOT 0–100. Example: 50% GC → 0.5.

## Ambiguous Base Policy

IUPAC ambiguity codes are accepted (`N`, `R`, `Y`, `S`, `W`, `K`, `M`, `B`, `D`, `H`, `V`).

- **Ambiguous bases do NOT count as G or C** in the numerator.
- **Ambiguous bases DO count** in the denominator (sequence length).
- Rationale: ambiguity means uncertainty; none of the possibilities in non-GC ambiguity classes are guaranteed to be G or C. `S` (G or C) is conservatively excluded because the caller cannot be certain.

## Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `sequence` | string | required | IUPAC DNA | DNA sequence to analyze |
| `gc_window_size` | int | 5 | > 0 | Sliding window size in nucleotides |
| `gc_split_ratio` | float | 0.5 | [0, 1] | Fraction of sequence for 5' half |
| `gc_min_threshold` | float | 0.20 | [0, 1] | Minimum GC for pass filter |
| `gc_max_threshold` | float | 0.80 | [0, 1] | Maximum GC for pass filter |
| `include_sliding_window` | bool | true | | Compute sliding-window GC |
| `include_half_split` | bool | true | | Compute 5'/3' split GC |
| `round_decimals` | int | 3 | ≥ 0 | Decimal places for rounding |

## Half-Split Behavior

The split index is computed as:

```python
split_index = floor(sequence_length * gc_split_ratio)
split_index = max(1, min(split_index, sequence_length - 1))
```

- Both halves are guaranteed non-empty (at least 1 nt each).
- For `gc_split_ratio = 0.5`: even-length sequences split at midpoint; odd-length sequences get `floor(n/2)` for 5'.
- Example: `ACGTACGT` (8 nt) → 5'=`ACGT`, 3'=`ACGT`
- Example: `ACGCG` (5 nt) → 5'=`AC` (2 nt), 3'=`GCG` (3 nt)

When `include_half_split = false`, returns `gc_5prime = null`, `gc_3prime = null`.

## Sliding-Window GC

For each valid window of size `gc_window_size`:

```python
for i in range(seq_len - window_size + 1):
    window = seq[i : i + window_size]
    gc = gc_content(window)
```

**Coordinate convention:** 0-based half-open `[start, end)` — consistent with VEYRA's coordinate convention.

Returns a list of `{"start": int, "end": int, "gc": float}` dicts.

When `include_sliding_window = false`, returns `sliding_windows = []`.

If `gc_window_size > sequence_length`, returns `sliding_windows = []` with a warning.

## Threshold Filter

```python
passes_basic_filter = gc_min_threshold <= gc_content <= gc_max_threshold
```

Returns a boolean. This is a configurable heuristic only — NOT a universal CRISPR safety or efficacy threshold.

## Output Schema

```json
{
  "tool": "compute_gc_content",
  "rows": [...],
  "summary": {
    "sequence_length": 20,
    "gc_content": 0.5,
    "gc_5prime": 0.0,
    "gc_3prime": 1.0,
    "sliding_windows": [
      {"start": 0, "end": 5, "gc": 0.6}
    ],
    "passes_basic_filter": true
  },
  "metadata": {
    "gc_window_size": 5,
    "gc_split_ratio": 0.5,
    "gc_min_threshold": 0.20,
    "gc_max_threshold": 0.80,
    "include_sliding_window": true,
    "include_half_split": true,
    "round_decimals": 3,
    "scoring_note": "GC content is a sequence feature, NOT a CRISPR safety/efficacy claim."
  }
}
```

## Usage

### CLI

```bash
python -m cli.main sequence gc --sequence GCGCGCGCGCAAAAAAAAAA
python -m cli.main sequence gc --sequence GCGCGCGCGCAAAAAAAAAA --gc-window-size 3 --round-decimals 2
python -m cli.main sequence gc --input seq.fasta
```

### Python API

```python
from api import compute_gc_content

result = compute_gc_content("GCGCGCGCGCAAAAAAAAAA")
print(result.summary["gc_content"])  # 0.5
```

### HTTP API

```bash
curl -X POST http://localhost:8000/sequence/gc \
    -H "Content-Type: application/json" \
    -d '{"sequence": "GCGCGCGCGCAAAAAAAAAA"}'
```

### MCP

```python
from mcp.tools.compute_gc_content import compute_gc_content

result = compute_gc_content("GCGCGCGCGCAAAAAAAAAA")
```

## Computational Cost

O(n) where n = sequence length. Suitable for agent workflows:

```
PAM candidate → compute_gc_content → threshold/filter → expensive analysis
```

## Limitations

- Only computes GC content — not Tm, MFE, homopolymers, or other features.
- Ambiguous bases are treated conservatively (not counted as GC).
- The threshold filter is a heuristic, not a biological claim.
