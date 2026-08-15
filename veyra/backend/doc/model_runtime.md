# Model Runtime Manager

## Overview

The VEYRA Model Runtime Manager (`backend/core/model_runtime.py`) manages isolated Python virtual environments for on-target efficiency models. This allows models with conflicting dependency requirements (e.g., legacy scikit-learn or lightgbm versions) to coexist without polluting the main VEYRA environment.

## Architecture

VEYRA supports a **three-environment architecture** to maintain isolation and compatibility:

### Three-Environment Architecture

```
MAIN VEYRA Environment
├── Python: Current system Python (3.12.3)
├── Location: backend/venv/
└── Status: Always available, never modified

RULE SET 3 Environment  
├── Python: Python 3.x (compatible with rs3 0.0.15)
├── Location: data/model_envs/rule_set_3/
└── Status: ✅ VERIFIED (working in main env with compatibility shim)

RULE SET 2 Environment
├── Python: Python 2.7 (required by Azimuth 2.0)
├── Location: data/model_envs/rule_set_2/
└── Status: ❌ INCOMPATIBLE (requires Conda/micromamba provisioning)
```

## Cross-Platform Runtime Discovery

VEYRA automatically detects available runtimes:

### Python Runtime Discovery
- System Python 2.7 executables: `python2.7`, `python2`, `python27`
- System Python 3 executables: `python3`, `python3.12`, `python3.11`, etc.
- Conda environment managers: `conda`, `micromamba`, `mamba`

### Conda Environment Detection
- Lists existing Conda environments
- Identifies environments with Python 2.7
- Reports package manager availability

## Rule Set 2 Special Requirements

### Authoritative Specification (Azimuth 2.0)
- **Model:** Azimuth 2.0 (Microsoft Research)
- **Python:** 2.7 (primary target)
- **scikit-learn:** 0.17.1 (exact version from setup.py)
- **numpy:** >=1.9.0
- **scipy:** >=0.15.1  
- **pandas:** >=0.17.1
- **biopython:** >=1.65
- **matplotlib:** >=1.4.0
- **Source:** https://github.com/MicrosoftResearch/Azimuth

### Provisioning Strategy
1. **Linux:** Prefer Conda/micromamba environment creation
2. **Windows:** Use project-local Conda environment
3. **Fallback:** System Python 2.7 if available

### Subprocess JSON Protocol
Rule Set 2 uses isolated execution with JSON protocol:

**Request:**
```json
{
  "context_sequence": "AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA"
}
```

**Response:**
```json
{
  "status": "success",
  "model_id": "rule_set_2", 
  "model_version": "2.0",
  "score": 0.85,
  "runtime_python": "Python 2.7.18",
  "provenance": "Azimuth 2.0 (Doench et al. 2016)"
}
```

Runtime state is persisted in:
```
backend/cache/model_runtime/
├── runtimes.json        # State per model (verified, provisioned, etc.)
└── locks/{model_id}.lock # File locks for concurrent setup prevention
```

## Trusted Model Specifications

Each model has a trusted specification in `MODEL_SPECS` that defines:
- Required Python version
- Dependency version pins
- Resource locations
- Runner entrypoint
- Verification case (reference test sequence + expected output range)

### Model Specifications

| Model | Python | Dependencies | Notes |
|-------|--------|-------------|-------|
| `rule_set_2` | 3.8 | scikit-learn==0.16.1, numpy==1.16.6, pandas==0.24.2 | Pickled AdaBoost model needs legacy sklearn |
| `rule_set_3` | main Python 3.12 works | rs3==0.0.15 + installed LightGBM with compatibility shim | Native RS3 score scale; isolated spec remains available |
| `doench_2014` | any | (none) | Pure Python, no isolated runtime needed |

## Runtime State Machine

```
NOT_PROVISIONED → PROVISIONING → PROVISIONDED → VERIFYING → VERIFIED
                     ↓              ↓              ↓
              INCOMPATIBLE    INCOMPATIBLE   FAILED
```

### States

| State | Meaning |
|-------|---------|
| `not_provisioned` | No runtime exists; needs provisioning |
| `provisioning` | Currently creating venv and installing deps (transient) |
| `provisioned` | Venv + deps installed, not yet verified |
| `verifying` | Running health check (transient) |
| `verified` | Runtime exists AND passes verification — eligible for auto-selection |
| `incompatible` | Dependencies cannot be installed (e.g., package version conflicts) |
| `failed` | Verification failed or provisioning error |

**Important:** A model must be in `verified` state to be eligible for auto-selection. `provisioned` alone is not sufficient.

## Provisioning Lifecycle

### Manual Setup

```bash
# Provision a specific model
veyra models setup rule_set_3

# Force reprovision
veyra models setup rule_set_3 --force

# Setup all models
veyra models setup --all

# Verify a model
veyra models verify rule_set_3
```

### Explicit Setup (Required Before Auto Eligibility)

On-target prediction does not create virtual environments or install packages
implicitly. Use `models setup <model>` followed by `models verify <model>` (or
the equivalent HTTP/MCP runtime-management operation) to provision a declared
isolated runtime. This keeps prediction requests bounded, reproducible, and
free from package-install side effects. `model="auto"` only selects models
already marked `verified` and otherwise reports its fallback chain.

