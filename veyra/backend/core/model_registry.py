"""VEYRA On-Target Model Registry.

Tracks availability, compatibility, and verification status of all
on-target efficiency models. Integrates with the runtime manager for
automatic isolated-environment provisioning.
"""

from __future__ import annotations

import sys
import os
import contextlib
import io
import math
from dataclasses import dataclass, field
from typing import Any, Optional

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import ComputeOnTargetEfficiencyRequest


@dataclass
class ModelInfo:
    """Information about an on-target efficiency model."""

    model_id: str
    display_name: str
    version: str
    source: str
    implementation: str
    resource_path: str = ""
    installed: bool = False
    compatible: bool = False
    verified: bool = False
    availability: str = "unknown"
    expected_context_length: int = 30
    expected_spacer_length: int = 20
    output_scale: str = "0-1"
    license: str = ""
    provenance: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)
    error_message: str = ""
    runtime_path: str = ""
    runtime_state: str = "not_provisioned"
    runtime_action: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "version": self.version,
            "source": self.source,
            "implementation": self.implementation,
            "resource_path": self.resource_path,
            "installed": self.installed,
            "compatible": self.compatible,
            "verified": self.verified,
            "availability": self.availability,
            "expected_context_length": self.expected_context_length,
            "expected_spacer_length": self.expected_spacer_length,
            "output_scale": self.output_scale,
            "license": self.license,
            "provenance": self.provenance,
            "dependencies": self.dependencies,
            "error_message": self.error_message,
            "runtime_path": self.runtime_path,
            "runtime_state": self.runtime_state,
            "runtime_action": self.runtime_action,
        }


MODEL_REGISTRY: dict[str, ModelInfo] = {}


def _check_rule_set_2() -> ModelInfo:
    """Check Rule Set 2 (Doench 2016 / Azimuth / Fusi) availability."""

    from core.model_runtime import get_model_status, RuntimeState

    model = ModelInfo(
        model_id="rule_set_2",
        display_name="Rule Set 2 (Doench 2016 / Azimuth / Fusi)",
        version="2016",
        source="Doench et al., Nature Biotechnology 2016 (PMID: 26825659); Azimuth 2.0 (Microsoft Research)",
        implementation="AdaBoost Regressor (scikit-learn) with nucleotide/positional features",
        resource_path="/home/hrirake/Desktop/hck15/veyra/refrences.local/data/tools/crisporWebsite/bin/fusiDoench/saved_models/V3_model_nopos.pickle",
        expected_context_length=30,
        expected_spacer_length=20,
        output_scale="0-1",
        license="MIT (Azimuth 2.0)",
        provenance="https://github.com/gpp-rnd/azimuth",
        dependencies={"scikit-learn": "0.16.1 (required for pickled model)"},
    )

    # Check if model file exists (read-only reference)
    if not os.path.isfile(model.resource_path):
        model.availability = "missing"
        model.error_message = f"Model file not found: {model.resource_path}"
        return model

    model.installed = True

    # Check if an isolated runtime is verified
    rt_status = get_model_status("rule_set_2")
    if rt_status["state"] == RuntimeState.VERIFIED:
        model.compatible = True
        model.verified = True
        model.availability = "verified"
        model.runtime_path = rt_status.get("runtime_path", "")
        model.runtime_state = rt_status["state"]
        model.runtime_action = "already_available"
        return model

    # Check main environment compatibility
    try:
        import sklearn
        sklearn_version = sklearn.__version__
        model.dependencies["scikit-learn"] = f"{sklearn_version} (installed in main env)"

        major, minor = map(int, sklearn_version.split(".")[:2])
        if major == 0 and minor <= 16:
            model.compatible = True
        else:
            model.compatible = False
            model.availability = "incompatible"
            model.error_message = (
                f"Pickled Rule Set 2 model requires scikit-learn <= 0.16.1, "
                f"but {sklearn_version} is installed. "
                "An isolated runtime can be provisioned via 'models setup rule_set_2'."
            )
    except Exception as e:
        model.availability = "error"
        model.error_message = f"Failed to check sklearn version: {e}"

    model.runtime_state = rt_status.get("state", "not_provisioned")
    model.runtime_path = rt_status.get("runtime_path", "")
    model.runtime_action = rt_status.get("runtime_action", "none")

    if not model.compatible and model.availability != "incompatible":
        model.availability = "unverified"

    return model


