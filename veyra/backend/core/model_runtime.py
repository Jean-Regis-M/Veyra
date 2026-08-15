"""VEYRA Model Runtime Manager.

Manages isolated Python environments for on-target efficiency models.
Each model that requires specific dependency versions gets its own venv
under data/model_envs/.

State machine per model:
    NOT_PROVISIONED → PROVISIONING → PROVISIONED → VERIFYING → VERIFIED
                          ↓              ↓              ↓
                    INCOMPATIBLE    INCOMPATIBLE   FAILED

Provisioning/modification happens only under data/ - never touches the
main backend/venv.
"""

from __future__ import annotations

import json
import os
import sys
import subprocess
import time
import fcntl
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from pathlib import Path

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

_VEYRA_DIR = os.path.dirname(_BACKEND_DIR)
_MODEL_ENVS_DIR = os.path.join(_VEYRA_DIR, "data", "model_envs")
_STATE_DIR = os.path.join(_BACKEND_DIR, "cache", "model_runtime")
_LOCK_DIR = os.path.join(_STATE_DIR, "locks")
_STATE_FILE = os.path.join(_STATE_DIR, "runtimes.json")

os.makedirs(_MODEL_ENVS_DIR, exist_ok=True)
os.makedirs(_STATE_DIR, exist_ok=True)
os.makedirs(_LOCK_DIR, exist_ok=True)


# Trusted model specifications — defines what each model needs
MODEL_SPECS: dict[str, dict[str, Any]] = {
    "rule_set_2": {
        "model_id": "rule_set_2",
        "display_name": "Rule Set 2 (Doench 2016 / Azimuth / Fusi)",
        "version": "2016",
        "source": "Doench et al., Nature Biotechnology 2016 (PMID: 26825659); Azimuth 2.0",
        "implementation": "AdaBoost Regressor (scikit-learn) with nucleotide/positional features",
        "expected_python": "3.8",  # sklearn 0.16.1 needs Python <= 3.8
        "dependency_spec": {
            "scikit-learn": "==0.16.1",
            "numpy": "==1.16.6",
            "pandas": "==0.24.2",
        },
        "resource_source": {
            "type": "file",
            "path": "refrences.local/data/tools/crisporWebsite/bin/fusiDoench/saved_models/V3_model_nopos.pickle",
        },
        "runner_entrypoint": "rs2_predict",  # internal function name
        "verification_case": {
            "context_sequence": "AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA",
            "expected_range": [-10.0, 10.0],
        },
        "license": "MIT (Azimuth 2.0)",
        "provenance": "https://github.com/gpp-rnd/azimuth",
    },
    "rule_set_3": {
        "model_id": "rule_set_3",
        "display_name": "Rule Set 3 (Doench 2021)",
        "version": "2021",
        "source": "Doench et al., Nature Biotechnology 2021",
        "implementation": "LightGBM gradient boosting (via rs3 package)",
        "expected_python": "3.8",
        "dependency_spec": {
            "rs3": "==0.0.15",
            "lightgbm": "==3.3.5",  # Older version compatible with rs3
            "scikit-learn": "==1.0.2",
            "numpy": "==1.24.0",
            "pandas": "==1.5.3",
        },
        "resource_source": {
            "type": "package",
            "name": "rs3",
            "version": "0.0.15",
        },
        "runner_entrypoint": "rs3_predict",
        "verification_case": {
            "context_sequence": "AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA",
            "expected_range": [0.0, 1.0],
        },
        "license": "MIT",
        "provenance": "https://github.com/gpp-rnd/rs3",
    },
    "doench_2014": {
        "model_id": "doench_2014",
        "display_name": "Doench 2014 (Rule Set 1)",
        "version": "2014",
        "source": "Doench et al., Nature Biotechnology 2014 (PMID: 25184501)",
        "implementation": "Linear regression with position-specific nucleotide/dinucleotide weights + GC adjustment (pure Python)",
        "expected_python": None,  # No specific Python version needed
        "dependency_spec": {},  # No external dependencies
        "resource_source": {
            "type": "builtin",
            "path": "core/ontarget.py:_predict_doench2014",
        },
        "runner_entrypoint": "doench_2014_predict",
        "verification_case": {
            "context_sequence": "AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA",
            "expected_score": 0.025,
            "expected_range": [0.0, 1.0],
        },
        "license": "Open (reimplementation of published coefficients)",
        "provenance": "http://www.broadinstitute.org/rnai/public/analysis-tools/sgrna-design",
    },
}


