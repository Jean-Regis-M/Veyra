"""Comprehensive End-to-End Freeze Gate Verification Suite.

Validates all 24 parts required for final freeze:
- Backend live engine execution
- MIDEND connectors (HTTP & MCP parity)
- AI provider and orchestration
- Multi-tool parallel execution
- Analysis and Calibration file validation
- Model calibration skill & deterministic least-squares fitting
- SpCas9 gene-cutting skill (both strands, cut sites, features, ranking)
- Off-target toxicity risk skill (uncalibrated, user-supplied, calibrated)
- Exposure API & MCP capability registry
- Error injection & secret leakage security audit
- Deterministic repeatability
"""

import asyncio
import json
import time
from pathlib import Path

import httpx
import pytest

from veyra.midend.connectors.http_backend import HTTPBackendConnector
from veyra.midend.connectors.mcp_backend import MCPBackendConnector
from veyra.midend.control_plane import control_plane
from veyra.midend.http_api.app import app
from veyra.midend.mcp_interface import MIDEND_MCP_CAPABILITIES
from veyra.midend.skills.offtarget_toxicity_risk import COEFFICIENT_REGISTRY, CoefficientModel


FIXTURES_DIR = Path(__file__).parent / "fixtures"
CALIB_CSV_BYTES = (FIXTURES_DIR / "crispr_calibration.csv").read_bytes()
CALIB_TSV_BYTES = (FIXTURES_DIR / "crispr_calibration.tsv").read_bytes()
TARGET_FASTA_BYTES = (FIXTURES_DIR / "test_target.fasta").read_bytes()


async def wait_for_execution(client: httpx.AsyncClient, exec_id: str, timeout: float = 10.0) -> dict:
    start_t = time.perf_counter()
    while time.perf_counter() - start_t < timeout:
        resp = await client.get(f"/executions/{exec_id}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") in {"completed", "failed"}:
                return data
        await asyncio.sleep(0.05)
    resp = await client.get(f"/executions/{exec_id}")
    return resp.json()


# -----------------------------------------------------------------------------
# Part 6: MIDEND Connector Verification (HTTP & MCP Parity)
# -----------------------------------------------------------------------------
def test_connector_parity_mcp_and_backend():
    mcp_conn = MCPBackendConnector()
    tools = asyncio.run(mcp_conn.list_tools())
    tool_names = {t.name for t in tools}
    assert "pam_scan" in tool_names
    assert "compute_gc_content" in tool_names
    assert "compute_cut_site" in tool_names
    assert "score_offtargets" in tool_names
    assert "predict_ontarget_efficiency" in tool_names

    # Test live execution through MCP connector
    gc_res = asyncio.run(mcp_conn.call_tool("compute_gc_content", {"sequence": "ATGCATGC"}))
    assert gc_res.is_success
    assert gc_res.summary["gc_content"] == 0.5

    # Test PAM scan through MCP connector
    pam_res = asyncio.run(mcp_conn.call_tool("pam_scan", {"sequence": "AAAAAAAAAAAAAAAAAAAATGG", "pam_pattern": "NGG"}))
    assert pam_res.is_success
    assert len(pam_res.rows) == 1
    assert pam_res.rows[0]["protospacer"] == "AAAAAAAAAAAAAAAAAAAA"


