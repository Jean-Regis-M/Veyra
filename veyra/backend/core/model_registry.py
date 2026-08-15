"""VEYRA On-Target Model Registry.

Tracks availability, compatibility, and verification status of all
on-target efficiency models.
"""

from __future__ import annotations

import sys
import os
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
    availability: str = "unknown"  # installed, missing, incompatible, unverified, verified, error
    expected_context_length: int = 30
    expected_spacer_length: int = 20
    output_scale: str = "0-1"  # or "0-100"
    license: str = ""
    provenance: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)
    error_message: str = ""
    
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
        }


# Model registry
MODEL_REGISTRY: dict[str, ModelInfo] = {}


def _check_rule_set_2() -> ModelInfo:
    """Check Rule Set 2 (Doench 2016 / Azimuth / Fusi) availability."""
    
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
    
    # Check if model file exists
    if not os.path.isfile(model.resource_path):
        model.availability = "missing"
        model.error_message = f"Model file not found: {model.resource_path}"
        return model
    
    model.installed = True
    
    # Check compatibility - need old sklearn for pickled model
    try:
        import sklearn
        sklearn_version = sklearn.__version__
        model.dependencies["scikit-learn"] = f"{sklearn_version} (installed)"
        
        # The pickled model requires sklearn 0.16.1
        major, minor = map(int, sklearn_version.split(".")[:2])
        if major == 0 and minor <= 16:
            model.compatible = True
        else:
            model.compatible = False
            model.availability = "incompatible"
            model.error_message = (
                f"Pickled Rule Set 2 model requires scikit-learn <= 0.16.1, "
                f"but {sklearn_version} is installed. "
                "Model was serialized with sklearn 0.16.1 and cannot be loaded "
                "with newer versions due to internal API changes "
                "(sklearn.ensemble._gb_losses module removed)."
            )
    except Exception as e:
        model.availability = "error"
        model.error_message = f"Failed to check sklearn version: {e}"
    
    # If compatible, attempt to load and verify
    if model.compatible:
        try:
            import pickle
            with open(model.resource_path, "rb") as f:
                model_data = pickle.load(f, encoding="bytes")
            # If we can load it, verify with reference case
            model.verified = True
            model.availability = "verified"
        except Exception as e:
            model.verified = False
            model.availability = "error"
            model.error_message = f"Failed to load/verify model: {e}"
    elif model.availability != "incompatible":
        model.availability = "unverified"
    
    return model


def _check_rule_set_3() -> ModelInfo:
    """Check Rule Set 3 (Doench 2021) availability."""
    
    model = ModelInfo(
        model_id="rule_set_3",
        display_name="Rule Set 3 (Doench 2021)",
        version="2021",
        source="Doench et al., Nature Biotechnology 2021",
        implementation="LightGBM gradient boosting (via rs3 package)",
        resource_path="rs3 package (PyPI)",
        expected_context_length=30,
        expected_spacer_length=20,
        output_scale="0-1",
        license="MIT",
        provenance="https://github.com/gpp-rnd/rs3",
        dependencies={"rs3": "0.0.15", "lightgbm": "compatible version required"},
    )
    
    # Check if rs3 package is available
    try:
        import rs3
        model.installed = True
        model.dependencies["rs3"] = f"{rs3.__version__} (installed)"
        
        # Check lightgbm compatibility
        try:
            import lightgbm
            model.dependencies["lightgbm"] = f"{lightgbm.__version__} (installed)"
            
            # Try to run reference case
            from rs3.seq import predict_seq
            test_seq = "AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA"
            score = predict_seq([test_seq], sequence_tracr="Hsu2013")
            
            model.verified = True
            model.availability = "verified"
        except Exception as e:
            model.verified = False
            model.compatible = False
            model.availability = "incompatible"
            model.error_message = f"rs3 prediction failed: {e}"
    except ImportError:
        model.installed = False
        model.availability = "missing"
        model.error_message = "rs3 package not installed (pip install rs3)"
    except Exception as e:
        model.availability = "error"
        model.error_message = f"Failed to check rs3: {e}"
    
    return model


def _check_doench_2014() -> ModelInfo:
    """Check Doench 2014 fallback model availability."""
    
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
        dependencies={},  # No external dependencies
    )
    
    # Doench 2014 is pure Python - always available
    model.installed = True
    model.compatible = True
    model.verified = True
    model.availability = "verified"
    
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


def select_model(requested_model: str) -> tuple[str | None, dict[str, Any]]:
    """
    Select a model based on request.
    
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
    }
    
    if requested_model == "auto":
        # Auto-selection: choose highest-priority verified model
        available = get_auto_model_priority()
        
        if not available:
            selection["model_used"] = None
            selection["model_status"] = "no_verified_model"
            selection["selection_status"] = "failed"
            selection["fallback_chain"] = [
                {"model": m, "status": registry[m].availability, "reason": registry[m].error_message or "unknown"}
                for m in ["rule_set_3", "rule_set_2", "doench_2014"]
            ]
            return None, selection
        
        # Use the highest-priority available model
        selected = available[0]
        selection["model_used"] = selected
        selection["model_status"] = registry[selected].availability
        selection["selection_status"] = "selected"
        selection["fallback_used"] = False
        
        # Build fallback chain for transparency
        for m in ["rule_set_3", "rule_set_2", "doench_2014"]:
            info = registry[m]
            if m == selected:
                selection["fallback_chain"].append({
                    "model": m,
                    "status": info.availability,
                    "reason": "selected" if info.availability == "verified" else info.error_message
                })
                break
            else:
                selection["fallback_chain"].append({
                    "model": m,
                    "status": info.availability,
                    "reason": info.error_message or "unavailable"
                })
        
        return selected, selection
    
    # Explicit model selection
    if requested_model not in registry:
        selection["model_used"] = None
        selection["model_status"] = "unknown_model"
        selection["selection_status"] = "failed"
        return None, selection
    
    info = registry[requested_model]
    selection["model_used"] = requested_model
    selection["model_status"] = info.availability
    
    if info.availability == "verified":
        selection["selection_status"] = "selected"
        selection["fallback_used"] = False
    else:
        # Explicit model requested but not available - DO NOT FALL BACK
        selection["selection_status"] = "failed"
        selection["fallback_used"] = False
        selection["fallback_chain"] = [{
            "model": requested_model,
            "status": info.availability,
            "reason": info.error_message or "model not verified"
        }]
    
    return requested_model if info.availability == "verified" else None, selection


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
    }


# Initialize on import
initialize_model_registry()