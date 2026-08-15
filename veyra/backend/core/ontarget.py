"""Core on-target efficiency prediction service.

Implements model selection with auto-fallback and transparent reporting.

Models:
- rule_set_3: Doench 2021 (LightGBM via rs3) - highest priority for auto
- rule_set_2: Doench 2016 / Azimuth / Fusi (AdaBoost via pickled model) - medium priority
- doench_2014: Doench 2014 linear regression (pure Python) - fallback, always available

Auto-selection priority: rule_set_3 > rule_set_2 > doench_2014
(only among verified models)

Explicit model requests NEVER fall back.
"""

from __future__ import annotations

import sys
import os
import math
import contextlib
import io

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import (
    ComputeOnTargetEfficiencyRequest,
    VeyraResult,
)

from core.model_registry import (
    get_model_registry,
    get_model_info,
    select_model,
    get_auto_model_priority,
)


# Path to the fusiDoench reference implementation (READ-ONLY reference)
_FUSI_DOENCH_DIR = os.path.join(
    os.path.dirname(_BACKEND_DIR),
    "refrences.local", "data", "tools", "crisporWebsite",
    "bin", "fusiDoench", "analysis"
)

# Path to the Azimuth 2.0 library
_AZIMUTH_DIR = os.path.join(
    os.path.dirname(_BACKEND_DIR),
    "refrences.local", "data", "tools", "crisporWebsite",
    "bin", "Azimuth-2.0"
)

_MODEL_FILE_NOPOS = os.path.join(
    os.path.dirname(_BACKEND_DIR),
    "refrences.local", "data", "tools", "crisporWebsite",
    "bin", "fusiDoench", "saved_models", "V3_model_nopos.pickle"
)

_MODEL_FILE_FULL = os.path.join(
    os.path.dirname(_BACKEND_DIR),
    "refrences.local", "data", "tools", "crisporWebsite",
    "bin", "fusiDoench", "saved_models", "V3_model_full.pickle"
)


def _predict_doench2014(seq: str) -> float:
    """Doench 2014 linear regression model (reimplemented from crisporEffScores).
    
    Input: 30-mer (4nt up + 20nt guide + 3nt PAM + 3nt down)
    Output: 0-1 probability
    """
    intercept = 0.59763615
    gc_high = -0.1665878
    gc_low = -0.2026259
    
    score = intercept
    
    guide_seq = seq[4:24]
    gc_count = guide_seq.count("G") + guide_seq.count("C")
    
    if gc_count <= 10:
        gc_weight = gc_low
    else:
        gc_weight = gc_high
    
    score += abs(10 - gc_count) * gc_weight
    
    doench_params = [
        (1,'G',-0.2753771),(2,'A',-0.3238875),(2,'C',0.17212887),(3,'C',-0.1006662),
        (4,'C',-0.2018029),(4,'G',0.24595663),(5,'A',0.03644004),(5,'C',0.09837684),
        (6,'C',-0.7411813),(6,'G',-0.3932644),(11,'A',-0.466099),(14,'A',0.08537695),
        (14,'C',-0.013814),(15,'A',0.27262051),(15,'C',-0.1190226),(15,'T',-0.2859442),
        (16,'A',0.09745459),(16,'G',-0.1755462),(17,'C',-0.3457955),(17,'G',-0.6780964),
        (18,'A',0.22508903),(18,'C',-0.5077941),(19,'G',-0.4173736),(19,'T',-0.054307),
        (20,'G',0.37989937),(20,'T',-0.0907126),(21,'C',0.05782332),(21,'T',-0.5305673),
        (22,'T',-0.8770074),(23,'C',-0.8762358),(23,'G',0.27891626),(23,'T',-0.4031022),
        (24,'A',-0.0773007),(24,'C',0.28793562),(24,'T',-0.2216372),(27,'G',-0.6890167),
        (27,'T',0.11787758),(28,'C',-0.1604453),(29,'G',0.38634258),(1,'GT',-0.6257787),
        (4,'GC',0.30004332),(5,'AA',-0.8348362),(5,'TA',0.76062777),(6,'GG',-0.4908167),
        (11,'GG',-1.5169074),(11,'TA',0.7092612),(11,'TC',0.49629861),(11,'TT',-0.5868739),
        (12,'GG',-0.3345637),(13,'GA',0.76384993),(13,'GC',-0.5370252),(16,'TG',-0.7981461),
        (18,'GG',-0.6668087),(18,'TC',0.35318325),(19,'CC',0.74807209),(19,'TG',-0.3672668),
        (20,'AC',0.56820913),(20,'CG',0.32907207),(20,'GA',-0.8364568),(20,'GG',-0.7822076),
        (21,'TC',-1.029693),(22,'CG',0.85619782),(22,'CT',-0.4632077),(23,'AA',-0.5794924),
        (23,'AG',0.64907554),(24,'AG',-0.0773007),(24,'CG',0.28793562),(24,'TG',-0.2216372),
        (26,'GT',0.11787758),(28,'GG',-0.69774),
    ]
    
    for pos, model_seq, weight in doench_params:
        sub_seq = seq[pos:pos + len(model_seq)]
        if sub_seq == model_seq:
            score += weight
    
    return 1.0 / (1.0 + math.exp(-score))