def _check_rule_set_3() -> ModelInfo:
    """Check Rule Set 3 (Doench 2021) availability."""

    from core.model_runtime import get_model_status, RuntimeState

    model = ModelInfo(
        model_id="rule_set_3",
        display_name="Rule Set 3 (Doench 2021)",
        version="2021",
        source="Doench et al., Nature Biotechnology 2021",
        implementation="LightGBM gradient boosting (via rs3 package)",
        resource_path="rs3 package (PyPI)",
        expected_context_length=30,
        expected_spacer_length=20,
        output_scale="native RS3 activity score (not bounded to 0-1)",
        license="MIT",
        provenance="https://github.com/gpp-rnd/rs3",
        dependencies={"rs3": "0.0.15", "lightgbm": "compatible version required"},
    )

    # Check if an isolated runtime is verified
    rt_status = get_model_status("rule_set_3")
    if rt_status["state"] == RuntimeState.VERIFIED:
        model.compatible = True
        model.verified = True
        model.availability = "verified"
        model.runtime_path = rt_status.get("runtime_path", "")
        model.runtime_state = rt_status["state"]
        model.runtime_action = "already_available"
        return model

    # Check main environment
    try:
        import rs3
        import lightgbm
        model.installed = True
        model.dependencies["rs3"] = f"{rs3.__version__} (installed in main env)"
        model.dependencies["lightgbm"] = f"{lightgbm.__version__} (installed in main env)"

        # Try to run reference case
        try:
            from rs3.seq import featurize_context, load_seq_model
            test_seq = "AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA"
            # Third-party feature code may emit progress bars.  Registry
            # discovery is used by JSON-producing interfaces, so keep that
            # diagnostic output out of stdout. Use a non-blocking approach
            # to avoid tqdm deadlocks when redirecting stderr.
            import os
            old_stderr = os.dup(2)
            try:
                # Redirect stderr to /dev/null to suppress tqdm output
                with open(os.devnull, 'w') as devnull:
                    os.dup2(devnull.fileno(), 2)
                    model_obj = load_seq_model()
                    if getattr(model_obj, "_n_classes", None) is None:
                        model_obj._n_classes = 0
                    score = float(model_obj.predict(
                        featurize_context([test_seq], sequence_tracr="Hsu2013", n_jobs=1)
                    )[0])
                    if not math.isfinite(score):
                        raise ValueError("rs3 returned a non-finite score")
            finally:
                os.dup2(old_stderr, 2)

            model.verified = True
            model.compatible = True
            model.availability = "verified"
        except Exception as e:
            model.verified = False
            model.compatible = False
            model.availability = "incompatible"
            model.error_message = f"rs3 prediction failed: {e}"
    except ImportError:
        model.installed = False
        model.availability = "missing"
        model.error_message = "rs3 package not installed"
    except Exception as e:
        model.availability = "error"
        model.error_message = f"Failed to check rs3: {e}"

    model.runtime_state = rt_status.get("state", "not_provisioned")
    model.runtime_path = rt_status.get("runtime_path", "")
    model.runtime_action = rt_status.get("runtime_action", "none")

    return model


def _check_doench_2014() -> ModelInfo:
    """Check Doench 2014 fallback model availability."""

    from core.model_runtime import get_model_status, RuntimeState

    model = ModelInfo(
        model_id="doench_2014",
        display_name="Doench 2014 (Rule Set 1)",
        version="2014",
        source="Doench et al., Nature Biotechnology 2014 (PMID: 25184501)",
        implementation="Linear regression with position-specific nucleotide/dinucleotide weights + GC adjustment (pure Python)",
        resource_path="Internal reimplementation (crisporEffScores.py / doenchScore.py)",
        expected_context_length=30,
        expected_spacer_length=20,
        output_scale="0-1",
        license="Open (reimplementation of published coefficients)",
        provenance="http://www.broadinstitute.org/rnai/public/analysis-tools/sgrna-design",
        dependencies={},
    )

    # Doench 2014 is pure Python - always available
    model.installed = True
    model.compatible = True
    model.verified = True
    model.availability = "verified"

    rt_status = get_model_status("doench_2014")
    model.runtime_state = rt_status.get("state", RuntimeState.VERIFIED)
    model.runtime_path = rt_status.get("runtime_path", "builtin")

    return model


def initialize_model_registry() -> dict[str, ModelInfo]:
    """Initialize the model registry by checking all models."""
    global MODEL_REGISTRY

    if MODEL_REGISTRY:
        return MODEL_REGISTRY

    MODEL_REGISTRY = {
        "rule_set_2": _check_rule_set_2(),
        "rule_set_3": _check_rule_set_3(),
        "doench_2014": _check_doench_2014(),
    }

    return MODEL_REGISTRY


def get_model_registry() -> dict[str, ModelInfo]:
    """Get the model registry, initializing if needed."""
    if not MODEL_REGISTRY:
        initialize_model_registry()
    return MODEL_REGISTRY