class RuntimeState:
    """Runtime provisioning states."""
    NOT_PROVISIONED = "not_provisioned"
    PROVISIONING = "provisioning"
    PROVISIONED = "provisioned"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    INCOMPATIBLE = "incompatible"
    FAILED = "failed"


@dataclass
class RuntimeInfo:
    """Runtime state for a model."""
    model_id: str
    state: str = RuntimeState.NOT_PROVISIONED
    runtime_path: Optional[str] = None
    python_version: Optional[str] = None
    dependencies_installed: bool = False
    installed_packages: dict[str, str] = field(default_factory=dict)
    last_error: str = ""
    last_provision_at: float = 0.0
    last_verify_at: float = 0.0
    verification_passed: bool = False
    runtime_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeInfo":
        return cls(**data)


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def _load_state() -> dict[str, RuntimeInfo]:
    """Load runtime state from disk."""
    if not os.path.exists(_STATE_FILE):
        return {}
    try:
        with open(_STATE_FILE, "r") as f:
            data = json.load(f)
        return {k: RuntimeInfo.from_dict(v) for k, v in data.items()}
    except Exception:
        return {}


def _save_state(state: dict[str, RuntimeInfo]) -> None:
    """Persist runtime state to disk."""
    os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
    with open(_STATE_FILE, "w") as f:
        json.dump({k: v.to_dict() for k, v in state.items()}, f, indent=2)


def _acquire_lock(model_id: str) -> Any:
    """Acquire a file lock for model provisioning to prevent concurrent setup."""
    os.makedirs(_LOCK_DIR, exist_ok=True)
    lock_file = os.path.join(_LOCK_DIR, f"{model_id}.lock")
    fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _release_lock(fd: int) -> None:
    """Release a file lock."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Runtime management
# ---------------------------------------------------------------------------

def get_model_spec(model_id: str) -> Optional[dict[str, Any]]:
    """Get the trusted specification for a model."""
    return MODEL_SPECS.get(model_id)


def get_model_runtime_path(model_id: str) -> str:
    """Get the filesystem path for a model's isolated runtime."""
    return os.path.join(_MODEL_ENVS_DIR, model_id)


def get_model_status(model_id: str) -> dict[str, Any]:
    """Get the runtime status for a model.

    Returns a dict with state, runtime_path, python_version,
    dependency_status, verification_status.
    """
    state = _load_state()
    info = state.get(model_id, RuntimeInfo(model_id=model_id))

    spec = MODEL_SPECS.get(model_id, {})
    runtime_path = get_model_runtime_path(model_id)

    # Determine python version
    python_version = info.python_version
    if not python_version and os.path.exists(runtime_path):
        python_bin = os.path.join(runtime_path, "bin", "python")
        if os.path.exists(python_bin):
            try:
                result = subprocess.run(
                    [python_bin, "--version"],
                    capture_output=True, text=True, timeout=10
                )
                python_version = result.stderr.strip() or result.stdout.strip()
            except Exception:
                python_version = None

    # Determine dependency status
    deps = spec.get("dependency_spec", {})
    if info.dependencies_installed:
        dep_status = "installed"
    elif info.state in (RuntimeState.PROVISIONED, RuntimeState.VERIFYING, RuntimeState.VERIFIED):
        dep_status = "installed"
    elif info.state == RuntimeState.INCOMPATIBLE:
        dep_status = "incompatible"
    else:
        dep_status = "not_installed"

    return {
        "model_id": model_id,
        "state": info.state,
        "runtime_path": runtime_path,
        "python_version": python_version,
        "expected_python": spec.get("expected_python"),
        "dependencies": spec.get("dependency_spec", {}),
        "dependency_status": dep_status,
        "installed_packages": info.installed_packages,
        "verification_status": "pass" if info.verification_passed else "pending" if info.state != RuntimeState.FAILED else "fail",
        "last_error": info.last_error,
        "last_provision_at": info.last_provision_at,
        "last_verify_at": info.last_verify_at,
        "runtime_action": info.runtime_action,
    }


