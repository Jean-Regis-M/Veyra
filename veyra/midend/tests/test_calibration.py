import asyncio
import httpx
import pytest

from veyra.midend.connectors.models import BackendToolSchema, ToolExecutionResult
from veyra.midend.control_plane import control_plane
from veyra.midend.http_api.app import app
from veyra.midend.input_validation import MIDENDInputError, validate_calibration_file, validate_input_file
from veyra.midend.mcp_interface import MIDEND_MCP_CAPABILITIES


VALID_CALIBRATION_CSV = b"""guide,target,sh,delta_g_binding,ca
CTAGCCTACGGATCAGCCTC,15.2,0.1,-8.5,0.7
GTCAGTCAGTCAGTCAGTCA,85.0,0.8,-2.1,0.2
ATCGATCGATCGATCGATCG,45.6,0.4,-5.2,0.5
"""

VALID_CALIBRATION_TSV = b"""guide\ttarget\tsh\tdelta_g_binding\tca
CTAGCCTACGGATCAGCCTC\t15.2\t0.1\t-8.5\t0.7
GTCAGTCAGTCAGTCAGTCA\t85.0\t0.8\t-2.1\t0.2
ATCGATCGATCGATCGATCG\t45.6\t0.4\t-5.2\t0.5
"""


class FakeBackendConnector:
    connector_type = "http"
    base_url = "http://fake"

    async def list_tools(self):
        return [
            BackendToolSchema(name="pam_scan", description="fake", connector_source="http"),
            BackendToolSchema(name="compute_cut_site", description="fake", connector_source="http"),
            BackendToolSchema(name="compute_gc_content", description="fake", connector_source="http"),
            BackendToolSchema(name="rank_candidates", description="fake", connector_source="http"),
        ]

    async def call_tool(self, tool_name, arguments):
        if tool_name == "pam_scan":
            return ToolExecutionResult(tool=tool_name, rows=[{
                "chrom": None, "start": 7, "end": 10, "strand": "+",
                "protospacer": "CTAGCCTACGGATCAGCCTC", "pam": "TGG", "pam_type": "SpCas9",
            }], summary={"total_sites": 1})
        if tool_name == "compute_cut_site":
            return ToolExecutionResult(tool=tool_name, summary={"cut_site_relative": 17, "cut_site_genomic": None})
        if tool_name == "compute_gc_content":
            return ToolExecutionResult(tool=tool_name, summary={"gc_content": 0.55})
        if tool_name == "rank_candidates":
            return ToolExecutionResult(tool=tool_name, rows=arguments.get("guides", []))
        return ToolExecutionResult(tool=tool_name, summary={"ok": True})


def test_calibration_direct_validation():
    # Valid CSV
    csv_item = validate_calibration_file("calib.csv", VALID_CALIBRATION_CSV)
    assert csv_item.input_class == "calibration_input"
    assert csv_item.detected_format == "csv"
    assert csv_item.column_count == 5
    assert csv_item.row_count == 3
    assert csv_item.columns == ["guide", "target", "sh", "delta_g_binding", "ca"]
    assert csv_item.calibration_status == "uncalibrated"

    # Valid TSV
    tsv_item = validate_calibration_file("calib.tsv", VALID_CALIBRATION_TSV)
    assert tsv_item.input_class == "calibration_input"
    assert tsv_item.detected_format == "tsv"
    assert tsv_item.column_count == 5
    assert tsv_item.row_count == 3

    # Empty file
    with pytest.raises(MIDENDInputError) as exc_empty:
        validate_calibration_file("empty.csv", b"")
    assert exc_empty.value.error == "empty_file"

    # Header only / empty dataset
    with pytest.raises(MIDENDInputError) as exc_hdr:
        validate_calibration_file("header_only.csv", b"guide,target,sh\n")
    assert exc_hdr.value.error == "empty_dataset"

    # Inconsistent columns
    with pytest.raises(MIDENDInputError) as exc_inconsistent:
        validate_calibration_file("bad.csv", b"guide,target,sh\nACTG,12.0\n")
    assert exc_inconsistent.value.error == "inconsistent_columns"

    # Unsupported format
    with pytest.raises(MIDENDInputError) as exc_unsupported:
        validate_calibration_file("bad.xlsx", b"some binary data")
    assert exc_unsupported.value.error == "unsupported_calibration_format"

    # Mismatched delimiter: CSV extension with TSV content
    with pytest.raises(MIDENDInputError) as exc_mismatch:
        validate_calibration_file("mismatch.csv", b"guide\ttarget\tsh\nACTG\t1.0\t0.5\n")
    assert exc_mismatch.value.error == "mismatched_file_format"