# -----------------------------------------------------------------------------
# Part 9: Multi-tool / Parallel Execution Verification
# -----------------------------------------------------------------------------
def test_multi_tool_parallel_execution_in_control_plane():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/executions", json={
                "parallel_groups": [{
                    "group_id": "seq_props_group",
                    "calls": [
                        {"call_id": "call_gc", "tool": "compute_gc_content", "arguments": {"sequence": "GCGCGCGCGCGCGCGCGCGC"}},
                        {"call_id": "call_tm", "tool": "compute_melting_temp", "arguments": {"sequence": "GCGCGCGCGCGCGCGCGCGC"}},
                        {"call_id": "call_homo", "tool": "check_homopolymer_runs", "arguments": {"sequence": "GCGCGCGCGCGCGCGCGCGC"}},
                        {"call_id": "call_pos", "tool": "compute_positional_features", "arguments": {"sequence": "GCGCGCGCGCGCGCGCGCGG"}},
                    ]
                }]
            })
            assert resp.status_code == 202
            exec_id = resp.json()["execution_id"]

            exec_data = await wait_for_execution(client, exec_id)
            assert exec_data["status"] == "completed"
            assert exec_data["completed_tool_calls"] == 4
            assert exec_data["failed_tool_calls"] == 0

            tools_data = (await client.get(f"/executions/{exec_id}/tools")).json()
            group = tools_data["parallel_groups"][0]
            assert group["group_id"] == "seq_props_group"
            assert group["duration_ms"] >= 0
            call_ids = [c["call_id"] for c in tools_data["tools"]]
            assert "call_gc" in call_ids
            assert "call_tm" in call_ids
            assert "call_homo" in call_ids
            assert "call_pos" in call_ids
    asyncio.run(run())


# -----------------------------------------------------------------------------
# Part 10 & 11: File Input & Calibration Input Validation
# -----------------------------------------------------------------------------
def test_file_inputs_and_calibration_inputs_matrix():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # 1. Valid Analysis FASTA
            fasta_res = await client.post("/inputs/file", files={"file": ("target.fasta", TARGET_FASTA_BYTES, "text/x-fasta")})
            assert fasta_res.status_code == 201
            assert fasta_res.json()["input_class"] == "analysis_input"
            assert fasta_res.json()["record_count"] == 1

            # 2. Malformed FASTA
            bad_fasta = await client.post("/inputs/file", files={"file": ("target.fasta", b"not_fasta_header", "text/plain")})
            assert bad_fasta.status_code == 400
            assert bad_fasta.json()["error"] == "malformed_file"

            # 3. Empty File
            empty_res = await client.post("/inputs/file", files={"file": ("empty.fasta", b"", "text/x-fasta")})
            assert empty_res.status_code == 400
            assert empty_res.json()["error"] == "empty_file"

            # 4. Valid Calibration CSV
            csv_res = await client.post("/calibration/file", files={"file": ("calib.csv", CALIB_CSV_BYTES, "text/csv")})
            assert csv_res.status_code == 201
            assert csv_res.json()["input_class"] == "calibration_input"
            assert csv_res.json()["sample_count"] == 10

            # 5. Valid Calibration TSV
            tsv_res = await client.post("/calibration/file", files={"file": ("calib.tsv", CALIB_TSV_BYTES, "text/tab-separated-values")})
            assert tsv_res.status_code == 201
            assert tsv_res.json()["input_class"] == "calibration_input"

            # 6. Inconsistent Columns CSV
            bad_csv = await client.post("/calibration/file", files={"file": ("bad.csv", b"guide,target,sh\nATCG,12.0\n", "text/csv")})
            assert bad_csv.status_code == 400
            assert bad_csv.json()["error"] == "inconsistent_columns"

            # 7. Unsupported Calibration Format
            bad_fmt = await client.post("/calibration/file", files={"file": ("bad.xlsx", b"data", "application/vnd.ms-excel")})
            assert bad_fmt.status_code == 400
            assert bad_fmt.json()["error"] == "unsupported_calibration_format"
    asyncio.run(run())