def get_model_info(model_id: str) -> Optional[ModelInfo]:
    """Get information about a specific model."""
    registry = get_model_registry()
    return registry.get(model_id)


def get_auto_model_priority() -> list[str]:
    """Get the auto-selection priority order (only verified models)."""
    registry = get_model_registry()
    priority = ["rule_set_3", "rule_set_2", "doench_2014"]
    return [m for m in priority if registry.get(m, ModelInfo("", "", "", "", "")).availability == "verified"]


def select_model(requested_model: str, auto_provision: bool = False) -> tuple[str | None, dict[str, Any]]:
    """
    Select a model based on request.

    Args:
        requested_model: "auto", "rule_set_2", "rule_set_3", "doench_2014", "both"
        auto_provision: If True and model="auto", attempt provisioning of unavailable models

    Returns:
        (model_used, selection_metadata)
    """
    registry = get_model_registry()
    selection = {
        "requested_model": requested_model,
        "model_used": None,
        "model_status": None,
        "selection_status": "unknown",
        "fallback_used": False,
        "fallback_from": None,
        "fallback_to": None,
        "fallback_reason": None,
        "fallback_chain": [],
        "runtime_actions": {},
    }

    if requested_model == "auto":
        # Auto-selection: try each model in priority order
        priority = ["rule_set_3", "rule_set_2", "doench_2014"]

        # Build full fallback chain
        chain = []
        selected = None
        for i, m in enumerate(priority):
            info = registry.get(m)
            if info and info.availability == "verified":
                chain.append({
                    "model": m,
                    "status": info.availability,
                    "reason": "selected",
                })
                selected = m
                break
            elif info:
                chain.append({
                    "model": m,
                    "status": info.availability,
                    "reason": info.error_message or "unavailable",
                })

        if selected is None:
            selection["model_status"] = "no_verified_model"
            selection["selection_status"] = "failed"
            selection["fallback_chain"] = chain
            return None, selection

        info = registry[selected]
        selection["model_used"] = selected
        selection["model_status"] = info.availability
        selection["selection_status"] = "selected"
        selection["runtime_action"] = info.runtime_action

        # Determine if this was a fallback
        if selected != "rule_set_3":
            selection["fallback_used"] = True
            selection["fallback_from"] = "rule_set_3"
            selection["fallback_to"] = selected
            selection["fallback_reason"] = "rule_set_3_unavailable"

        selection["fallback_chain"] = chain
        return selected, selection

    # Explicit model selection
    if requested_model not in registry:
        selection["model_status"] = "unknown_model"
        selection["selection_status"] = "failed"
        return None, selection

    info = registry[requested_model]

    # If verified, use it
    if info.availability == "verified":
        selection["model_used"] = requested_model
        selection["model_status"] = info.availability
        selection["selection_status"] = "selected"
        selection["fallback_used"] = False
        selection["runtime_action"] = info.runtime_action
        return requested_model, selection

    # Explicit model requested but not verified - attempt provisioning if requested
    if auto_provision:
        from core.model_runtime import ensure_model_ready
        model_used, rt_info = ensure_model_ready(requested_model)
        if model_used:
            # Refresh registry
            initialize_model_registry()
            registry = get_model_registry()
            info = registry[requested_model]
            selection["model_used"] = requested_model
            selection["model_status"] = info.availability
            selection["selection_status"] = "selected"
            selection["fallback_used"] = False
            selection["runtime_action"] = rt_info.get("runtime_action", "auto_provisioned")
            selection["runtime_actions"][requested_model] = rt_info
            return requested_model, selection
        else:
            selection["runtime_actions"][requested_model] = rt_info

    # Explicit model not available - DO NOT FALL BACK
    selection["model_status"] = info.availability
    selection["selection_status"] = "failed"
    selection["fallback_used"] = False
    selection["fallback_chain"] = [{
        "model": requested_model,
        "status": info.availability,
        "reason": info.error_message or "model not verified",
    }]
    return None, selection


def get_model_fallback_info(model_id: str) -> dict[str, Any]:
    """Get detailed fallback information for a model."""
    registry = get_model_registry()
    info = registry.get(model_id)
    if not info:
        return {"error": f"Unknown model: {model_id}"}

    return {
        "model_id": model_id,
        "display_name": info.display_name,
        "availability": info.availability,
        "verified": info.verified,
        "compatible": info.compatible,
        "installed": info.installed,
        "error_message": info.error_message,
        "dependencies": info.dependencies,
        "runtime_path": info.runtime_path,
        "runtime_state": info.runtime_state,
        "runtime_action": info.runtime_action,
    }


# Initialize on import
initialize_model_registry()
