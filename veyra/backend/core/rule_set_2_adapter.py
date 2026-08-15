"""Rule Set 2 / Azimuth Legacy Runtime Adapter.

Provides isolated Python 2.7 runtime execution for Azimuth 2.0 model.
Uses subprocess JSON protocol to avoid direct import of legacy Python 2 code.

Architecture:
    VEYRA Python 3 → Rule Set 2 adapter → isolated Python 2.7 runner → JSON response

Security:
    - No direct import of Python 2.7 code
    - No modification to main VEYRA environment
    - Only trusted dependencies from MODEL_SPECS
    - Argument arrays for subprocess (no shell interpolation)
"""

from __future__ import annotations

import json
import os
import sys
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any, Optional

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VEYRA_DIR = os.path.dirname(_BACKEND_DIR)


@dataclass
class RuleSet2RuntimeInfo:
    """Runtime information for Rule Set 2."""
    runtime_path: str
    python_executable: str
    package_manager: str
    python_version: str
    dependencies: dict[str, str] = field(default_factory=dict)
    platform: str = "unknown"
    runtime_type: str = "unknown"
    provisioning_status: str = "not_provisioned"
    verification_status: str = "pending"


def get_rule_set_2_runtime_info() -> RuleSet2RuntimeInfo:
    """Get current Rule Set 2 runtime information."""
    from core.model_runtime import get_model_status, RuntimeState
    
    status = get_model_status("rule_set_2")
    runtime_path = status.get("runtime_path", "")
    python_version = status.get("python_version", "unknown")
    
    # Try to find Python executable
    python_executable = ""
    if runtime_path and os.path.exists(runtime_path):
        # Try different Python executable names
        for py_name in ["python", "python2.7", "python2", "python27"]:
            test_path = os.path.join(runtime_path, "bin", py_name)
            if os.path.exists(test_path):
                python_executable = test_path
                break
    
    # Determine package manager
    package_manager = "none"
    if status.get("dependency_status") == "installed":
        package_manager = "conda"  # Default for legacy environments
    
    # Determine platform
    platform = sys.platform
    
    # Determine runtime type
    runtime_type = "isolated"
    if not runtime_path:
        runtime_type = "not_provisioned"
    
    # Determine provisioning status
    state = status.get("state", RuntimeState.NOT_PROVISIONED)
    provisioning_status = state
    
    # Determine verification status
    verification_status = "pass" if status.get("verification_status") == "pass" else "pending"
    
    return RuleSet2RuntimeInfo(
        runtime_path=runtime_path,
        python_executable=python_executable,
        package_manager=package_manager,
        python_version=python_version,
        dependencies=status.get("installed_packages", {}),
        platform=platform,
        runtime_type=runtime_type,
        provisioning_status=provisioning_status,
        verification_status=verification_status,
    )


def create_rule_set_2_runner_script() -> str:
    """Create the Rule Set 2 runner script for isolated execution.
    
    This script will be executed in the isolated Python 2.7 environment
    and communicates via JSON stdin/stdout.
    """
    return '''#!/usr/bin/env python
"""Rule Set 2 / Azimuth Runner Script.

Executes in isolated Python 2.7 environment.
Communicates via JSON protocol on stdin/stdout.
"""
import sys
import json
import os
import traceback

def main():
    try:
        # Read JSON request from stdin
        request = json.load(sys.stdin)
        
        # Validate required fields
        if "context_sequence" not in request:
            error_response("Missing context_sequence")
            return
        
        context_sequence = request["context_sequence"]
        
        # Validate sequence
        if not context_sequence or len(context_sequence) != 30:
            error_response("Context sequence must be 30 characters")
            return
        
        # Import Azimuth and dependencies
        try:
            import numpy as np
            import azimuth.model_comparison
        except ImportError as e:
            error_response("Failed to import Azimuth dependencies: " + str(e))
            return
        
        # Prepare input for Azimuth
        # Azimuth expects: GUIDE (20nt), CUT_POSITION, PERCENT_PEPTIDE
        # For standard SpCas9 with NGG PAM, we extract the 20nt guide
        guide_seq = context_sequence[4:24]  # Extract 20nt guide from 30-mer
        
        # Azimuth model_comparison.predict expects numpy arrays
        # We'll use dummy values for CUT_POSITION and PERCENT_PEPTIDE as they're not critical for basic prediction
        try:
            # Convert to numpy arrays as expected by Azimuth
            guides = np.array([guide_seq])
            cut_positions = np.array([-1])  # -1 indicates unknown/irrelevant
            percent_peptides = np.array([0.5])  # 0.5 as default
            
            # Get prediction from Azimuth
            predictions = azimuth.model_comparison.predict(
                guides, percent_peptides, cut_positions, pam_audit=False
            )
            
            if predictions is None or len(predictions) == 0:
                error_response("No prediction returned from Azimuth")
                return
            
            score = float(predictions[0])
            
            # Validate score
            if not (0.0 <= score <= 1.0):
                error_response("Azimuth score out of expected range [0,1]: " + str(score))
                return
            
            # Build success response
            response = {
                "status": "success",
                "model_id": "rule_set_2",
                "model_version": "2.0",
                "score": score,
                "runtime_python": sys.version,
                "provenance": "Azimuth 2.0 (Doench et al. 2016)",
                "input_sequence": context_sequence,
                "guide_sequence": guide_seq
            }
            
            print(json.dumps(response))
            sys.stdout.flush()
            
        except Exception as e:
            error_response("Azimuth prediction failed: " + str(e))
            
    except json.JSONDecodeError as e:
        error_response("Invalid JSON input: " + str(e))
    except Exception as e:
        error_response("Unexpected error: " + str(e))


def error_response(message):
    """Send error response."""
    response = {
        "status": "error",
        "error": message,
        "model_id": "rule_set_2",
        "runtime_python": sys.version
    }
    print(json.dumps(response))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
'''