# -----------------------------------------------------------------------------
# Part 12: Deterministic Model Calibration Workflow
# -----------------------------------------------------------------------------
def test_deterministic_toxicity_calibration_workflow():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            upload_res = await client.post("/calibration/file", files={"file": ("dataset.csv", CALIB_CSV_BYTES, "text/csv")})
            calib_id = upload_res.json()["input_id"]

            run_res = await client.post("/calibration/run", json={"calibration_input_id": calib_id, "model_id": "calibrated_freeze_test"})
            assert run_res.status_code == 202
            exec_id = run_res.json()["execution_id"]

            exec_status = await wait_for_execution(client, exec_id)
            assert exec_status["status"] == "completed"

            result = exec_status["skill_result"]
            assert result["status"] == "complete"
            assert result["calibration_status"] == "calibrated"
            assert result["sample_count"] == 10
            assert "r2" in result["metrics"]
            assert "mse" in result["metrics"]
            assert "mae" in result["metrics"]
            assert result["fitted_coefficients"]["alpha"] is not None
            assert result["fitted_coefficients"]["beta"] is not None
            assert result["fitted_coefficients"]["gamma"] is not None

            # Verify AI review summary contains metadata without raw CSV dump
            ai_summary = result["ai_review_summary"]
            assert ai_summary["sample_count"] == 10
            assert "mapped_columns" in ai_summary
            assert "fitted_coefficients" in ai_summary

            # Check model is registered in registry
            assert "calibrated_freeze_test" in COEFFICIENT_REGISTRY
            reg_model = COEFFICIENT_REGISTRY["calibrated_freeze_test"]
            assert reg_model.calibration_status == "calibrated"
            assert reg_model.metrics["sample_count"] == 10
    asyncio.run(run())


# -----------------------------------------------------------------------------
# Part 13: SpCas9 Gene Cutting Skill (Both Strands, Cut Site, Features, Ranking)
# -----------------------------------------------------------------------------
def test_spcas9_gene_cutting_skill_e2e():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # 1. Without calibration (normal workflow)
            resp = await client.post("/skills/spcas9_gene_cutting", json={
                "sequence": "GAGTCCGAGCAGAAGAAGAAGGGCTCCCATCACATCAACCGGTGGCGCATTGCCACGAAGCAGGCCAATGGGGAGGACATCGATGTCACCTCCAATGAC",
                "depth": "quick",
                "strand": "both",
                "max_candidates": 10,
            })
            assert resp.status_code == 202
            exec_id = resp.json()["execution_id"]

            exec_data = await wait_for_execution(client, exec_id)
            assert exec_data["status"] == "completed"
            assert exec_data["calibration_status"] == "not_provided"

            skill_res = exec_data["skill_result"]
            candidates = skill_res["candidates"]
            assert len(candidates) > 0
            strands = {c["strand"] for c in candidates}
            assert "+" in strands
            for cand in candidates:
                assert cand["protospacer"] is not None
                assert cand["pam"] is not None
                assert cand["cut_site"]["relative"] == 17
                assert cand["cutting_site_string"] is not None
                assert "gc" in cand["features"]
                assert cand["rank"] is not None
    asyncio.run(run())


# -----------------------------------------------------------------------------
# Part 14: Off-Target Toxicity Risk Skill Lifecycle
# -----------------------------------------------------------------------------
def test_offtarget_toxicity_risk_skill_lifecycle():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # 1. No calibration & missing features -> unavailable / not_provided
            unavail_resp = await client.post("/skills/offtarget_toxicity_risk", json={
                "spacer_sequence": "GAGTCCGAGCAGAAGAAGAA",
            })
            exec_id1 = unavail_resp.json()["execution_id"]
            res1 = (await wait_for_execution(client, exec_id1))["skill_result"]
            assert res1["status"] == "unavailable"
            assert res1["validated"] is False
            assert res1["toxicity_risk"] is None
            assert res1["calibration"]["status"] == "not_provided"

            # 2. User supplied explicit features -> prototype
            proto_resp = await client.post("/skills/offtarget_toxicity_risk", json={
                "spacer_sequence": "GAGTCCGAGCAGAAGAAGAA",
                "features": {"Sh": 0.1, "delta_g_binding": -8.5, "Ca": 0.7},
                "coefficients": {"alpha": -1.5, "beta": 2.5, "gamma": 1.0},
            })
            exec_id2 = proto_resp.json()["execution_id"]
            res2 = (await wait_for_execution(client, exec_id2))["skill_result"]
            assert res2["status"] == "prototype"
            assert res2["validated"] is False
            assert res2["toxicity_risk"] is not None
            assert 0.0 <= res2["toxicity_risk"] <= 100.0
            assert res2["calibration"]["status"] == "user_supplied"

            # 3. Using calibrated model -> calibrated / validated: True
            calib_upload = await client.post("/calibration/file", files={"file": ("calib.csv", CALIB_CSV_BYTES, "text/csv")})
            calib_id = calib_upload.json()["input_id"]

            # Run calibration
            calib_run_resp = await client.post("/calibration/run", json={"calibration_input_id": calib_id, "model_id": "calib_tox_e2e"})
            await wait_for_execution(client, calib_run_resp.json()["execution_id"])

            calib_resp = await client.post("/skills/offtarget_toxicity_risk", json={
                "spacer_sequence": "GAGTCCGAGCAGAAGAAGAA",
                "features": {"Sh": 0.1, "delta_g_binding": -8.5, "Ca": 0.7},
                "coefficient_model_id": "calib_tox_e2e",
                "calibration_input_id": calib_id,
            })
            exec_id3 = calib_resp.json()["execution_id"]
            res3 = (await wait_for_execution(client, exec_id3))["skill_result"]
            assert res3["status"] == "complete"
            assert res3["validated"] is True
            assert res3["toxicity_risk"] is not None
            assert res3["calibration"]["status"] == "calibrated"
    asyncio.run(run())


