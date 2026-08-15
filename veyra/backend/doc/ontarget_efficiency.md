# On-Target Efficiency Prediction

## Overview

The `predict_ontarget_efficiency` tool predicts the on-target cleavage efficiency of SpCas9 guide RNAs. This is fundamentally different from off-target specificity scoring (CFD) — it answers: **"How efficiently is this intended guide expected to cut its target?"**

## Model Selection System

VEYRA implements a **model registry** with automatic fallback and **transparent reporting**.

### Supported Models

| Model ID | Display Name | Priority (Auto) | Status |
|----------|--------------|-----------------|--------|
| `rule_set_3` | Rule Set 3 (Doench 2021) | 1 (highest) | **VERIFIED** (rs3 + LightGBM compatibility shim) |
| `rule_set_2` | Rule Set 2 (Doench 2016 / Azimuth / Fusi) | 2 | INCOMPATIBLE (sklearn version) |
| `doench_2014` | Doench 2014 (Rule Set 1) | 3 (fallback) | **VERIFIED** |

### Selection Modes

**Explicit Selection** (never falls back):
- `model="rule_set_3"` — Use Rule Set 3 specifically, error if unavailable
- `model="rule_set_2"` — Use Rule Set 2 specifically, error if unavailable
- `model="doench_2014"` — Use Doench 2014 specifically

**Automatic Selection** (falls back with full transparency):
- `model="auto"` — Choose highest-priority verified model
- `model="both"` — Legacy alias for `auto`

**Auto Priority Order**: `rule_set_3` > `rule_set_2` > `doench_2014`  
(Only among verified models)

Rule Set 3 returns its native activity score, which is not bounded to 0–1;
VEYRA does not apply an unvalidated probability normalization. Doench 2014
remains on a 0–1 scale.

### Fallback Transparency

When `model="auto"` falls back, the response includes:

```json
{
  "requested_model": "auto",
  "model_used": "rule_set_3",
  "selection_status": "selected",
  "fallback_used": false,
  "fallback_chain": [
    {"model": "rule_set_3", "status": "verified", "reason": "selected"},
    {"model": "rule_set_2", "status": "incompatible", "reason": "sklearn version conflict"},
    {"model": "doench_2014", "status": "verified", "reason": "selected"}
  ]
}
```

**Explicit model requests NEVER fall back** — they return an error if unavailable.

## Available Models Detail

### Rule Set 3 (Doench 2021)
- **Source**: Doench et al., Nature Biotechnology 2021
- **Implementation**: LightGBM gradient boosting (via rs3 package)
- **Status**: **VERIFIED** — rs3 0.0.15 runs with a compatibility shim for
  LightGBM's missing regressor `_n_classes` attribute
- **Scale**: native RS3 activity score; not bounded to 0–1
- **Reference Value**: For test sequence `AAAAGGCGCGCGCGCGCGCGGGTTTAAA`, score = `-0.9412279161596062`

### Rule Set 2 (Doench 2016 / Azimuth 2.0)
- **Source**: Doench et al., Nature Biotechnology 2016 (PMID: 26825659)
- **Implementation**: AdaBoost Regressor (scikit-learn) with nucleotide/positional features
- **Model file**: `V3_model_nopos.pickle` (AdaBoost regressor from Azimuth 2.0)
- **Status**: **INCOMPATIBLE** — Requires Python 2.7 with scikit-learn 0.17.1 (Azimuth 2.0 official specification)
- **Error**: Python 2.7 and legacy dependencies not available in current environment
- **Provisioning**: Available via `veysa models setup rule_set_2` or `veyra models setup rule_set_2` (requires Conda/micromamba)
- **Architecture**: Uses subprocess JSON protocol with isolated Python 2.7 runtime
- **Reference**: https://github.com/MicrosoftResearch/Azimuth

### Doench 2014 (Rule Set 1) — Fallback
- **Source**: Doench et al., Nature Biotechnology 2014 (PMID: 25184501)
- **Implementation**: Linear regression with position-specific nucleotide/dinucleotide weights + GC content adjustment (pure Python)
- **Status**: **VERIFIED** — Pure Python, no dependencies, always available

