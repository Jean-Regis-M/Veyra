import asyncio

import httpx
import pytest

from veyra.midend.http_api.app import app
from veyra.midend.skills.offtarget_toxicity_risk import (
    CoefficientModel,
    RiskModelError,
    bounded_binding_feature,
    calculate_risk,
    stable_logistic,
)


def test_stable_logistic_extremes():
    assert stable_logistic(1000.0) == pytest.approx(1.0)
    assert stable_logistic(-1000.0) == pytest.approx(0.0)
    assert stable_logistic(0.0) == pytest.approx(0.5)


def test_bounded_binding_feature_is_safe_and_monotonic():
    assert bounded_binding_feature(0.0) == 0.0
    assert bounded_binding_feature(-1e-12) > 0.0
    assert bounded_binding_feature(-10.0) > bounded_binding_feature(-1.0)
    assert bounded_binding_feature(-10.0) < 1.0
    with pytest.raises(RiskModelError):
        bounded_binding_feature(0.1)
    with pytest.raises(RiskModelError):
        bounded_binding_feature(-1.0, 0.0)


def test_formula_contributions_and_documented_signs():
    model = CoefficientModel("test", alpha=-2.0, beta=3.0, gamma=4.0,
                            calibration_status="user_supplied")
    result = calculate_risk(sh=0.25, delta_g_binding=-2.0, ca=0.5, coefficients=model)
    assert result["contributions"]["sequence"] == pytest.approx(-0.5)
    assert result["contributions"]["binding"] > 0
    assert result["contributions"]["accessibility"] > 0
    assert 0.0 < result["toxicity_risk"] < 100.0


def test_calibrated_model_requires_dataset_and_metrics():
    with pytest.raises(RiskModelError):
        CoefficientModel("bad", 1.0, 1.0, 1.0, calibration_status="calibrated")


def test_missing_features_are_explicit_and_not_substituted():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            status = await client.get("/skills/offtarget_toxicity_risk/status")
            assert status.status_code == 200
            assert status.json()["feature_availability"]["delta_g_binding"]["available"] is False
            response = await client.post("/skills/offtarget_toxicity_risk", json={
                "spacer_sequence": "CTAGCCTACGGATCAGCCTC",
            })
            assert response.status_code == 202
            execution_id = response.json()["execution_id"]
            await asyncio.sleep(0.03)
            execution = (await client.get(f"/executions/{execution_id}")).json()
            result = execution["skill_result"]
            assert result["status"] == "unavailable"
            assert result["validated"] is False
            assert result["toxicity_risk"] is None
            assert result["features"]["Sh"]["status"] == "unavailable"
            assert any("CFD" in warning for warning in result["warnings"])
    asyncio.run(run())


def test_explicit_features_are_prototype_not_validated():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/skills/offtarget_toxicity_risk", json={
                "spacer_sequence": "CTAGCCTACGGATCAGCCTC",
                "features": {"Sh": 0.1, "delta_g_binding": -2.0, "Ca": 0.8},
                "coefficients": {"alpha": -1.0, "beta": 2.0, "gamma": 1.0},
            })
            execution_id = response.json()["execution_id"]
            await asyncio.sleep(0.03)
            result = (await client.get(f"/executions/{execution_id}")).json()["skill_result"]
            assert result["status"] == "prototype"
            assert result["validated"] is False
            assert result["toxicity_risk"] is not None
            assert result["calibration"]["status"] == "user_supplied"
    asyncio.run(run())
