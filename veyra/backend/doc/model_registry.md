# Model Registry

## Overview

The VEYRA Model Registry (`backend/core/model_registry.py`) manages availability, compatibility, and selection of ML models for on-target efficiency prediction. It provides **explicit selection** (no fallback) and **automatic selection** (with transparent fallback).

## Architecture

```
model_registry.py
├── ModelInfo (dataclass)
│   ├── model_id
│   ├── display_name
│   ├── description
│   ├── priority (auto-selection ordering)
│   ├── status (verified/incompatible/not_installed/experimental/broken)
│   ├── version
│   ├── source
│   ├── license
│   ├── input_requirements
│   └── notes
│
├── MODEL_REGISTRY (dict[str, ModelInfo])
│
├── get_model_registry() → list[ModelInfo]
├── get_model_info(model_id) → ModelInfo | None
├── select_model(requested_model, context_sequence) → ModelSelection
│   ├── selection_status: selected | failed
│   ├── model_used
│   ├── fallback_used: bool
│   ├── fallback_chain: list[FallbackStep]
│   └── errors: list[str]
├── get_model_fallback_info(model_id) → dict
└── get_auto_model_priority() → list[str]
```

## Models in Registry

| Model ID | Display Name | Priority | Status | Reason |
|----------|--------------|----------|--------|--------|
| `rule_set_3` | Rule Set 3 (Doench 2021) | 1 | `incompatible` | rs3 v0.0.15 has lightgbm 4.7.0 sklearn API incompatibility: `TypeError: '>' not supported between instances of 'NoneType' and 'int'` |
| `rule_set_2` | Rule Set 2 (Doench 2016/Azimuth) | 2 | `incompatible` | Pickled model `V3_model_nopos.pickle` requires sklearn ≤0.16.1; installed version is 1.9.0 (`ModuleNotFoundError: No module named 'sklearn.ensemble._gb_losses'`) |
| `doench_2014` | Doench 2014 (Rule Set 1) | 3 | `verified` | Pure Python implementation, no external ML dependencies |

## Selection Logic

### Explicit Selection (`model="rule_set_2"`, `"rule_set_3"`, `"doench_2014"`)

- Never falls back
- Returns error if requested model is not `verified`
- User gets: `"explicit model request cannot be satisfied"`

### Auto Selection (`model="auto"`)

1. Query `MODEL_REGISTRY` for all models with status `verified`
2. Sort by `priority` (ascending = highest priority first)
3. Return highest-priority verified model
4. Include full `fallback_chain` showing every model considered, its status, and reason

### Both Selection (`model="both"`)

- Legacy alias for `auto`
- Behaves identically to `auto`

## Fallback Chain Format

```python
[
    {"model": "rule_set_3", "status": "incompatible", "reason": "lightgbm error"},
    {"model": "rule_set_2", "status": "incompatible", "reason": "sklearn version conflict"},
    {"model": "doench_2014", "status": "verified", "reason": "selected"},
]
```

## CLI Commands

| Command | Output | Description |
|---------|--------|-------------|
| `veysa models list` | JSON | All models with status and priority |
| `veysa models describe rule_set_2` | JSON | Detailed model info including input requirements |
| `veysa models check` | JSON | Availability check and dependency diagnostics |

## Python API

```python
from core.model_registry import (
    get_model_registry,
    get_model_info,
    select_model,
    get_auto_model_priority,
    get_model_fallback_info,
)

# List all models
registry = get_model_registry()
for m in registry:
    print(f"{m.model_id}: {m.status}")

# Get specific model info
info = get_model_info("doench_2014")

# Auto-select model
selection = select_model("auto", context_sequence="AAAAA...")
print(selection.model_used)        # "doench_2014"
print(selection.fallback_chain)    # Full decision trace

# Check availability
fallback_info = get_model_fallback_info("rule_set_2")
# Returns: {"status": "incompatible", "fallback_to": "doench_2014", "reason": "..."}
```

## Status Values

| Status | Meaning |
|--------|---------|
| `verified` | Tested and working |
| `incompatible` | Model files present but runtime incompatible |
| `not_installed` | Model package not installed |
| `experimental` | Experimental, not recommended for production |
| `broken` | Model files corrupted or incomplete |

## Adding a New Model

1. Add entry to `MODEL_REGISTRY` in `backend/core/model_registry.py`
2. Implement prediction in `backend/core/ontarget.py` (e.g., `_predict_new_model()`)
3. Add model case to `select_model()` dispatch
4. Add to CLI model choices in `backend/cli/main.py`
5. Add schema validation if needed in `backend/schemas/canonical.py`
6. Add tests in `tests/test_interfaces.py`
7. Update this documentation