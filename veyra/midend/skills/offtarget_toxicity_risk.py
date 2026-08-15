"""Audited, evidence-gated off-target toxicity-risk model.

The module provides numerically safe transforms and calibration metadata. The
skill orchestration below never derives scientific features from unrelated
backend outputs: CFD is not Sh, guide MFE is not hybridization DeltaG, and
model attention is not chromatin accessibility.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .base import Skill, SkillError, SkillMetadata

EPSILON_DEFAULT = 1e-3
FEATURE_DEFINITION_VERSION = "offtarget-toxicity-v1-audited"

VALID_CALIBRATION_STATUSES = {
    "not_provided",
    "unavailable",
    "uncalibrated",
    "user_supplied",
    "calibrated",
    "external_calibration",
    "externally_validated",
}


class RiskModelError(ValueError):
    pass


@dataclass(frozen=True)
class CoefficientModel:
    model_id: str
    alpha: float | None
    beta: float | None
    gamma: float | None
    epsilon: float = EPSILON_DEFAULT
    feature_definition_version: str = FEATURE_DEFINITION_VERSION
    dataset: str | None = None
    dataset_version: str | None = None
    fitting_method: str | None = None
    calibration_status: str = "uncalibrated"
    fitted_at: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.calibration_status not in VALID_CALIBRATION_STATUSES:
            raise RiskModelError(f"invalid calibration_status '{self.calibration_status}'")
        if not math.isfinite(self.epsilon) or self.epsilon <= 0:
            raise RiskModelError("epsilon must be finite and greater than zero")
        for value in (self.alpha, self.beta, self.gamma):
            if value is not None and not math.isfinite(value):
                raise RiskModelError("coefficients must be finite numbers")
        if self.calibration_status in {"calibrated", "externally_validated"} and (not self.dataset or not self.metrics):
            raise RiskModelError("calibrated models require dataset and metrics")

    def public(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id, "alpha": self.alpha, "beta": self.beta,
            "gamma": self.gamma, "epsilon": self.epsilon,
            "feature_definition_version": self.feature_definition_version,
            "dataset": self.dataset, "dataset_version": self.dataset_version,
            "fitting_method": self.fitting_method, "calibration_status": self.calibration_status,
            "fitted_at": self.fitted_at, "metrics": self.metrics,
        }


COEFFICIENT_REGISTRY: dict[str, CoefficientModel] = {
    "offtarget_toxicity_prototype": CoefficientModel(
        model_id="offtarget_toxicity_prototype", alpha=None, beta=None, gamma=None,
        calibration_status="uncalibrated",
    )
}


def register_coefficient_model(model: CoefficientModel) -> None:
    COEFFICIENT_REGISTRY[model.model_id] = model


def stable_logistic(z: float) -> float:
    """Stable sigma(z), including finite extreme values without overflow."""
    if not math.isfinite(z):
        raise RiskModelError("linear score must be finite")
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    exp_z = math.exp(z)
    return exp_z / (1.0 + exp_z)


def bounded_binding_feature(delta_g_binding: float, epsilon: float = EPSILON_DEFAULT) -> float:
    """Return B in [0,1): larger magnitude of valid negative DeltaG is larger B."""
    if not math.isfinite(delta_g_binding):
        raise RiskModelError("delta_g_binding must be finite")
    if delta_g_binding > 0:
        raise RiskModelError("delta_g_binding must be zero or negative kcal/mol")
    if not math.isfinite(epsilon) or epsilon <= 0:
        raise RiskModelError("epsilon must be finite and greater than zero")
    magnitude = abs(delta_g_binding)
    return magnitude / (magnitude + epsilon)


def _bounded_unit(name: str, value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise RiskModelError(f"{name} must be a finite number")
    if not 0.0 <= value <= 1.0:
        raise RiskModelError(f"{name} must be between 0 and 1")
    return float(value)


def calculate_risk(*, sh: float, delta_g_binding: float, ca: float,
                   coefficients: CoefficientModel) -> dict[str, Any]:
    """Calculate only when all required features and coefficients are present.

    Sh remains the blueprint's mismatch penalty. B is the audited bounded
    stability transform. Ca is accessibility itself, so larger Ca contributes
    in the positive direction when gamma is positive. Coefficient signs are
    calibration parameters, not biological assumptions baked into code.
    """
    sh_value = _bounded_unit("Sh", sh)
    ca_value = _bounded_unit("Ca", ca)
    if coefficients.alpha is None or coefficients.beta is None or coefficients.gamma is None:
        raise RiskModelError("alpha, beta, and gamma are required for calculation")
    binding = bounded_binding_feature(delta_g_binding, coefficients.epsilon)
    sequence_contribution = coefficients.alpha * sh_value
    binding_contribution = coefficients.beta * binding
    accessibility_contribution = coefficients.gamma * ca_value
    linear = sequence_contribution + binding_contribution + accessibility_contribution
    logistic = stable_logistic(linear)
    return {
        "linear_score": linear,
        "logistic_score": logistic,
        "toxicity_risk": 100.0 * logistic,
        "binding_feature": binding,
        "contributions": {
            "sequence": sequence_contribution,
            "binding": binding_contribution,
            "accessibility": accessibility_contribution,
        },
    }


class OfftargetToxicityRiskSkill(Skill):
    metadata = SkillMetadata(
        skill_id="offtarget_toxicity_risk",
        name="Off-target toxicity risk (evidence-gated prototype)",
        description="Audit and combine explicitly available off-target risk features without scientific substitution.",
        version="1.0.0",
        required_inputs=[{"name": "spacer_sequence", "type": "string", "required": True}],
        optional_inputs=[
            {"name": "calibration_input_id", "type": "string", "default": None},
            {"name": "genome_id", "type": "string", "default": None},
            {"name": "features", "type": "object", "default": {}},
            {"name": "coefficients", "type": "object", "default": None},
            {"name": "coefficient_model_id", "type": "string", "default": "offtarget_toxicity_prototype"},
            {"name": "max_mismatches", "type": "integer", "default": 4, "minimum": 0, "maximum": 10},
        ],
        allowed_tools=["offtarget_search", "cas_offinder_search", "analyze_mismatch_seed", "score_offtargets"],
        workflow=["validate guide, optional calibration input, and explicit feature inputs",
                  "collect optional off-target evidence",
                  "mark exact scientific feature availability",
                  "apply audited formula or calibrated fit only when complete",
                  "return calibration status, metrics, and provenance"],
        output_schema={"status": "complete|partial|prototype|unavailable", "validated": "boolean",
                       "toxicity_risk": "number|null", "features": "object", "contributions": "object",
                       "calibration": "object"},
        validation_rules=[
            "spacer_sequence must be concrete A/C/G/T and 15-30 nt.",
            "calibration_input is OPTIONAL. Skill functions normally without calibration data.",
            "Sh, delta_g_binding, and Ca are never inferred from CFD, guide MFE, or model attention.",
            "delta_g_binding must be finite and <= 0 when supplied.",
            "calibrated is only valid with identified dataset and metrics.",
        ],
    )

    def model_status(self) -> dict[str, Any]:
        return {
            "model": self.metadata.skill_id,
            "formula_version": FEATURE_DEFINITION_VERSION,
            "formula": "T=100*stable_logistic(alpha*Sh + beta*B + gamma*Ca)",
            "binding_transform": "B=abs(delta_g_binding)/(abs(delta_g_binding)+epsilon)",
            "feature_availability": {
                "Sh": {"available": False, "source": None, "reason": "No exact full-locus mismatch-penalty feature in current backend."},
                "delta_g_binding": {"available": False, "source": None, "reason": "No gRNA-DNA hybridization free-energy provider."},
                "Ca": {"available": False, "source": None, "reason": "No calibrated chromatin-accessibility provider."},
            },
            "coefficient_models": [model.public() for model in COEFFICIENT_REGISTRY.values()],
        }

    def validate(self, request: dict[str, Any], control_plane: Any) -> None:
        guide = request.get("spacer_sequence")
        if not isinstance(guide, str) or not 15 <= len(guide.strip()) <= 30 or any(ch not in "ACGT" for ch in guide.strip().upper()):
            raise SkillError("invalid_spacer_sequence", "spacer_sequence must be 15-30 concrete A/C/G/T bases.", "spacer_sequence")
        if request.get("genome_id") is not None and not isinstance(request["genome_id"], str):
            raise SkillError("invalid_genome_id", "genome_id must be a string.", "genome_id")
        max_mismatches = request.get("max_mismatches", 4)
        if not isinstance(max_mismatches, int) or not 0 <= max_mismatches <= 10:
            raise SkillError("invalid_max_mismatches", "max_mismatches must be between 0 and 10.", "max_mismatches")
        calib_id = (
            request.get("calibration_input_id")
            or request.get("calibration_input")
            or request.get("calibration_id")
        )
        if calib_id:
            control_plane.inputs.get_calibration_input(calib_id)

    @staticmethod
    def _coefficient_model(request: dict[str, Any], control_plane: Any = None) -> CoefficientModel:
        supplied = request.get("coefficients")
        if supplied is not None:
            required = ("alpha", "beta", "gamma")
            if any(key not in supplied for key in required):
                raise SkillError("invalid_coefficients", "coefficients must contain alpha, beta, and gamma.", "coefficients")
            try:
                return CoefficientModel(
                    model_id="user_supplied", alpha=float(supplied["alpha"]), beta=float(supplied["beta"]),
                    gamma=float(supplied["gamma"]), epsilon=float(supplied.get("epsilon", EPSILON_DEFAULT)),
                    feature_definition_version=FEATURE_DEFINITION_VERSION,
                    calibration_status="user_supplied", fitting_method="user supplied",
                )
            except (TypeError, ValueError, RiskModelError) as exc:
                raise SkillError("invalid_coefficients", str(exc), "coefficients") from None

        model_id = request.get("coefficient_model_id")
        if model_id and model_id in COEFFICIENT_REGISTRY:
            return COEFFICIENT_REGISTRY[model_id]

        calib_id = (
            request.get("calibration_input_id")
            or request.get("calibration_input")
            or request.get("calibration_id")
        )
        if calib_id:
            model_key = f"calibrated_{calib_id}"
            if model_key in COEFFICIENT_REGISTRY:
                return COEFFICIENT_REGISTRY[model_key]

        return COEFFICIENT_REGISTRY.get(model_id or "offtarget_toxicity_prototype",
                                        COEFFICIENT_REGISTRY["offtarget_toxicity_prototype"])

    @staticmethod
    def _feature_record(value: Any, status: str, source: str | None) -> dict[str, Any]:
        return {"value": value, "status": status, "source": source}

    async def execute(self, request: dict[str, Any], *, control_plane: Any,
                      call_tool: Any, emit: Any) -> dict[str, Any]:
        self.validate(request, control_plane)
        guide = request["spacer_sequence"].strip().upper()
        warnings: list[str] = []
        errors: list[str] = []
        provenance: list[str] = []
        features = request.get("features") or {}

        calib_id = (
            request.get("calibration_input_id")
            or request.get("calibration_input")
            or request.get("calibration_id")
        )
        if calib_id:
            provenance.append(f"calibration_dataset:{calib_id}")

        model = self._coefficient_model(request, control_plane)

        feature_values = {
            "Sh": self._feature_record(features.get("Sh"), "user_supplied" if "Sh" in features else "unavailable",
                                        "user_request" if "Sh" in features else None),
            "delta_g_binding": self._feature_record(features.get("delta_g_binding"), "user_supplied" if "delta_g_binding" in features else "unavailable",
                                                     "user_request" if "delta_g_binding" in features else None),
            "Ca": self._feature_record(features.get("Ca"), "user_supplied" if "Ca" in features else "unavailable",
                                        "user_request" if "Ca" in features else None),
        }

        # Existing backend search is useful evidence, but it does not define
        # Sh. Its presence is recorded without converting it to a feature.
        if request.get("genome_id"):
            genome = await call_tool("genome_info", {"genome_id": request["genome_id"]})
            provenance.append("genome_info")
            if genome.errors:
                warnings.extend(genome.errors)
                calib_status = model.calibration_status if calib_id or request.get("coefficients") else "not_provided"
                return {
                    "model": self.metadata.skill_id, "status": "partial", "validated": False,
                    "toxicity_risk": None, "linear_score": None, "logistic_score": None,
                    "features": feature_values,
                    "feature_transforms": {},
                    "contributions": {"sequence": None, "binding": None, "accessibility": None},
                    "coefficients": model.public(),
                    "calibration": {"status": calib_status, "model_id": model.model_id,
                                    "dataset": model.dataset, "dataset_version": model.dataset_version,
                                    "metrics": model.metrics},
                    "provenance": provenance, "warnings": warnings,
                    "errors": ["genome_unavailable"],
                }
            result = await call_tool("offtarget_search", {
                "spacer_sequence": guide, "genome_id": request["genome_id"],
                "pam_pattern": "NGG", "max_mismatches": request.get("max_mismatches", 4),
                "backend": request.get("backend", "bwa"), "search_scope": "genome",
                "strand_search": "both", "max_results": request.get("max_results", 1000),
            })
            provenance.append("offtarget_search")
            if result.errors:
                warnings.extend(result.errors)
            else:
                warnings.append("Off-target search completed, but its results are not the blueprint-defined full-locus Sh feature.")

        warnings.extend([
            "Sh is unavailable unless explicitly supplied; CFD/mismatch count is not substituted.",
            "gRNA-DNA hybridization delta_g_binding is unavailable unless explicitly supplied; guide MFE is not substituted.",
            "Ca chromatin accessibility is unavailable unless explicitly supplied; model attention is not substituted.",
        ])
        calculation: dict[str, Any] | None = None
        try:
            if any(feature_values[name]["status"] == "unavailable" for name in feature_values):
                raise RiskModelError("one or more required scientific features are unavailable")
            calculation = calculate_risk(sh=feature_values["Sh"]["value"],
                                         delta_g_binding=feature_values["delta_g_binding"]["value"],
                                         ca=feature_values["Ca"]["value"], coefficients=model)
        except RiskModelError as exc:
            errors.append(str(exc))

        validated = bool(calculation and model.calibration_status in {"calibrated", "external_calibration", "externally_validated"})
        if calculation:
            status = "complete" if validated else "prototype"
        else:
            status = "partial" if provenance else "unavailable"
        if not validated:
            warnings.append("This result is unvalidated/prototype; no labeled calibration dataset and fit metrics establish validity.")

        calib_status = model.calibration_status
        if not calib_id and request.get("coefficients") is None and model.model_id == "offtarget_toxicity_prototype":
            if status == "unavailable":
                calib_status = "not_provided"
            else:
                calib_status = "uncalibrated"

        result = {
            "model": self.metadata.skill_id, "status": status, "validated": validated,
            "toxicity_risk": calculation["toxicity_risk"] if calculation else None,
            "linear_score": calculation["linear_score"] if calculation else None,
            "logistic_score": calculation["logistic_score"] if calculation else None,
            "features": feature_values,
            "feature_transforms": {
                "Sh": "raw mismatch penalty: 0 perfect complement, 1 maximal mismatch",
                "delta_g_binding": "B=abs(delta_g_binding)/(abs(delta_g_binding)+epsilon); larger B means more stable binding",
                "Ca": "raw accessibility estimate: larger Ca means more accessible chromatin",
            },
            "contributions": calculation["contributions"] if calculation else {"sequence": None, "binding": None, "accessibility": None},
            "coefficients": model.public(),
            "calibration": {"status": calib_status, "model_id": model.model_id,
                            "dataset": model.dataset, "dataset_version": model.dataset_version,
                            "metrics": model.metrics},
            "provenance": provenance,
            "warnings": warnings,
            "errors": errors,
        }
        await emit("risk_features_evaluated", feature_status={name: value["status"] for name, value in feature_values.items()})
        await emit("risk_model_completed", status=status, validated=validated, toxicity_risk=result["toxicity_risk"])
        return result