## Input Requirements

### Context Sequence

The tool requires a **30-nucleotide context sequence** with the following composition:

```
[4 nt upstream][20 nt spacer][3 nt PAM][3 nt downstream]
```

Example: `AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA`

- **Upstream**: 4 nt (default, configurable via `context_upstream`)
- **Spacer**: 20 nt (default, configurable via `spacer_length`)  
- **PAM**: 3 nt (NGG for SpCas9)
- **Downstream**: 3 nt (default, configurable via `context_downstream`)

### Validation Rules

1. Total context length must equal: `context_upstream + spacer_length + 3 + context_downstream`
2. Spacer must be at the correct position within the context
3. PAM must be at the expected position (after spacer)
4. Sequence must contain only valid DNA nucleotides (A, C, G, T)

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `context_sequence` | string | **required** | 30-mer context sequence |
| `model` | string | `"auto"` | `"auto"`, `"rule_set_2"`, `"rule_set_3"`, `"doench_2014"`, `"both"` |
| `context_upstream` | int | `4` | Upstream context length |
| `context_downstream` | int | `3` | Downstream context length |
| `spacer_length` | int | `20` | Spacer/protospacer length |
| `normalize_score` | bool | `false` | Normalize to [0,1] (all models already 0–1) |
| `round_decimals` | int | `3` | Decimal places for output |
| `precomputed_features` | dict | `null` | Optional precomputed features |

## Output

### Summary Fields

| Field | Description |
|-------|-------------|
| `ontarget_score_rule_set_2` | Rule Set 2 efficiency score (0–1) |
| `raw_score_rule_set_2` | Unrounded Rule Set 2 score |
| `ontarget_score_rule_set_3` | Rule Set 3 score (null if unavailable) |
| `raw_score_rule_set_3` | Unrounded Rule Set 3 score |
| `ontarget_score_doench_2014` | Doench 2014 score (0–1) |
| `raw_score_doench_2014` | Unrounded Doench 2014 score |
| `ontarget_score` | Generic score field (backward compatibility) |
| `raw_score` | Generic raw score field |
| `requested_model` | Model requested by user |
| `model_used` | Model actually used |
| `model_source` | Source description |
| `model_version` | Model version identifier |
| `output_scale` | `"0-1"` |
| `selection_status` | `"selected"` or `"failed"` |
| `fallback_used` | Boolean |
| `fallback_from` | Model fallen back from |
| `fallback_to` | Model fallen back to |
| `fallback_reason` | Reason for fallback |
| `fallback_chain` | Full decision chain |
| `normalized` | Whether score was normalized |
| `feature_source` | `"computed"` or `"precomputed"` |
| `model_version` | Model version identifier |
| `spacer` | Extracted spacer sequence |
| `pam` | Extracted PAM sequence |
| `confidence_flag` | Status: `ok`, `fallback`, `model_unavailable`, `partial`, `no_verified_model`, `execution_failed`, `context_length_mismatch` |

## Usage Examples

### Python API

```python
from api import predict_ontarget_efficiency

# Auto-selection (recommended)
result = predict_ontarget_efficiency(
    context_sequence="AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA",
    model="auto"
)

# Explicit Doench 2014
result = predict_ontarget_efficiency(
    context_sequence="AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA",
    model="doench_2014"
)

# Explicit Rule Set 2 (will error if unavailable)
result = predict_ontarget_efficiency(
    context_sequence="AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA",
    model="rule_set_2"
)

# Custom context
result = predict_ontarget_efficiency(
    context_sequence="AAAAAAAAGGCGCGCGCGCGCGCGCGGGTTTTT",
    model="auto",
    context_upstream=7,
    context_downstream=4,
    round_decimals=5
)
```

### CLI