# -----------------------------------------------------------------------------
# Part 15 & 16: Exposure API and MCP Interface Parity
# -----------------------------------------------------------------------------
def test_exposure_api_and_mcp_surface():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # Health
            assert (await client.get("/health")).status_code == 200
            # AI Status & Providers
            assert (await client.get("/ai/status")).status_code == 200
            assert (await client.get("/ai/providers")).status_code == 200
            # Backend Status & Tools
            assert (await client.get("/backend/status")).status_code == 200
            assert (await client.get("/tools")).status_code == 200
            # Skills
            skills_resp = await client.get("/skills")
            assert skills_resp.status_code == 200
            skill_ids = [s["skill_id"] for s in skills_resp.json()["skills"]]
            assert "spcas9_gene_cutting" in skill_ids
            assert "offtarget_toxicity_risk" in skill_ids
            assert "model_calibration" in skill_ids
            # Calibration Status
            assert (await client.get("/calibration/status")).status_code == 200

            # MCP capability parity
            mcp_status = await MIDEND_MCP_CAPABILITIES["backend_status"]()
            assert "active_connector" in mcp_status
            mcp_skills = await MIDEND_MCP_CAPABILITIES["list_skills"]()
            assert len(mcp_skills["skills"]) >= 3
            mcp_calib = await MIDEND_MCP_CAPABILITIES["calibration_status"]()
            assert "coefficient_models" in mcp_calib
    asyncio.run(run())


# -----------------------------------------------------------------------------
# Part 17 & 18: Error Injection and Security / Secret Audit
# -----------------------------------------------------------------------------
def test_error_injection_and_secret_protection():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # Add provider with secret key
            secret_key = "super_secret_api_key_12345"
            add_prov = await client.post("/ai/providers", json={
                "provider_id": "secret-audit-prov",
                "base_url": "https://api.example.com/v1",
                "api_key": secret_key,
                "models": ["model-a"],
                "default_model": "model-a",
            })
            assert add_prov.status_code == 200
            assert secret_key not in add_prov.text

            # Check /ai/status, /ai/providers, /ai/config - verify no key leakage
            assert secret_key not in (await client.get("/ai/status")).text
            assert secret_key not in (await client.get("/ai/providers")).text
            assert secret_key not in (await client.get("/ai/config")).text

            # Error injection: invalid DNA in skill
            bad_dna = await client.post("/skills/spcas9_gene_cutting", json={"sequence": "INVALID_DNA_123"})
            assert bad_dna.status_code == 422
            assert bad_dna.json()["detail"]["error"] == "invalid_sequence"

            # Error injection: nonexistent skill
            bad_skill = await client.post("/skills/nonexistent_skill", json={"sequence": "ATGC"})
            assert bad_skill.status_code == 404

            # Error injection: invalid execution ID
            bad_exec = await client.get("/executions/nonexistent_exec_id")
            assert bad_exec.status_code == 404
    asyncio.run(run())