def test_calibration_endpoints_and_status():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # Upload CSV via /calibration/file
            upload_resp = await client.post("/calibration/file", files={
                "file": ("dataset.csv", VALID_CALIBRATION_CSV, "text/csv")
            })
            assert upload_resp.status_code == 201
            metadata = upload_resp.json()
            calib_id = metadata["input_id"]
            assert metadata["input_class"] == "calibration_input"
            assert metadata["columns"] == ["guide", "target", "sh", "delta_g_binding", "ca"]
            assert metadata["sample_count"] == 3

            # Inspect dataset metadata
            get_resp = await client.get(f"/calibration/{calib_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["input_id"] == calib_id

            # Inspect calibration status
            status_resp = await client.get("/calibration/status")
            assert status_resp.status_code == 200
            assert status_resp.json()["registered_datasets_count"] >= 1

            # Reject invalid calibration attachment
            bad_get = await client.get("/calibration/non_existent_id")
            assert bad_get.status_code == 400
            assert bad_get.json()["error"] == "unknown_calibration_input"
    asyncio.run(run())


def test_calibration_only_workflow_without_gene(monkeypatch):
    async def run():
        monkeypatch.setattr("veyra.midend.control_plane.get_backend_connector", lambda *_args, **_kwargs: FakeBackendConnector())
        control_plane.active_connector = "http"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # Register calibration dataset
            upload_resp = await client.post("/inputs/file", files={
                "file": ("experiment.tsv", VALID_CALIBRATION_TSV, "text/tab-separated-values")
            })
            assert upload_resp.status_code == 201
            calib_id = upload_resp.json()["input_id"]

            # Run calibration explicitly without any analysis gene
            run_resp = await client.post("/calibration/run", json={
                "calibration_input_id": calib_id,
            })
            assert run_resp.status_code == 202
            exec_id = run_resp.json()["execution_id"]

            await asyncio.sleep(0.05)
            exec_status = (await client.get(f"/executions/{exec_id}")).json()
            assert exec_status["status"] == "completed"
            skill_result = exec_status["skill_result"]
            assert skill_result["status"] == "complete"
            assert skill_result["calibration_status"] == "calibrated"
            assert "r2" in skill_result["metrics"]
            assert "mse" in skill_result["metrics"]
            assert skill_result["fitted_coefficients"]["alpha"] is not None
            assert skill_result["sample_count"] == 3
            assert skill_result["ai_review_summary"]["sample_count"] == 3
    asyncio.run(run())


def test_normal_analysis_without_calibration_works(monkeypatch):
    async def run():
        monkeypatch.setattr("veyra.midend.control_plane.get_backend_connector", lambda *_args, **_kwargs: FakeBackendConnector())
        control_plane.active_connector = "http"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # SpCas9 gene cutting with FASTA upload only (no calibration)
            fasta_upload = await client.post("/inputs/file", files={
                "file": ("target.fasta", b">seq1\nACGTGACCTGAGGCTGATCCGTAGGCTAGCTAGG\n", "text/x-fasta")
            })
            assert fasta_upload.status_code == 201
            input_id = fasta_upload.json()["input_id"]

            skill_resp = await client.post("/skills/spcas9_gene_cutting", json={
                "input_id": input_id,
            })
            assert skill_resp.status_code == 202
            exec_id = skill_resp.json()["execution_id"]

            await asyncio.sleep(0.05)
            exec_status = (await client.get(f"/executions/{exec_id}")).json()
            assert exec_status["status"] == "completed"
            assert len(exec_status["skill_result"]["candidates"]) > 0
            assert exec_status["calibration_status"] == "not_provided"
            assert exec_status["calibration_input"] is None
    asyncio.run(run())


def test_normal_analysis_with_calibration_attached(monkeypatch):
    async def run():
        monkeypatch.setattr("veyra.midend.control_plane.get_backend_connector", lambda *_args, **_kwargs: FakeBackendConnector())
        control_plane.active_connector = "http"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # Upload analysis FASTA
            fasta_upload = await client.post("/inputs/file", files={
                "file": ("target.fasta", b">seq1\nACGTGACCTGAGGCTGATCCGTAGGCTAGCTAGG\n", "text/x-fasta")
            })
            analysis_id = fasta_upload.json()["input_id"]

            # Upload calibration CSV
            calib_upload = await client.post("/calibration/file", files={
                "file": ("calib.csv", VALID_CALIBRATION_CSV, "text/csv")
            })
            calib_id = calib_upload.json()["input_id"]

            # Run SpCas9 skill with both analysis_input and calibration_input
            exec_resp = await client.post("/skills/spcas9_gene_cutting", json={
                "input_id": analysis_id,
                "calibration_input_id": calib_id,
            })
            assert exec_resp.status_code == 202
            exec_id = exec_resp.json()["execution_id"]

            await asyncio.sleep(0.05)
            exec_status = (await client.get(f"/executions/{exec_id}")).json()
            assert exec_status["status"] == "completed"
            assert exec_status["analysis_input"]["input_id"] == analysis_id
            assert exec_status["calibration_input"]["input_id"] == calib_id
            assert exec_status["calibration_status"] in {"uncalibrated", "user_supplied", "calibrated"}
    asyncio.run(run())


def test_invalid_calibration_attachment_rejected(monkeypatch):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # Upload FASTA
            fasta_upload = await client.post("/inputs/file", files={
                "file": ("target.fasta", b">seq1\nACGTACGTACGT\n", "text/x-fasta")
            })
            analysis_id = fasta_upload.json()["input_id"]

            # Attempt to attach FASTA as calibration_input_id
            resp = await client.post("/skills/spcas9_gene_cutting", json={
                "sequence": "ACGTGACCTGAGGCTGATCCGTAGGCTAGCTAGG",
                "calibration_input_id": analysis_id,
            })
            assert resp.status_code == 400
            assert resp.json()["error"] == "invalid_input_class"
    asyncio.run(run())


def test_mcp_calibration_parity():
    async def run():
        # Test calibration status MCP tool
        status_func = MIDEND_MCP_CAPABILITIES["calibration_status"]
        status = await status_func()
        assert "registered_datasets_count" in status
        assert "coefficient_models" in status

        # Test list calibration datasets MCP tool
        list_func = MIDEND_MCP_CAPABILITIES["list_calibration_datasets"]
        datasets = await list_func()
        assert "calibration_datasets" in datasets
    asyncio.run(run())
