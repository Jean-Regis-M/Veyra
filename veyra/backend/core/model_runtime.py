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
import platform
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
        "version": "2.0",
        "source": "Doench et al., Nature Biotechnology 2016 (PMID: 26825659); Azimuth 2.0 (Microsoft Research)",
        "implementation": "AdaBoost Regressor (scikit-learn) with nucleotide/positional features",
        "expected_python": "2.7",  # Azimuth 2.0 officially supports Python 2.7
        "dependency_spec": {
            "scikit-learn": "==0.17.1",  # Authoritative requirement from Azimuth setup.py
            "numpy": ">=1.9.0",           # Compatible with scikit-learn 0.17.1
            "scipy": ">=0.15.1",         # Required by Azimuth
            "pandas": ">=0.17.1",        # Required by Azimuth
            "biopython": ">=1.65",       # Required by Azimuth
            "matplotlib": ">=1.4.0",     # Required by Azimuth
        },
        "resource_source": {
            "type": "package",
            "path": "refrences.local/data/tools/crisporWebsite/bin/Azimuth-2.0",
            "model_file": "azimuth/saved_models/V3_model_nopos.pickle",
        },
        "runner_entrypoint": "azimuth_predict",
        "verification_case": {
            "context_sequence": "AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA",
            "expected_range": [0.0, 1.0],  # Azimuth outputs 0-1 probability scores
        },
        "license": "BSD",
        "provenance": "https://github.com/MicrosoftResearch/Azimuth",
        "package_manager": "conda",
        "environment_type": "legacy_python27",
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