When `model="auto"` is requested, the system checks each model in priority
order (`rule_set_3 > rule_set_2 > doench_2014`) and selects the first model
already marked `verified`. It never provisions or installs packages during a
prediction request; unavailable models and the fallback chain are reported.

### Runtime Provisioning Flow

```mermaid
graph TD
    A[model="auto"] --> B{Check registry}
    B --> C[Rule Set 3 verified?]
    C -->|Yes| D[Use Rule Set 3]
    C -->|No| E[Check Rule Set 2]
    E -->|Verified| F[Use Rule Set 2]
    E -->|Not verified| G[Use Doench 2014]
    G --> H[Report fallback chain]
```

## Concurrency & Locking

File-based locks prevent concurrent provisioning of the same model:

```python
from core.model_runtime import provision_model

# Two concurrent calls will serialize
result1 = provision_model("rule_set_3")
result2 = provision_model("rule_set_3")  # Waits for lock
```

Locks are stored in `backend/cache/model_runtime/locks/`.

## Python API

```python
from core.model_runtime import (
    provision_model,
    verify_model,
    ensure_model_ready,
    get_model_status,
    list_model_runtimes,
    get_model_spec,
    RuntimeState,
)

# Provision a model
result = provision_model("rule_set_2")
# → {"action": "verified", "runtime_status": "verified", "runtime_path": "..."}

# Verify a model
result = verify_model("rule_set_2")
# → {"verification_status": "pass"}

# Ensure model is ready (provisions if needed)
model_id, status = ensure_model_ready("rule_set_3")
# → ("rule_set_3", {"state": "verified", "ready": True, "runtime_action": "auto_provisioned"})
# or → (None, {"state": "incompatible", "ready": False, "error": "...")

# Get status
status = get_model_status("doench_2014")
# → {"state": "verified", "runtime_path": "...", ...}

# List all runtimes
runtimes = list_model_runtimes()
# → [{"model_id": "rule_set_2", "state": "...", ...}, ...]

# Get trusted spec
spec = get_model_spec("rule_set_2")
# → {"model_id": "rule_set_2", "dependency_spec": {...}, ...}
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `veyra models list` | List all models with availability + runtime status |
| `veyra models describe <model>` | Detailed model info including spec |
| `veyra models check` | Check all models' availability + runtime |
| `veyra models setup <model>` | Provision isolated runtime |
| `veyra models setup --all` | Provision all models |
| `veyra models setup <model> --force` | Force reprovision |
| `veyra models verify <model>` | Run health check |

### Example Output

```
$ veyra models setup rule_set_2

Model: rule_set_2
Runtime: data/model_envs/rule_set_2
Action: PROVISIONED
Python: Python 3.8.x
Dependencies: OK (scikit-learn==0.16.1, numpy==1.16.6, pandas==0.24.2)
Reference test: PASS
Status: VERIFIED
```

## HTTP API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/models` | List all models with status |
| `GET` | `/models/{model_id}` | Detailed model info |
| `GET` | `/models/{model_id}/status` | Runtime status |
| `POST` | `/models/{model_id}/setup` | Provision runtime |
| `POST` | `/models/{model_id}/verify` | Verify runtime |

### Example

```bash
curl -X POST http://localhost:8000/models/rule_set_3/setup
# → {"success": true, "result": {"action": "verified", "runtime_status": "verified", ...}}

curl http://localhost:8000/models/doench_2014/status
# → {"state": "verified", "runtime_path": "...", ...}
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `models_list_runtimes` | List all model runtime states |
| `model_status` | Get detailed status for a model |
| `setup_model` | Provision isolated runtime (expensive) |
| `verify_model` | Run health check verification |

### Agent Instructions

The MCP tool descriptions tell AI agents:
- `setup_model` may be expensive (creates venv, installs packages)
- `setup_model` modifies ONLY project-local environments under `data/model_envs/`
- No system Python modification occurs
- Explicit model setup does NOT imply fallback to another model
- Verification is required before a model becomes auto-eligible

### Agent Workflow Example

```
Agent: predict_ontarget_efficiency(model="rule_set_3")
System: Model rule_set_3 is not verified. Would you like to set it up?
Agent: setup_model(rule_set_3)
System: [provisioning...takes ~30s...]
        Result: rule_set_3 is now verified
Agent: predict_ontarget_efficiency(model="rule_set_3")
System: Returns score from isolated runtime
```

## Security

- **No arbitrary shell execution**: Only dependencies declared in `MODEL_SPECS` can be installed
- **No caller-supplied URLs**: Model sources are from trusted specifications only
- **No system Python modification**: Only `data/model_envs/` is modified
- **No `--break-system-packages` or `sudo`**: Isolated venvs handle dependencies
- **File locking**: Prevents concurrent provisioning corruption
- **Trusted specifications**: Package names, versions, and sources are hardcoded, not caller-supplied

## Testing

Tests are in `tests/test_interfaces.py`:
- `TestModelRuntimeProvisioning` — Python API, CLI, state management
- `TestModelRuntimeHTTPAPI` — HTTP endpoints
- `TestModelRuntimeMCP` — MCP tool wrappers

Run tests:
```bash
python -m pytest tests/test_interfaces.py::TestModelRuntimeProvisioning -v
python -m pytest tests/test_interfaces.py::TestModelRuntimeHTTPAPI -v
python -m pytest tests/test_interfaces.py::TestModelRuntimeMCP -v
```