def _create_isolated_venv(model_id: str, expected_python: Optional[str] = None) -> tuple[bool, str]:
    """Create an isolated Python venv for a model.

    Returns:
        (success, error_message)
    """
    runtime_path = get_model_runtime_path(model_id)

    # Check if a venv already exists
    python_bin = os.path.join(runtime_path, "bin", "python")
    if os.path.exists(python_bin):
        return True, ""

    # Try to find a compatible Python interpreter
    python_cmd = None

    # First, check if we have pyenv or similar that can provide the expected Python
    if expected_python:
        # Try specific Python versions
        for py_name in [f"python{expected_python.split('.')[0]}.{expected_python.split('.')[1]}",
                       f"python{expected_python.split('.')[0]}"]:
            try:
                result = subprocess.run(
                    ["which", py_name],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    python_cmd = result.stdout.strip()
                    break
            except Exception:
                pass

    # Fall back to current Python
    if python_cmd is None:
        python_cmd = sys.executable

    # Create venv
    try:
        subprocess.run(
            [python_cmd, "-m", "venv", runtime_path],
            capture_output=True, text=True, timeout=60, check=True
        )
        python_bin = os.path.join(runtime_path, "bin", "python")

        # Verify venv works
        result = subprocess.run(
            [python_bin, "--version"],
            capture_output=True, text=True, timeout=10
        )

        version = result.stderr.strip() or result.stdout.strip()
        return True, version
    except subprocess.CalledProcessError as e:
        return False, f"venv creation failed: {e.stderr or e.stdout or str(e)}"
    except Exception as e:
        return False, f"venv creation error: {e}"


def _install_dependencies(model_id: str, dep_spec: dict[str, str]) -> tuple[bool, str, dict[str, str]]:
    """Install dependencies into the isolated environment.

    Returns:
        (success, error_message, installed_dict)
    """
    if not dep_spec:
        return True, "", {}

    runtime_path = get_model_runtime_path(model_id)
    python_bin = os.path.join(runtime_path, "bin", "python")
    pip_bin = os.path.join(runtime_path, "bin", "pip")

    if not os.path.exists(python_bin):
        return False, f"venv not found at {runtime_path}", {}

    installed = {}

    # Upgrade pip first
    try:
        subprocess.run(
            [python_bin, "-m", "pip", "install", "--upgrade", "pip"],
            capture_output=True, text=True, timeout=60
        )
    except Exception:
        pass

    for pkg, version_spec in dep_spec.items():
        try:
            subprocess.run(
                [pip_bin, "install", f"{pkg}{version_spec}"],
                capture_output=True, text=True, timeout=300, check=True
            )
            installed[pkg] = version_spec
        except subprocess.CalledProcessError as e:
            stderr = e.stderr or ""
            stdout = e.stdout or ""
            return False, f"Failed to install {pkg}: {stderr or stdout[:200]}", installed
        except Exception as e:
            return False, f"Install error for {pkg}: {e}", installed

    # Record actual versions
    try:
        result = subprocess.run(
            [pip_bin, "list", "--format=freeze"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if "==" in line:
                    name, ver = line.split("==", 1)
                    installed[name.lower()] = ver
    except Exception:
        pass

    return True, "", installed


def _run_verification(model_id: str) -> tuple[bool, str]:
    """Run model health/verification test in the isolated environment.

    Returns:
        (success, error_message)
    """
    spec = MODEL_SPECS.get(model_id)
    if not spec:
        return False, f"Unknown model: {model_id}"

    # Doench 2014 has no dependencies — verify with main interpreter
    if model_id == "doench_2014":
        try:
            from core.ontarget import _predict_doench2014
            test_seq = spec["verification_case"]["context_sequence"]
            score = _predict_doench2014(test_seq)
            expected = spec["verification_case"].get("expected_score")
            if expected is not None:
                if abs(score - expected) > 0.01:
                    return False, f"Verification failed: expected ~{expected}, got {score}"
            expected_range = spec["verification_case"]["expected_range"]
            if not (expected_range[0] <= score <= expected_range[1]):
                return False, f"Score {score} out of expected range {expected_range}"
            return True, ""
        except Exception as e:
            return False, f"Verification error: {e}"

    # For models with isolated environments
    runtime_path = get_model_runtime_path(model_id)
    python_bin = os.path.join(runtime_path, "bin", "python")

    if not os.path.exists(python_bin):
        return False, f"No runtime at {runtime_path}"

    runner = spec.get("runner_entrypoint", "")
    test_seq = spec["verification_case"]["context_sequence"]
    expected_range = spec["verification_case"]["expected_range"]

    # Write a temporary verification script
    verify_script = f'''
import sys
sys.path.insert(0, "{_BACKEND_DIR}")

model_id = "{model_id}"
test_seq = "{test_seq}"
expected_range = {expected_range}

try:
    if model_id == "rule_set_2":
        import pickle, os
        import numpy as np
        model_path = "{spec["resource_source"]["path"]}"
        if not os.path.exists(model_path):
            print("ERROR:model file not found")
            sys.exit(1)
        # Check sklearn version
        import sklearn
        ver = sklearn.__version__
        major, minor = map(int, ver.split(".")[:2])
        if major > 0 or minor > 16:
            print(f"ERROR:sklearn {ver} incompatible (need <=0.16.1)")
            sys.exit(1)
        with open(model_path, "rb") as f:
            model_data = pickle.load(f, encoding="bytes")
        # Basic load test
        print("OK:model loaded with sklearn", ver)
        sys.exit(0)

    elif model_id == "rule_set_3":
        import rs3
        from rs3.seq import predict_seq, featurize_context, load_seq_model
        import joblib, os
        # Load model and check _n_classes
        model = load_seq_model()
        if getattr(model, "_n_classes", None) is None:
            model._n_classes = 0
        feats = featurize_context([test_seq])
        score = model.predict(feats)[0]
        print(f"OK:score={score}")
        sys.exit(0)

    print("ERROR:unknown model runner")
    sys.exit(1)

except Exception as e:
    print(f"ERROR:{{e}}")
    sys.exit(1)
'''

    script_path = os.path.join(_STATE_DIR, f"verify_{model_id}.py")
    with open(script_path, "w") as f:
        f.write(verify_script)

    try:
        result = subprocess.run(
            [python_bin, script_path],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if result.returncode == 0 and output.startswith("OK"):
            return True, ""
        else:
            err = output if output else result.stderr.strip()
            return False, f"Verification failed: {err}"
    except subprocess.TimeoutExpired:
        return False, "Verification timed out"
    except Exception as e:
        return False, f"Verification execution error: {e}"
    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


def provision_model(model_id: str, force: bool = False) -> dict[str, Any]:
    """Provision an isolated runtime for a model.

    Args:
        model_id: Model to provision
        force: If True, recreate the environment even if it exists

    Returns:
        Dict with provisioning results
    """
    spec = MODEL_SPECS.get(model_id)
    if not spec:
        return {
            "model_id": model_id,
            "action": "failed",
            "error": f"Unknown model: {model_id}",
            "runtime_status": "failed",
        }

    # Doench 2014 needs no provisioning
    if model_id == "doench_2014":
        return {
            "model_id": model_id,
            "action": "no_provisioning_needed",
            "runtime_status": "verified",
            "message": "Doench 2014 is pure Python, no isolated runtime required",
        }

    lock_fd = _acquire_lock(model_id)
    try:
        state = _load_state()
        info = state.get(model_id, RuntimeInfo(model_id=model_id))

        # If already verified and not forcing, skip
        if info.state == RuntimeState.VERIFIED and not force:
            return {
                "model_id": model_id,
                "action": "already_verified",
                "runtime_status": "verified",
                "runtime_path": info.runtime_path,
                "python_version": info.python_version,
            }

        # Force recreate if requested
        if force and info.runtime_path and os.path.exists(info.runtime_path):
            import shutil
            try:
                shutil.rmtree(info.runtime_path)
            except Exception:
                pass
            info = RuntimeInfo(model_id=model_id)

        info.state = RuntimeState.PROVISIONING
        info.runtime_action = "provisioning"
        info.last_provision_at = time.time()
        state[model_id] = info
        _save_state(state)

        # Create isolated venv
        success, result_msg = _create_isolated_venv(model_id, spec.get("expected_python"))
        if not success:
            info.state = RuntimeState.FAILED
            info.last_error = result_msg
            info.runtime_action = "failed"
            state[model_id] = info
            _save_state(state)
            return {
                "model_id": model_id,
                "action": "failed",
                "error": result_msg,
                "runtime_status": "failed",
            }

        # Check Python version
        info.python_version = result_msg
        runtime_path = get_model_runtime_path(model_id)
        info.runtime_path = runtime_path
        info.state = RuntimeState.PROVISIONED
        info.runtime_action = "provisioned"
        _save_state(state)

        # Install dependencies
        success, error, installed = _install_dependencies(model_id, spec.get("dependency_spec", {}))
        if not success:
            info.state = RuntimeState.INCOMPATIBLE
            info.last_error = error
            info.runtime_action = "failed"
            state[model_id] = info
            _save_state(state)
            return {
                "model_id": model_id,
                "action": "dependency_install_failed",
                "error": error,
                "runtime_status": "incompatible",
                "runtime_path": runtime_path,
                "installed_packages": installed,
            }

        info.dependencies_installed = True
        info.installed_packages = installed
        info.state = RuntimeState.VERIFYING
        info.runtime_action = "verifying"
        _save_state(state)

        # Run verification
        success, error = _run_verification(model_id)
        if not success:
            info.state = RuntimeState.FAILED
            info.last_error = error
            info.runtime_action = "failed"
            state[model_id] = info
            _save_state(state)
            return {
                "model_id": model_id,
                "action": "verification_failed",
                "error": error,
                "runtime_status": "failed",
                "runtime_path": runtime_path,
                "python_version": info.python_version,
                "installed_packages": installed,
            }

        # Success
        info.state = RuntimeState.VERIFIED
        info.verification_passed = True
        info.runtime_action = "verified"
        info.last_verify_at = time.time()
        info.last_error = ""
        state[model_id] = info
        _save_state(state)

        return {
            "model_id": model_id,
            "action": "verified",
            "runtime_status": "verified",
            "runtime_path": runtime_path,
            "python_version": info.python_version,
            "installed_packages": installed,
            "runtime_action": "auto_provisioned",
        }

    finally:
        _release_lock(lock_fd)


def verify_model(model_id: str) -> dict[str, Any]:
    """Verify a model's runtime by running its health check.

    Returns:
        Dict with verification results
    """
    state = _load_state()
    info = state.get(model_id, RuntimeInfo(model_id=model_id))

    spec = MODEL_SPECS.get(model_id)
    if not spec:
        return {
            "model_id": model_id,
            "verification_status": "failed",
            "error": f"Unknown model: {model_id}",
        }

    # Doench 2014 always verified (in main env)
    if model_id == "doench_2014":
        success, error = _run_verification(model_id)
        return {
            "model_id": model_id,
            "verification_status": "pass" if success else "fail",
            "error": error,
        }

    runtime_path = get_model_runtime_path(model_id)
    if not os.path.exists(runtime_path):
        return {
            "model_id": model_id,
            "verification_status": "fail",
            "error": f"Runtime not provisioned at {runtime_path}",
        }

    # Run verification
    info.state = RuntimeState.VERIFYING
    info.runtime_action = "verifying"
    _save_state(state)

    success, error = _run_verification(model_id)

    if success:
        info.state = RuntimeState.VERIFIED
        info.verification_passed = True
        info.last_verify_at = time.time()
        info.last_error = ""
        info.runtime_action = "verified"
    else:
        info.state = RuntimeState.FAILED
        info.verification_passed = False
        info.last_error = error
        info.last_verify_at = time.time()
        info.runtime_action = "failed"

    state[model_id] = info
    _save_state(state)

    return {
        "model_id": model_id,
        "verification_status": "pass" if success else "fail",
        "error": error,
        "runtime_path": runtime_path,
        "runtime_action": info.runtime_action,
    }


def ensure_model_ready(model_id: str) -> tuple[str, dict[str, Any]]:
    """Ensure a model is ready for use, provisioning if needed.

    Returns:
        (model_id_or_none, status_dict)
    """
    state = _load_state()
    info = state.get(model_id, RuntimeInfo(model_id=model_id))

    # Doench 2014 is always ready
    if model_id == "doench_2014":
        return model_id, {
            "state": RuntimeState.VERIFIED,
            "ready": True,
            "runtime_action": "already_available",
        }

    # If already verified, use it
    if info.state == RuntimeState.VERIFIED:
        return model_id, {
            "state": RuntimeState.VERIFIED,
            "ready": True,
            "runtime_action": "already_available",
        }

    # If not provisioned or unverified, try to provision
    if info.state in (RuntimeState.NOT_PROVISIONED, RuntimeState.PROVISIONED):
        result = provision_model(model_id)
        if result.get("runtime_status") == "verified":
            return model_id, {
                "state": RuntimeState.VERIFIED,
                "ready": True,
                "runtime_action": result.get("runtime_action", "auto_provisioned"),
                "runtime_path": result.get("runtime_path"),
                "python_version": result.get("python_version"),
            }
        else:
            return None, {
                "state": result.get("runtime_status", RuntimeState.FAILED),
                "ready": False,
                "runtime_action": result.get("action", "failed"),
                "error": result.get("error", "provisioning failed"),
            }

    # If failed/incompatible, return status
    return None, {
        "state": info.state,
        "ready": False,
        "runtime_action": info.runtime_action or "unavailable",
        "error": info.last_error,
    }


def list_model_runtimes() -> list[dict[str, Any]]:
    """List all model runtime states."""
    state = _load_state()
    results = []
    for model_id in ["rule_set_3", "rule_set_2", "doench_2014"]:
        status = get_model_status(model_id)
        results.append(status)
    return results


def clear_model_runtime(model_id: str) -> dict[str, Any]:
    """Clear a model's runtime (deprovision).

    Does NOT touch the main VEYRA environment.
    """
    if model_id == "doench_2014":
        return {
            "model_id": model_id,
            "action": "skipped",
            "message": "Doench 2014 is built-in, no runtime to clear",
        }

    runtime_path = get_model_runtime_path(model_id)

    lock_fd = _acquire_lock(model_id)
    try:
        import shutil
        removed = False
        if os.path.exists(runtime_path):
            try:
                shutil.rmtree(runtime_path)
                removed = True
            except Exception as e:
                return {"model_id": model_id, "action": "failed", "error": str(e)}

        # Clear state
        state = _load_state()
        if model_id in state:
            state[model_id] = RuntimeInfo(model_id=model_id)
            _save_state(state)

        return {
            "model_id": model_id,
            "action": "cleared" if removed else "already_cleared",
            "runtime_path": runtime_path,
        }
    finally:
        _release_lock(lock_fd)