def _predict_rs2_azimuth(seq: str) -> float | None:
    """Predict on-target efficiency using Rule Set 2 (Azimuth/Doench 2016).
    
    Uses the azimuth library if available.
    
    Args:
        seq: 30-mer sequence (4nt up + 20nt spacer + 3nt PAM + 3nt down)
    
    Returns:
        Score 0-1 or None if model unavailable
    """
    if not seq or len(seq) != 30:
        return None
    
    seq = seq.upper()
    
    # Check for invalid characters
    valid = set("ACGT")
    if not all(c in valid for c in seq):
        return None
    
    # Try azimuth first (full pipeline)
    try:
        import numpy as np
        import azimuth.model_comparison
        score = azimuth.model_comparison.predict(
            np.array([seq]), None, None, pam_audit=False
        )[0]
        return float(score)
    except ImportError:
        pass
    except Exception:
        pass
    
    return None


def _predict_rs2_model(seq: str) -> float | None:
    """Predict using the pickled model directly.
    
    Uses the fusiDoench V3_model_nopos.pickle.
    """
    if not seq or len(seq) != 30:
        return None
    
    seq = seq.upper()
    valid = set("ACGT")
    if not all(c in valid for c in seq):
        return None
    
    if not os.path.isfile(_MODEL_FILE_NOPOS):
        return None
    
    try:
        import pickle
        import numpy as np
        import pandas as pd
        
        # Need to add paths for the model's dependencies
        sys.path.insert(0, _FUSI_DOENCH_DIR)
        import model_comparison
        import features.featurization as feat
        
        with open(_MODEL_FILE_NOPOS, "rb") as f:
            model_data = pickle.load(f, encoding="bytes")
        
        if isinstance(model_data, tuple) and len(model_data) == 2:
            model, learn_options = model_data
        else:
            model = model_data
            learn_options = {}
        
        # Prepare data for prediction
        Xdf = pd.DataFrame(columns=['30mer', 'Strand'], data=[[seq, 'NA']])
        gene_position = pd.DataFrame(columns=['Percent Peptide', 'Amino Acid Cut position'], 
                                     data=[[-1, -1]])
        
        feature_sets = feat.featurize_data(
            Xdf, learn_options, pd.DataFrame(), gene_position, 
            pam_audit=False, length_audit=False
        )
        inputs, dim, dimsum, feature_names = model_comparison.concatenate_feature_sets(feature_sets)
        
        preds = model.predict(inputs)
        return float(preds[0])
    except Exception:
        return None


def _predict_rs3(seq: str) -> float | None:
    """Run rs3 with compatibility handling for modern LightGBM."""
    if not seq or len(seq) != 30 or not set(seq.upper()) <= set("ACGT"):
        return None
    try:
        from rs3.seq import featurize_context, load_seq_model

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            model = load_seq_model()
            if getattr(model, "_n_classes", None) is None:
                model._n_classes = 0
            features = featurize_context([seq.upper()], sequence_tracr="Hsu2013", n_jobs=1)
            score = float(model.predict(features)[0])
        return score if math.isfinite(score) else None
    except Exception:
        return None