def run_rule_set_2_prediction(context_sequence: str, runtime_info: RuleSet2RuntimeInfo) -> tuple[Optional[float], str]:
    """Run Rule Set 2 prediction in isolated runtime.
    
    Args:
        context_sequence: 30-mer context sequence
        runtime_info: Runtime information for Rule Set 2
    
    Returns:
        (score, error_message) - score if successful, None if failed
    """
    if not runtime_info.python_executable or not os.path.exists(runtime_info.python_executable):
        return None, "Rule Set 2 runtime not available: no Python executable found"
    
    if not os.path.exists(runtime_info.runtime_path):
        return None, "Rule Set 2 runtime path not found: " + runtime_info.runtime_path
    
    # Create runner script
    runner_script = create_rule_set_2_runner_script()
    
    # Write runner script to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(runner_script)
        script_path = f.name
    
    try:
        # Prepare JSON request
        request = {
            "context_sequence": context_sequence
        }
        
        # Run subprocess with argument array (no shell interpolation)
        cmd = [
            runtime_info.python_executable,
            script_path
        ]
        
        # Set up environment to include the Azimuth directory in Python path
        env = os.environ.copy()
        azimuth_dir = os.path.join(
            _VEYRA_DIR, 
            "refrences.local", "data", "tools", "crisporWebsite", "bin", "Azimuth-2.0"
        )
        
        # Add Azimuth directory to PYTHONPATH
        existing_path = env.get("PYTHONPATH", "")
        if existing_path:
            env["PYTHONPATH"] = azimuth_dir + ":" + existing_path
        else:
            env["PYTHONPATH"] = azimuth_dir
        
        # Execute subprocess
        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=runtime_info.runtime_path,
                env=env,
                bufsize=-1  # Fully buffered
            )
            
            # Send JSON request to stdin
            stdin_data = json.dumps(request).encode('utf-8')
            stdout_data, stderr_data = process.communicate(input=stdin_data, timeout=30)
            
            # Check return code
            if process.returncode != 0:
                error_msg = stderr_data.decode('utf-8', errors='replace').strip()
                return None, f"Rule Set 2 subprocess failed (exit {process.returncode}): {error_msg}"
            
            # Parse JSON response
            try:
                response = json.loads(stdout_data.decode('utf-8', errors='replace').strip())
                
                if response.get("status") == "success":
                    score = response.get("score")
                    if score is not None:
                        return float(score), "Rule Set 2 (Azimuth 2.0)"
                    else:
                        return None, "Rule Set 2 returned no score"
                else:
                    error_msg = response.get("error", "Unknown error")
                    return None, f"Rule Set 2 error: {error_msg}"
                    
            except json.JSONDecodeError as e:
                return None, f"Rule Set 2 invalid JSON response: {e}"
                
        except subprocess.TimeoutExpired:
            process.kill()
            return None, "Rule Set 2 subprocess timed out"
        except Exception as e:
            return None, f"Rule Set 2 subprocess execution error: {e}"
            
    finally:
        # Clean up temporary script
        try:
            os.unlink(script_path)
        except Exception:
            pass


def detect_python27_runtimes() -> list[dict[str, Any]]:
    """Detect available Python 2.7 runtimes on the system."""
    runtimes = []
    
    # Check common Python 2.7 executable names
    python_executables = [
        "python2.7", "python2", "python27", 
        "python"  # Might be Python 2.7 on some systems
    ]
    
    # Check in PATH
    for py_name in python_executables:
        try:
            result = subprocess.run(
                [py_name, "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                version_output = result.stderr.strip() or result.stdout.strip()
                if "2.7" in version_output:
                    runtimes.append({
                        "type": "system",
                        "executable": py_name,
                        "version": version_output,
                        "source": "PATH"
                    })
        except Exception:
            continue
    
    # Check common Conda installations
    conda_executables = ["conda", "micromamba", "mamba"]
    for conda_name in conda_executables:
        try:
            result = subprocess.run(
                [conda_name, "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                runtimes.append({
                    "type": "conda",
                    "executable": conda_name,
                    "version": result.stdout.strip(),
                    "source": "PATH"
                })
        except Exception:
            continue
    
    return runtimes


def detect_existing_rule_set_2_runtime() -> Optional[RuleSet2RuntimeInfo]:
    """Detect existing Rule Set 2 runtime."""
    from core.model_runtime import get_model_status, RuntimeState
    
    status = get_model_status("rule_set_2")
    if status.get("state") == RuntimeState.VERIFIED:
        return get_rule_set_2_runtime_info()
    
    return None


def create_rule_set_2_environment_spec() -> dict[str, Any]:
    """Get the trusted specification for Rule Set 2 environment."""
    return {
        "model_id": "rule_set_2",
        "python_version": "2.7",
        "package_manager": "conda",
        "dependencies": {
            "scikit-learn": "0.17.1",
            "numpy": "1.9.0",
            "scipy": "0.15.1", 
            "pandas": "0.17.1",
            "biopython": "1.65",
            "matplotlib": "1.4.0",
        },
        "environment_name": "rule_set_2",
        "installation_method": "conda_create",
        "azimuth_source": os.path.join(
            _VEYRA_DIR, 
            "refrences.local", "data", "tools", "crisporWebsite", "bin", "Azimuth-2.0"
        )
    }