if sys.platform == "win32":
    import msvcrt

    def _lock_fd(fd: int, blocking: bool) -> None:
        # msvcrt has no blocking-lock primitive; poll LK_NBLCK instead.
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if not blocking:
                    raise
                time.sleep(0.1)

    def _unlock_fd(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock_fd(fd: int, blocking: bool) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_fd(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


def _acquire_lock(model_id: str) -> Any:
    """Acquire a file lock for model provisioning to prevent concurrent setup."""
    os.makedirs(_LOCK_DIR, exist_ok=True)
    lock_file = os.path.join(_LOCK_DIR, f"{model_id}.lock")
    fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        _lock_fd(fd, blocking=False)
    except (IOError, OSError):
        _lock_fd(fd, blocking=True)
    return fd


def _release_lock(fd: int) -> None:
    """Release a file lock."""
    try:
        _unlock_fd(fd)
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


def detect_python_runtimes() -> dict[str, list[dict[str, Any]]]:
    """Detect available Python runtimes on the system.
    
    Returns:
        Dict mapping runtime types to list of available runtimes.
    """
    runtimes = {
        "python27": [],
        "python3": [],
        "conda": [],
        "micromamba": [],
        "mamba": [],
    }
    
    # Check for Python 2.7 executables
    python27_names = ["python2.7", "python2", "python27"]
    for py_name in python27_names:
        try:
            result = subprocess.run(
                [py_name, "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                version_output = result.stderr.strip() or result.stdout.strip()
                if "2.7" in version_output:
                    runtimes["python27"].append({
                        "executable": py_name,
                        "version": version_output,
                        "source": "PATH",
                        "type": "system"
                    })
        except Exception:
            continue
    
    # Check for Python 3 executables
    python3_names = ["python3", "python3.12", "python3.11", "python3.10", "python3.9", "python3.8", "python"]
    for py_name in python3_names:
        try:
            result = subprocess.run(
                [py_name, "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                version_output = result.stderr.strip() or result.stdout.strip()
                if "3." in version_output:
                    runtimes["python3"].append({
                        "executable": py_name,
                        "version": version_output,
                        "source": "PATH",
                        "type": "system"
                    })
        except Exception:
            continue
    
    # Check for Conda environment managers
    conda_names = ["conda", "micromamba", "mamba"]
    for conda_name in conda_names:
        try:
            result = subprocess.run(
                [conda_name, "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                version_output = result.stdout.strip()
                runtime_type = conda_name
                if conda_name == "conda":
                    runtime_type = "conda"
                elif conda_name == "micromamba":
                    runtime_type = "micromamba"
                else:
                    runtime_type = "mamba"
                    
                runtimes[runtime_type].append({
                    "executable": conda_name,
                    "version": version_output,
                    "source": "PATH",
                    "type": "environment_manager"
                })
        except Exception:
            continue
    
    return runtimes


def detect_conda_environments() -> list[dict[str, Any]]:
    """Detect existing Conda environments that might have Python 2.7."""
    environments = []
    
    # Try to find conda executable
    conda_executables = ["conda", "micromamba", "mamba"]
    conda_cmd = None
    for cmd in conda_executables:
        try:
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                conda_cmd = cmd
                break
        except Exception:
            continue
    
    if not conda_cmd:
        return environments
    
    # List conda environments
    try:
        result = subprocess.run(
            [conda_cmd, "env", "list", "--json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            envs = json.loads(result.stdout.strip())
            for env_name, env_path in envs.get("envs", {}).items():
                # Check if this environment has Python 2.7
                python_executable = os.path.join(env_path, "bin", "python")
                if os.path.exists(python_executable):
                    try:
                        result = subprocess.run(
                            [python_executable, "--version"],
                            capture_output=True, text=True, timeout=5
                        )
                        if result.returncode == 0:
                            version_output = result.stderr.strip() or result.stdout.strip()
                            if "2.7" in version_output:
                                environments.append({
                                    "name": env_name,
                                    "path": env_path,
                                    "python_executable": python_executable,
                                    "python_version": version_output,
                                    "package_manager": conda_cmd,
                                    "type": "conda_environment"
                                })
                    except Exception:
                        continue
    except Exception:
        pass
    
    return environments


def find_compatible_python27_runtime() -> Optional[dict[str, Any]]:
    """Find a compatible Python 2.7 runtime for Rule Set 2.
    
    Search order:
    1. Existing project-local isolated environment
    2. Existing Conda environment with Python 2.7
    3. System Python 2.7
    
    Returns:
        Runtime info dict or None if not found.
    """
    # 1. Check existing project-local isolated environment
    runtime_path = get_model_runtime_path("rule_set_2")
    if os.path.exists(runtime_path):
        python_executable = os.path.join(runtime_path, "bin", "python")
        if os.path.exists(python_executable):
            try:
                result = subprocess.run(
                    [python_executable, "--version"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    version_output = result.stderr.strip() or result.stdout.strip()
                    if "2.7" in version_output:
                        return {
                            "type": "isolated",
                            "path": runtime_path,
                            "python_executable": python_executable,
                            "python_version": version_output,
                            "package_manager": "conda",
                            "source": "project_local"
                        }
            except Exception:
                pass
    
    # 2. Check existing Conda environments
    conda_envs = detect_conda_environments()
    for env in conda_envs:
        if "2.7" in env.get("python_version", ""):
            return {
                "type": "conda_environment",
                "path": env["path"],
                "python_executable": env["python_executable"],
                "python_version": env["python_version"],
                "package_manager": env["package_manager"],
                "source": "existing_conda"
            }
    
    # 3. Check system Python 2.7
    python27_runtimes = detect_python_runtimes().get("python27", [])
    for runtime in python27_runtimes:
        if runtime.get("source") == "PATH":
            return {
                "type": "system",
                "path": None,
                "python_executable": runtime["executable"],
                "python_version": runtime["version"],
                "package_manager": "system",
                "source": "system_path"
            }
    
    return None


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
        "platform": platform.system(),
        "runtime_type": spec.get("environment_type", "isolated"),
        "package_manager": spec.get("package_manager", "unknown"),
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


def _create_conda_environment(model_id: str, spec: dict[str, Any]) -> tuple[bool, str, str]:
    """Create a Conda environment for Rule Set 2 with Python 2.7.
    
    Args:
        model_id: Model identifier
        spec: Model specification
    
    Returns:
        (success, error_message, python_executable)
    """
    runtime_path = get_model_runtime_path(model_id)
    
    # Check if environment already exists
    python_bin = os.path.join(runtime_path, "bin", "python")
    if os.path.exists(python_bin):
        return True, "", python_bin
    
    # Find conda executable
    conda_cmd = None
    conda_executables = ["conda", "micromamba", "mamba"]
    for cmd in conda_executables:
        try:
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                conda_cmd = cmd
                break
        except Exception:
            continue
    
    if not conda_cmd:
        return False, "No conda environment manager found (tried: conda, micromamba, mamba)", ""
    
    # Get environment name
    env_name = spec.get("environment_name", model_id)
    python_version = spec.get("expected_python", "2.7")
    
    try:
        # Create conda environment with Python 2.7
        cmd = [
            conda_cmd, "create", "--yes", "--name", env_name,
            f"python={python_version}",
            "-c", "conda-forge"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=120
        )
        
        if result.returncode != 0:
            return False, f"Conda environment creation failed: {result.stderr.strip()}", ""
        
        # Find the actual environment path
        env_path = None
        try:
            result = subprocess.run(
                [conda_cmd, "env", "list", "--json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                envs = json.loads(result.stdout.strip())
                env_path = envs.get("envs", {}).get(env_name)
        except Exception:
            pass
        
        if not env_path:
            # Try default conda envs location
            default_env_path = os.path.join(os.path.expanduser("~"), "miniconda3", "envs", env_name)
            if os.path.exists(default_env_path):
                env_path = default_env_path
            else:
                default_env_path = os.path.join(os.path.expanduser("~"), ".conda", "envs", env_name)
                if os.path.exists(default_env_path):
                    env_path = default_env_path
        
        if not env_path:
            return False, "Could not determine conda environment path", ""
        
        # Install dependencies
        deps = spec.get("dependency_spec", {})
        for pkg, version in deps.items():
            try:
                subprocess.run(
                    [conda_cmd, "install", "--yes", "--name", env_name, f"{pkg}={version}"],
                    capture_output=True, text=True, timeout=120, check=True
                )
            except subprocess.CalledProcessError as e:
                return False, f"Failed to install {pkg}={version}: {e.stderr.strip()}", ""
        
        # Verify Python executable
        python_bin = os.path.join(env_path, "bin", "python")
        if not os.path.exists(python_bin):
            # Try Windows path
            python_bin = os.path.join(env_path, "python.exe")
        
        if not os.path.exists(python_bin):
            return False, f"Python executable not found in {env_path}", ""
        
        # Verify Python version
        try:
            result = subprocess.run(
                [python_bin, "--version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return False, f"Python executable not working: {result.stderr.strip()}", ""
        except Exception as e:
            return False, f"Python version check failed: {e}", ""
        
        # Update runtime path to point to conda environment
        # Note: We need to handle the symlink or move the environment
        # For now, we'll create a symlink from the expected location to the conda env
        os.makedirs(_MODEL_ENVS_DIR, exist_ok=True)
        target_path = os.path.join(_MODEL_ENVS_DIR, model_id)
        
        # Remove existing directory if it exists
        if os.path.exists(target_path):
            try:
                import shutil
                shutil.rmtree(target_path)
            except Exception:
                pass
        
        # Create symlink to conda environment
        try:
            os.symlink(env_path, target_path)
        except Exception:
            # If symlink fails, copy the path info but don't actually move files
            pass
        
        return True, "", python_bin
        
    except Exception as e:
        return False, f"Conda environment creation error: {e}", ""


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
    
    # Special handling for Rule Set 2 (uses subprocess JSON protocol)
    if model_id == "rule_set_2":
        return _verify_rule_set_2(runtime_path, spec)
    
    # Standard verification for other models
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
    if model_id == "rule_set_3":
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
    print(f"ERROR:{e}")
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


def _verify_rule_set_2(runtime_path: str, spec: dict[str, Any]) -> tuple[bool, str]:
    """Verify Rule Set 2 using subprocess JSON protocol."""
    from core.rule_set_2_adapter import run_rule_set_2_prediction, get_rule_set_2_runtime_info
    
    # Get runtime info
    runtime_info = get_rule_set_2_runtime_info()
    if not runtime_info.python_executable or not os.path.exists(runtime_info.python_executable):
        return False, f"Rule Set 2 runtime not available: {runtime_info.provisioning_status}"
    
    # Test with verification case
    test_seq = spec["verification_case"]["context_sequence"]
    expected_range = spec["verification_case"]["expected_range"]
    
    try:
        score, source = run_rule_set_2_prediction(test_seq, runtime_info)
        if score is None:
            return False, f"Rule Set 2 prediction failed: {source}"
        
        # Check if score is within expected range
        if not (expected_range[0] <= score <= expected_range[1]):
            return False, f"Rule Set 2 score {score} out of expected range {expected_range}"
        
        return True, f"Rule Set 2 verified with score {score}"
        
    except Exception as e:
        return False, f"Rule Set 2 verification error: {e}"


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

        # Special handling for Rule Set 2 (requires Python 2.7 and Conda)
        if model_id == "rule_set_2":
            success, error_msg, python_bin = _create_conda_environment(model_id, spec)
            if not success:
                info.state = RuntimeState.FAILED
                info.last_error = error_msg
                info.runtime_action = "failed"
                state[model_id] = info
                _save_state(state)
                return {
                    "model_id": model_id,
                    "action": "failed",
                    "error": error_msg,
                    "runtime_status": "failed",
                }
            
            # Check Python version
            try:
                result = subprocess.run(
                    [python_bin, "--version"],
                    capture_output=True, text=True, timeout=10
                )
                python_version = result.stderr.strip() or result.stdout.strip()
            except Exception:
                python_version = "unknown"
            
            info.python_version = python_version
            runtime_path = get_model_runtime_path(model_id)
            info.runtime_path = runtime_path
            info.state = RuntimeState.PROVISIONED
            info.runtime_action = "provisioned"
            _save_state(state)
        else:
            # Standard venv creation for other models
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