```bash
# Auto-selection (recommended)
veyra score on-target --context-sequence AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA

# Explicit Doench 2014
veyra score on-target \
    --context-sequence AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA \
    --model doench_2014

# Explicit Rule Set 2 (will error if unavailable)
veyra score on-target \
    --context-sequence AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA \
    --model rule_set_2

# With options
veyra score on-target \
    --context-sequence AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA \
    --model auto \
    --context-upstream 4 \
    --context-downstream 3 \
    --spacer-length 20 \
    --normalize-score \
    --round-decimals 5 \
    --output-format json

# Model introspection
veyra models list
veyra models describe rule_set_2
veyra models check
```

### HTTP API

```bash
# Auto-selection
curl -X POST http://localhost:8000/score/ontarget \
  -H "Content-Type: application/json" \
  -d '{
    "context_sequence": "AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA",
    "model": "auto",
    "context_upstream": 4,
    "context_downstream": 3,
    "spacer_length": 20,
    "normalize_score": false,
    "round_decimals": 3
  }'
```

### MCP

```json
{
  "tool": "predict_ontarget_efficiency",
  "arguments": {
    "context_sequence": "AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA",
    "model": "auto"
  }
}
```

### Model Introspection CLI

```bash
# List all models with availability
veyra models list

# Describe a specific model
veyra models describe rule_set_2

# Check availability and dependencies
veyra models check
```

## Model Provenance

### Rule Set 2 (Doench 2016 / Azimuth)

- **Model file**: `V3_model_nopos.pickle` (AdaBoost regressor)
- **Source**: https://github.com/gpp-rnd/azimuth
- **Reference**: Doench et al., Nat Biotechnol 2016
- **License**: MIT (Azimuth 2.0)
- **Location**: `refrences.local/data/tools/crisporWebsite/bin/fusiDoench/saved_models/`
- **Issue**: Requires scikit-learn ≤ 0.16.1 (current: 1.9.0)

### Rule Set 3 (Doench 2021)

- **Source**: Doench et al., Nature Biotechnology 2021
- **Implementation**: LightGBM via rs3 package (PyPI)
- **Issue**: lightgbm 4.7.0 compatibility issue with rs3 0.0.15

### Doench 2014 (Fallback)

- **Implementation**: Re-implemented from crisporEffScores.py / doenchScore.py
- **Reference**: Doench et al., Nat Biotechnol 2014
- **Parameters**: Position-specific nucleotide/dinucleotide weights + GC content adjustment
- **Status**: Pure Python, no dependencies, always available

## Limitations

1. **Rule Set 2**: Requires Python 2.7 with scikit-learn 0.17.1 (Azimuth 2.0). Provisioning available via `models setup rule_set_2` (requires Conda/micromamba).
2. **Rule Set 3**: **VERIFIED** - Available in main environment with LightGBM compatibility shim.
3. **PAM specificity**: Only validated for NGG PAM (SpCas9).
4. **Sequence context**: Requires exact 30-mer composition; no auto-detection of spacer position.
5. **Species specificity**: Models trained on human cell data; may not generalize to other species.
6. **Not a clinical predictor**: Research prototype only; not for clinical or therapeutic decisions.

## Scientific Discipline

- **ON-TARGET EFFICIENCY** ≠ **OFF-TARGET SPECIFICITY**
- This tool predicts cleavage efficiency at the intended target
- CFD/scoring tools predict off-target effects
- Do not combine or confuse these distinct concepts
- No clinical efficacy, therapeutic benefit, or biological certainty claimed

## Testing

Run interface parity tests:

```bash
python -m pytest tests/test_interfaces.py::TestOnTargetEfficiencyInterfaceParity -v
```

Tests verify:
- Context validation (30-mer requirement)
- Model selection (auto, rule_set_2, rule_set_3, doench_2014)
- Explicit model error handling (no fallback)
- Auto-selection with transparent fallback chain
- Error handling (invalid model, context length mismatch)
- Normalization and rounding
- Interface parity (Python API, CLI, HTTP, MCP)
- Deterministic repeatability
- Model introspection (list, describe, check)