def _execute_model(model_id: str, seq: str) -> tuple[float | None, str]:
    """Execute a specific model by ID.

    If an isolated runtime exists for the model, use it.
    Otherwise, try the main environment.

    Returns:
        (score, model_source_description)
    """
    from core.model_runtime import get_model_status, RuntimeState

    rt_status = get_model_status(model_id)
    runtime_path = rt_status.get("runtime_path")

    # Try isolated runtime first if it exists and is verified
    if runtime_path and os.path.exists(runtime_path) and rt_status.get("state") == RuntimeState.VERIFIED:
        python_bin = os.path.join(runtime_path, "bin", "python")
        if os.path.exists(python_bin):
            score, source = _run_in_isolated_runtime(model_id, python_bin, seq)
            if score is not None:
                return score, f"{source} (isolated runtime: {runtime_path})"

    # Try main environment
    if model_id == "rule_set_2":
        # Try azimuth first, then pickled model
        score = _predict_rs2_azimuth(seq)
        if score is not None:
            return score, "azimuth (Doench 2016 / Azimuth 2.0)"
        score = _predict_rs2_model(seq)
        if score is not None:
            return score, "fusiDoench V3_model_nopos (Doench 2016 / Azimuth 2.0)"
        return None, "unavailable"

    elif model_id == "rule_set_3":
        score = _predict_rs3(seq)
        if score is not None:
            return score, "rs3 LightGBM (Doench 2021 / Rule Set 3; native activity scale)"
        return None, "unavailable"

    elif model_id == "doench_2014":
        score = _predict_doench2014(seq)
        return score, "Doench 2014 linear regression (reimplemented from crisporEffScores)"

    return None, "unknown_model"


def _run_in_isolated_runtime(model_id: str, python_bin: str, seq: str) -> tuple[float | None, str]:
    """Run a model prediction in an isolated runtime via subprocess.

    Args:
        model_id: Model to run
        python_bin: Path to isolated Python binary
        seq: 30-mer context sequence

    Returns:
        (score, source_description)
    """
    import json
    import subprocess
    import tempfile

    spec = {
        "model_id": model_id,
        "context_sequence": seq,
        "backend_dir": _BACKEND_DIR,
        "veyra_dir": _VEYRA_DIR,
    }

    # Write a temporary runner script
    runner_script = f'''
import sys
import json
import os

sys.path.insert(0, "{_BACKEND_DIR}")

spec = json.loads(sys.argv[1])
model_id = spec["model_id"]
seq = spec["context_sequence"]

try:
    if model_id == "rule_set_3":
        import rs3
        from rs3.seq import predict_seq, featurize_context, load_seq_model
        import joblib
        model = load_seq_model()
        if getattr(model, "_n_classes", None) is None:
            model._n_classes = 0
        feats = featurize_context([seq])
        score = float(model.predict(feats)[0])
        print(json.dumps({{"score": score, "source": "rs3 LightGBM (isolated runtime)"}}))

    elif model_id == "rule_set_2":
        import pickle
        import numpy as np
        import pandas as pd
        import sys
        sys.path.insert(0, os.path.join("{_VEYRA_DIR}", "refrences.local", "data", "tools", "crisporWebsite", "bin", "fusiDoench", "analysis"))
        model_path = "{_VEYRA_DIR}/refrences.local/data/tools/crisporWebsite/bin/fusiDoench/saved_models/V3_model_nopos.pickle"
        with open(model_path, "rb") as f:
            model_data = pickle.load(f, encoding="bytes")
        if isinstance(model_data, tuple) and len(model_data) == 2:
            model, learn_options = model_data
        else:
            model = model_data
            learn_options = {{}}
        Xdf = pd.DataFrame(columns=["30mer", "Strand"], data=[[seq, "NA"]])
        gene_position = pd.DataFrame(columns=["Percent Peptide", "Amino Acid Cut position"], data=[[-1, -1]])
        import model_comparison
        import features.featurization as feat
        feature_sets = feat.featurize_data(Xdf, learn_options, pd.DataFrame(), gene_position, pam_audit=False, length_audit=False)
        inputs, dim, dimsum, feature_names = model_comparison.concatenate_feature_sets(feature_sets)
        preds = model.predict(inputs)
        print(json.dumps({{"score": float(preds[0]), "source": "fusiDoench V3 (isolated runtime)"}}))

    else:
        print(json.dumps({{"error": "Unknown model"}}))
        sys.exit(1)

except Exception as e:
    print(json.dumps({{"error": str(e)}}))
    sys.exit(1)
'''

    script_path = os.path.join(_STATE_DIR, f"runner_{model_id}.py")
    with open(script_path, "w") as f:
        f.write(runner_script)

    try:
        result = subprocess.run(
            [python_bin, script_path, json.dumps(spec)],
            capture_output=True, text=True, timeout=120,
            cwd=_BACKEND_DIR,
        )

        if result.returncode != 0:
            return None, f"runtime error: {result.stderr.strip()[:200]}"

        output = json.loads(result.stdout.strip())
        if "error" in output:
            return None, f"runtime error: {output['error'][:200]}"

        return output["score"], output["source"]

    except subprocess.TimeoutExpired:
        return None, "runtime timeout"
    except json.JSONDecodeError:
        return None, f"runtime parse error: {result.stdout[:200]}"
    except Exception as e:
        return None, f"runtime error: {e}"
    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