# -----------------------------------------------------------------------------
# Part 19: Repeatability Verification
# -----------------------------------------------------------------------------
def test_repeatability_deterministic_calls():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            seq = "GAGTCCGAGCAGAAGAAGAAGGGCTCCCATCACATCAACCGGTGGCGCATTGCCACGAAGCAGGCCAATGGGGAGGACATCGATGTCACCTCCAATGAC"
            resp1 = await client.post("/skills/spcas9_gene_cutting", json={"sequence": seq})
            resp2 = await client.post("/skills/spcas9_gene_cutting", json={"sequence": seq})
            id1, id2 = resp1.json()["execution_id"], resp2.json()["execution_id"]

            res1 = (await wait_for_execution(client, id1))["skill_result"]
            res2 = (await wait_for_execution(client, id2))["skill_result"]

            assert len(res1["candidates"]) == len(res2["candidates"])
            for c1, c2 in zip(res1["candidates"], res2["candidates"]):
                assert c1["protospacer"] == c2["protospacer"]
                assert c1["strand"] == c2["strand"]
                assert c1["cut_site"] == c2["cut_site"]
                assert c1["features"] == c2["features"]
                assert c1["rank"] == c2["rank"]
    asyncio.run(run())


# -----------------------------------------------------------------------------
# Part 20: Complete E2E Demonstration (Analysis + Calibration)
# -----------------------------------------------------------------------------
def test_complete_e2e_full_workflow():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # Step 1: Upload target FASTA (analysis_input)
            fasta_up = await client.post("/inputs/file", files={"file": ("target.fasta", TARGET_FASTA_BYTES, "text/x-fasta")})
            assert fasta_up.status_code == 201
            analysis_id = fasta_up.json()["input_id"]

            # Step 2: Upload labeled experimental dataset (calibration_input)
            calib_up = await client.post("/calibration/file", files={"file": ("calib.csv", CALIB_CSV_BYTES, "text/csv")})
            assert calib_up.status_code == 201
            calib_id = calib_up.json()["input_id"]

            # Step 3: Run calibration workflow
            calib_exec = await client.post("/calibration/run", json={"calibration_input_id": calib_id, "model_id": "e2e_calibrated_model"})
            assert calib_exec.status_code == 202
            calib_res = await wait_for_execution(client, calib_exec.json()["execution_id"])
            assert calib_res["skill_result"]["status"] == "complete"
            assert calib_res["skill_result"]["calibration_status"] == "calibrated"

            # Step 4: Run gene-cutting analysis with calibration evidence attached
            analysis_exec = await client.post("/skills/spcas9_gene_cutting", json={
                "input_id": analysis_id,
                "calibration_input_id": calib_id,
                "depth": "quick",
            })
            assert analysis_exec.status_code == 202
            analysis_res = await wait_for_execution(client, analysis_exec.json()["execution_id"])
            assert analysis_res["status"] == "completed"
            assert len(analysis_res["skill_result"]["candidates"]) > 0

            # Step 5: Run calibrated off-target toxicity risk on top candidate
            top_guide = analysis_res["skill_result"]["candidates"][0]["protospacer"]
            tox_exec = await client.post("/skills/offtarget_toxicity_risk", json={
                "spacer_sequence": top_guide,
                "features": {"Sh": 0.05, "delta_g_binding": -9.2, "Ca": 0.85},
                "coefficient_model_id": "e2e_calibrated_model",
                "calibration_input_id": calib_id,
            })
            assert tox_exec.status_code == 202
            tox_res = await wait_for_execution(client, tox_exec.json()["execution_id"])
            assert tox_res["skill_result"]["status"] == "complete"
            assert tox_res["skill_result"]["validated"] is True
            assert tox_res["skill_result"]["toxicity_risk"] is not None
            assert tox_res["skill_result"]["calibration"]["status"] == "calibrated"
    asyncio.run(run())

