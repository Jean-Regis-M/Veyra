# Secondary Structure / MFE Computation

## Purpose

`compute_secondary_structure` is a deterministic sequence-analysis tool that estimates minimum free energy (MFE) and optional dot-bracket secondary structure for DNA sequences.

**This tool produces predicted thermodynamic stability features.** It does NOT predict Cas9 cleavage efficiency, guide efficacy, RNP assembly success, or therapeutic safety.

## Folding Engine

Uses **ViennaRNA 2.7.2** Python bindings for established nearest-neighbor thermodynamic folding.

**Important**: DNA sequences are converted to RNA (T→U) before folding because ViennaRNA operates on RNA. The thermodynamic parameters used are for RNA folding, not DNA. This is a documented limitation.

## Parameters

| Parameter | Type | Default | Valid values/range | Description |
|-----------|------|---------|-------------------|-------------|
| `sequence` | string | required | Standard ACGT | DNA sequence to analyze |
| `mfe_include_scaffold` | bool | false | true/false | Fold sequence + scaffold together |
| `scaffold_sequence` | string | "" | RNA alphabet | Scaffold RNA sequence (required when mfe_include_scaffold=true) |
| `temperature_celsius` | float | 37.0 | [0, 100] | Folding temperature in °C |
| `return_structure_string` | bool | false | true/false | Include dot-bracket structure |
| `mfe_threshold` | float | -5.0 | any numeric | MFE threshold for pass/fail filter |

## Spacer-Only Mode

When `mfe_include_scaffold = false` (default):

- Folds only the provided `sequence`
- Returns `mfe_kcal_mol` for the spacer alone
- `scaffold_length = null` in metadata

## Spacer + Scaffold Mode

When `mfe_include_scaffold = true`:

- Requires `scaffold_sequence != ""`
- Folds `sequence + scaffold_sequence` as a concatenated RNA molecule
- Returns `mfe_kcal_mol` for the combined structure
- `scaffold_length` reported in metadata
- The caller must explicitly provide the scaffold; no default scaffold is assumed

## MFE Threshold

```python
passes_mfe_filter = mfe <= mfe_threshold
```

- When `mfe <= mfe_threshold`: `passes_mfe_filter = true`
- When `mfe > mfe_threshold`: `passes_mfe_filter = false`

**Scientific caveat**: A strongly negative MFE does NOT by itself prove poor Cas9 loading. This threshold is a configurable heuristic for downstream VEYRA reasoning.

## Structure String

When `return_structure_string = true`:

- Returns standard dot-bracket notation from ViennaRNA
- `.` = unpaired base
- `(` = paired base (opening)
- `)` = paired base (closing)
- Structure corresponds to the exact sequence that was folded (spacer only or spacer + scaffold)

When `return_structure_string = false`:

- `structure_string = null`

## Output Schema

```json
{
  "tool": "compute_secondary_structure",
  "rows": [...],
  "summary": {
    "sequence_length": 20,
    "mfe_kcal_mol": -16.7,
    "passes_mfe_filter": true,
    "structure_string": "(((((((((....))))))))"
  },
  "metadata": {
    "folded_length": 20,
    "mfe_include_scaffold": false,
    "temperature_celsius": 37.0,
    "scaffold_length": null,
    "mfe_threshold": -5.0,
    "folding_engine": "ViennaRNA",
    "folding_engine_version": "2.7.2",
    "dependency_available": true,
    "scoring_note": "MFE describes predicted thermodynamic stability..."
  }
}
```

## Dependency Handling

When ViennaRNA is NOT installed:

- Tool returns a structured error message
- `dependency_available = false` in metadata
- No fabricated MFE values

When ViennaRNA IS installed:

- `dependency_available = true`
- Folding proceeds normally

## Usage

### CLI

```bash
# Spacer-only
python -m cli.main sequence secondary-structure --sequence GCGCGCGCGCGCGCGCGCGC

# With structure string
python -m cli.main sequence secondary-structure --sequence GCGCGCGCGCGCGCGCGCGC --return-structure-string

# With scaffold
python -m cli.main sequence secondary-structure \
    --sequence GCGCGCGCGCGCGCGCGCGC \
    --mfe-include-scaffold \
    --scaffold-sequence "GAAUACCGCUAGCUAGCUAGCUAGCUAGCUAG"

# Custom temperature
python -m cli.main sequence secondary-structure --sequence GCGCGCGCGCGCGCGCGCGC --temperature-celsius 25
```

### Python API

```python
from api import compute_secondary_structure

result = compute_secondary_structure("GCGCGCGCGCGCGCGCGCGC", return_structure_string=True)
print(result.summary["mfe_kcal_mol"])  # -16.7
print(result.summary["structure_string"])  # ((((((((....))))))))
```

### HTTP API

```bash
curl -X POST http://localhost:8000/sequence/secondary-structure \
    -H "Content-Type: application/json" \
    -d '{"sequence": "GCGCGCGCGCGCGCGCGCGC", "return_structure_string": true}'
```

### MCP

```python
from mcp.tools.compute_secondary_structure import compute_secondary_structure

result = compute_secondary_structure("GCGCGCGCGCGCGCGCGCGC", return_structure_string=True)
print(result.summary["mfe_kcal_mol"])  # -16.7
```

## Computational Cost

Moderate — ViennaRNA uses dynamic programming with O(n³) complexity for structure prediction. More expensive than GC content or homopolymer detection but suitable for agent workflows.

## Limitations

- DNA sequences are converted to RNA (T→U) for folding; thermodynamic parameters are for RNA
- ViennaRNA must be installed as a dependency
- MFE is a prediction, not experimental evidence
- Structure string is predicted secondary structure, not experimental
- Scaffold sequence must be provided explicitly; no default scaffold is assumed
- Temperature range limited to [0, 100]°C by ViennaRNA
