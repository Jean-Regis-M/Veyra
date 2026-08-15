# Positional Features

## Purpose

`compute_positional_features` is a deterministic sequence-analysis tool that extracts positional nucleotide identity features for SpCas9 candidate spacer sequences.

**This tool produces positional features for downstream ML/scoring systems.** It does NOT predict guide efficacy, cleavage rate, or replace Azimuth/Rule Set models.

## Position Convention

This tool uses **1-based biological positions**:

- Position 1 = 5' end of spacer
- Position N = PAM-proximal nucleotide (nearest the PAM)

For default SpCas9 with `spacer_length = 20`:

- Position 20 = PAM-proximal nucleotide

**Internal implementation uses 0-based Python indexes**, but all public API/output uses 1-based biological positions.

## Spacer Orientation

The sequence provided to this tool must already be in the orientation that should be scored. The tool does NOT reverse-complement automatically. Upstream PAM/candidate logic is responsible for providing the correctly oriented spacer.

## Parameters

| Parameter | Type | Default | Valid values/range | Description |
|-----------|------|---------|-------------------|-------------|
| `sequence` | string | required | Standard ACGT (IUPAC allowed) | DNA sequence to analyze |
| `spacer_length` | int | 20 | > 0 | Expected spacer length |
| `return_onehot` | bool | true | true/false | Include per-position one-hot encoding |
| `check_position20_bias` | bool | true | true/false | Check position-20 PAM-proximal bias |
| `custom_check_positions` | list[int] | [] | positions >= 1, <= spacer_length | 1-based positions to extract |
| `onehot_alphabet` | string | "ACGT" | non-empty, unique chars | Alphabet for one-hot encoding |

## One-Hot Encoding

When `return_onehot = true`, creates a per-position one-hot encoding vector.

For default `onehot_alphabet = "ACGT"`:

```yaml
position: 1
base: A
encoding:
  A: 1
  C: 0
  G: 0
  T: 0
encoded: true
```

### Ambiguous Bases

For ambiguous IUPAC symbols (e.g., N, R, Y) not present in the alphabet:

- `encoded = false`
- All zeros in encoding vector
- `base` preserves the original ambiguous character

Example for N:

```yaml
position: 1
base: N
encoding:
  A: 0
  C: 0
  G: 0
  T: 0
encoded: false
```

If the user extends `onehot_alphabet` to include ambiguity symbols, those symbols are encoded directly.

## Position-20 Bias

When `check_position20_bias = true`, inspects biological position 20 (PAM-proximal nucleotide for SpCas9).

### Heuristic

| Base | Flag | Description |
|------|------|-------------|
| G | `favored` | Known favorable position-20 base for SpCas9 |
| T | `disfavored` | Known disfavored position-20 base for SpCas9 |
| A | `neutral` | No specific heuristic |
| C | `neutral` | No specific heuristic |

**Important**: This is a categorical feature/heuristic, NOT a numerical efficacy penalty. Do NOT claim this rule universally predicts Cas9 activity.

### When Disabled

When `check_position20_bias = false`:

- `position20_base = null`
- `position20_bias_flag = "neutral"`

## Custom Position Checks

When `custom_check_positions = [1, 5, 10, 20]`, returns the identity of those positions:

```yaml
custom_positions:
  - position: 1
    base: A
  - position: 5
    base: G
  - position: 10
    base: T
  - position: 20
    base: G
```

When the list is empty: `custom_positions = []`.

## Validation

- `sequence`: non-empty, IUPAC characters allowed
- `spacer_length`: positive integer, sequence must be >= spacer_length
- `onehot_alphabet`: non-empty string, unique characters, alphabetic only
- `custom_check_positions`: integers >= 1, <= spacer_length
- If sequence is shorter than `spacer_length`: structured validation error

## Output Schema

```json
{
  "tool": "compute_positional_features",
  "rows": [...],
  "summary": {
    "sequence_length": 20,
    "spacer_length": 20,
    "spacer": "GCGCGCGCGCGCGCGCGCGG",
    "position20_base": "G",
    "position20_bias_flag": "favored",
    "custom_positions": [],
    "onehot": [
      {"position": 1, "base": "G", "encoding": {"A": 0, "C": 0, "G": 1, "T": 0}, "encoded": true},
      ...
    ]
  },
  "metadata": {
    "onehot_alphabet": "ACGT",
    "check_position20_bias": true,
    "custom_check_positions": [],
    "position_convention": "1-based biological positions (position 1 = 5' end, position N = PAM-proximal)",
    "scoring_note": "Positional features for downstream ML/scoring systems. NOT an efficacy prediction."
  }
}
```

## Usage

### CLI

```bash
# Basic usage
python -m cli.main sequence positional-features --sequence GCGCGCGCGCGCGCGCGCGG

# With custom positions
python -m cli.main sequence positional-features \
    --sequence GCGCGCGCGCGCGCGCGCGG \
    --custom-check-positions 1 10 20

# Disable one-hot
python -m cli.main sequence positional-features \
    --sequence GCGCGCGCGCGCGCGCGCGG \
    --no-onehot

# Custom alphabet
python -m cli.main sequence positional-features \
    --sequence GCGCGCGCGCGCGCGCGCGG \
    --onehot-alphabet ACGTN
```

### Python API

```python
from api import compute_positional_features

result = compute_positional_features("GCGCGCGCGCGCGCGCGCGG")
print(result.summary["position20_base"])  # "G"
print(result.summary["position20_bias_flag"])  # "favored"
```

### HTTP API

```bash
curl -X POST http://localhost:8000/sequence/positional-features \
    -H "Content-Type: application/json" \
    -d '{"sequence": "GCGCGCGCGCGCGCGCGCGG", "return_onehot": true}'
```

### MCP

```python
from mcp.tools.compute_positional_features import compute_positional_features

result = compute_positional_features("GCGCGCGCGCGCGCGCGCGG")
print(result.summary["onehot"][0])  # First position encoding
```

## Computational Cost

Cheap / deterministic — O(n) where n is the spacer length. Suitable for agent workflows.

## Limitations

- Position-20 heuristic is a categorical feature, not a validated efficacy score
- One-hot encoding uses the caller-specified alphabet; ambiguous bases outside the alphabet are not encoded
- The tool does not validate spacer orientation; upstream logic must provide correctly oriented sequences
- This tool is a feature extractor, NOT an efficacy predictor
