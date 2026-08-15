# Homopolymer Runs Detection

## Purpose

`check_homopolymer_runs` is a deterministic, cheap sequence-analysis tool that detects homopolymer runs (poly-T, poly-G, etc.) in DNA sequences.

**This tool produces sequence-level heuristics.** It does NOT predict transcription termination, G-quadruplex formation, or CRISPR efficacy.

## Run Detection

Scans for contiguous runs of identical bases. A run is flagged when its length >= `homopolymer_min_run`.

Uses **0-based half-open [start, end)** coordinate convention, consistent with the GC sliding-window tool.

## Parameters

| Parameter | Type | Default | Valid values/range | Description |
|-----------|------|---------|-------------------|-------------|
| `sequence` | string | required | IUPAC DNA | DNA sequence to analyze |
| `homopolymer_min_run` | int | 4 | >= 2 | Minimum run length to flag |
| `polyT_strict` | bool | true | true/false | Poly-T runs cause filter failure |
| `polyG_strict` | bool | false | true/false | Poly-G runs cause filter failure |
| `check_bases` | string | "ACGT" | Subset of ACGT | Bases to scan for runs |
| `return_run_positions` | bool | false | true/false | Include run position details |

## Poly-T Detection

Detects runs where `base == "T"` and `length >= homopolymer_min_run`.

- **polyT_strict = true**: qualifying poly-T runs cause `passes_filter = false`
- **polyT_strict = false**: poly-T runs are flagged but do not cause failure

**Scientific caveat**: poly-T flags relate to Pol III transcription termination risk. This is a sequence-level heuristic, NOT direct experimental evidence.

## Poly-G Detection

Detects runs where `base == "G"` and `length >= homopolymer_min_run`.

- **polyG_strict = true**: qualifying poly-G runs cause `passes_filter = false`
- **polyG_strict = false**: poly-G runs are flagged but do not cause failure

**Scientific caveat**: poly-G flags relate to potential G-quadruplex formation risk. This does NOT prove a G-quadruplex forms.

## Pass/Fail Logic

```python
fails = False
if polyT_strict and polyT_flag:
    fails = True
if polyG_strict and polyG_flag:
    fails = True

passes_filter = not fails
```

A run can be present without causing failure when strict mode is disabled.

## Output Schema

```json
{
  "tool": "check_homopolymer_runs",
  "rows": [...],
  "summary": {
    "sequence_length": 20,
    "polyT_flag": true,
    "polyG_flag": false,
    "homopolymer_max_run": 4,
    "passes_filter": false,
    "runs": [
      {"base": "T", "start": 3, "end": 7, "length": 4}
    ]
  },
  "metadata": {
    "homopolymer_min_run": 4,
    "polyT_strict": true,
    "polyG_strict": false,
    "check_bases": "ACGT",
    "return_run_positions": false,
    "scoring_note": "Homopolymer flags are sequence-level heuristics..."
  }
}
```

## Usage

### CLI

```bash
python -m cli.main sequence homopolymer --sequence TTTTGCGCGCGG
python -m cli.main sequence homopolymer --sequence TTTTGCGCGCGG --homopolymer-min-run 4 --polyT-strict true --polyG-strict false
```

### Python API

```python
from api import check_homopolymer_runs

result = check_homopolymer_runs("ACGTTTTACGT")
print(result.summary["polyT_flag"])  # True
print(result.summary["passes_filter"])  # False (polyT_strict=True by default)
```

### HTTP API

```bash
curl -X POST http://localhost:8000/sequence/homopolymer \
    -H "Content-Type: application/json" \
    -d '{"sequence": "ACGTTTTACGT"}'
```

### MCP

```python
from mcp.tools.check_homopolymer_runs import check_homopolymer_runs

result = check_homopolymer_runs("ACGTTTTACGT")
```

## Computational Cost

O(n) where n = sequence length. Suitable for agent workflows.

## Limitations

- Only detects contiguous runs of identical bases
- Does not predict biological effects (transcription termination, G-quadruplex formation)
- IUPAC ambiguity codes do not participate in run detection
- Strict mode is a heuristic filter, not a biological safety criterion