def predict_ontarget_efficiency(request: ComputeOnTargetEfficiencyRequest) -> VeyraResult:
    """Predict on-target SpCas9 efficiency.
    
    This is fundamentally different from CFD/off-target specificity.
    It answers: "How efficiently is this intended guide expected to cut?"
    
    Model selection:
    - model="auto": Select highest-priority verified model (rule_set_3 > rule_set_2 > doench_2014)
    - model="rule_set_3": Use Rule Set 3 specifically (fail if unavailable)
    - model="rule_set_2": Use Rule Set 2 specifically (fail if unavailable)
    - model="doench_2014": Use Doench 2014 specifically
    - model="both": Legacy alias for auto
    
    Args:
        request: ComputeOnTargetEfficiencyRequest with context_sequence, model, etc.
    
    Returns:
        VeyraResult with on-target efficiency scores and selection metadata.
    """
    from mcp.schemas import validate_dna_sequence

    errors = []
    warnings = []

    # Validate context sequence
    try:
        full_seq = validate_dna_sequence(request.context_sequence)
    except ValueError as e:
        return VeyraResult(
            tool="predict_ontarget_efficiency",
            errors=[f"Invalid context_sequence: {e}"],
        )
    
    # Compute expected context length (PAM is 3 nt for NGG)
    pam_len = 3
    context_length = request.context_upstream + request.spacer_length + pam_len + request.context_downstream
    
    if len(full_seq) != context_length:
        return VeyraResult(
            tool="predict_ontarget_efficiency",
            errors=[
                f"Context length mismatch: expected {context_length} nt "
                f"({request.context_upstream} up + {request.spacer_length} spacer + "
                f"{pam_len} PAM + {request.context_downstream} down), got {len(full_seq)} nt"
            ],
            summary={
                "confidence_flag": "context_length_mismatch",
                "context_length": len(full_seq),
                "expected_context_length": context_length,
            },
        )
    
    # Extract spacer from context
    spacer_start = request.context_upstream
    spacer_end = spacer_start + request.spacer_length
    spacer = full_seq[spacer_start:spacer_end]
    pam = full_seq[spacer_end:spacer_end + pam_len]
    
    # Validate PAM position
    if len(pam) < pam_len:
        return VeyraResult(
            tool="predict_ontarget_efficiency",
            errors=["Could not extract PAM from context sequence"],
        )
    
    # Model selection - support "auto" and "both" as aliases.
    requested_model = request.model.lower()
    if requested_model == "both":
        requested_model = "auto"

    # Prediction must not create environments or install packages implicitly.
    # Runtime provisioning is an explicit management operation.
    model_used, selection = select_model(requested_model, auto_provision=False)
    
    # If explicit model requested but unavailable, return error
    if requested_model != "auto" and model_used is None:
        registry = get_model_registry()
        info = registry.get(requested_model)
        return VeyraResult(
            tool="predict_ontarget_efficiency",
            errors=[f"Model '{requested_model}' is not available: {info.error_message if info else 'unknown model'}"],
            summary={
                "confidence_flag": "model_unavailable",
                "requested_model": requested_model,
                "selection": selection,
            },
        )
    
    # If auto and no verified model available
    if model_used is None:
        return VeyraResult(
            tool="predict_ontarget_efficiency",
            errors=["No verified on-target model available"],
            summary={
                "confidence_flag": "no_verified_model",
                "requested_model": "auto",
                "selection": selection,
            },
        )
    
    # Execute selected model
    # Construct 30-mer for model execution (standard: 4 up + 20 spacer + 3 PAM + 3 down)
    if request.context_upstream >= 4 and request.context_downstream >= 3:
        exec_seq = full_seq[:30] if len(full_seq) >= 30 else full_seq
        if len(exec_seq) < 30:
            exec_seq = exec_seq + "N" * (30 - len(exec_seq))
    else:
        # Model requires specific context - use what we have
        exec_seq = full_seq[:30] if len(full_seq) >= 30 else full_seq
        if len(exec_seq) < 30:
            exec_seq = exec_seq + "N" * (30 - len(exec_seq))
        warnings.append(
            f"Model {model_used} prefers >=4 nt upstream and >=3 nt downstream; "
            f"using available context ({request.context_upstream} up / {request.context_downstream} down)"
        )
    
    score, model_source = _execute_model(model_used, exec_seq)
    
    if score is None:
        # Model execution failed despite being marked available
        registry = get_model_registry()
        info = registry.get(model_used)
        return VeyraResult(
            tool="predict_ontarget_efficiency",
            errors=[f"Model '{model_used}' execution failed"],
            summary={
                "confidence_flag": "execution_failed",
                "requested_model": requested_model,
                "model_used": model_used,
                "selection": selection,
            },
        )
    
    # Normalization
    normalized = False
    if request.normalize_score:
        if model_used == "rule_set_3":
            warnings.append("Rule Set 3 exposes a native activity score; no validated 0-1 normalization was applied")
        else:
            normalized = True
    
    # Rounding
    round_decimals = request.round_decimals
    rounded_score = round(score, round_decimals)
    
    # Build comprehensive summary
    summary = {
        "tool": "predict_ontarget_efficiency",
        "context_length": len(full_seq),
        "spacer_length": request.spacer_length,
        "context_upstream": request.context_upstream,
        "context_downstream": request.context_downstream,
        "spacer": spacer,
        "pam": pam,
        "requested_model": requested_model,
        "model_used": model_used,
        "model_source": model_source,
        "model_version": get_model_info(model_used).version if get_model_info(model_used) else "unknown",
        "output_scale": get_model_info(model_used).output_scale if get_model_info(model_used) else "unknown",
        "selection_status": selection["selection_status"],
        "fallback_used": selection["fallback_used"],
        "fallback_from": selection["fallback_from"],
        "fallback_to": selection["fallback_to"],
        "fallback_reason": selection["fallback_reason"],
        "fallback_chain": selection["fallback_chain"],
        "normalized": normalized,
        "feature_source": "computed",
        "round_decimals": round_decimals,
    }
    
    # Add score with model-specific key
    if model_used == "rule_set_2":
        summary["ontarget_score_rule_set_2"] = rounded_score
        summary["raw_score_rule_set_2"] = score
    elif model_used == "rule_set_3":
        summary["ontarget_score_rule_set_3"] = rounded_score
        summary["raw_score_rule_set_3"] = score
    elif model_used == "doench_2014":
        summary["ontarget_score_doench_2014"] = rounded_score
        summary["raw_score_doench_2014"] = score
    
    # Also add generic score field for backward compatibility
    summary["ontarget_score"] = rounded_score
    summary["raw_score"] = score
    
    # Confidence flag
    if selection["selection_status"] == "selected" and not selection["fallback_used"]:
        confidence_flag = "ok"
    elif selection["fallback_used"]:
        confidence_flag = "fallback"
    else:
        confidence_flag = "partial"
    
    summary["confidence_flag"] = confidence_flag
    
    if request.precomputed_features:
        summary["precomputed_features_used"] = True
    
    return VeyraResult(
        tool="predict_ontarget_efficiency",
        summary=summary,
        errors=errors,
        warnings=warnings,
    )
