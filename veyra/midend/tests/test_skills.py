import asyncio

import httpx

from veyra.midend.connectors.models import BackendToolSchema, ToolExecutionResult
from veyra.midend.control_plane import control_plane
from veyra.midend.http_api.app import app


class SkillFakeConnector:
    connector_type = "http"
    base_url = "http://fake"

    async def list_tools(self):
        return [BackendToolSchema(name="pam_scan", description="fake", connector_source="http")]

    async def call_tool(self, tool_name, arguments):
        if tool_name == "genome_info":
            return ToolExecutionResult(tool=tool_name, summary={"genome_id": arguments["genome_id"]})
        if tool_name == "pam_scan":
            return ToolExecutionResult(tool=tool_name, rows=[{
                "chrom": None, "start": 7, "end": 10, "strand": "-",
                "protospacer": "CTAGCCTACGGATCAGCCTC", "pam": "AGG", "pam_type": "SpCas9",
            }], summary={"total_sites": 1})
        if tool_name == "compute_cut_site":
            return ToolExecutionResult(tool=tool_name, summary={"cut_site_relative": 17, "cut_site_genomic": None})
        if tool_name == "rank_candidates":
            return ToolExecutionResult(tool=tool_name, rows=arguments["guides"])
        return ToolExecutionResult(tool=tool_name, summary={"ok": True})


def test_skill_discovery_and_metadata():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            listing = await client.get("/skills")
            assert listing.status_code == 200
            assert listing.json()["skills"][0]["skill_id"] == "spcas9_gene_cutting"
            detail = await client.get("/skills/spcas9_gene_cutting")
            assert detail.status_code == 200
            assert "pam_scan" in detail.json()["allowed_tools"]
    asyncio.run(run())


def test_skill_execution_preserves_reverse_candidate_and_events(monkeypatch):
    async def run():
        monkeypatch.setattr("veyra.midend.control_plane.get_backend_connector", lambda *_args, **_kwargs: SkillFakeConnector())
        control_plane.active_connector = "http"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/skills/spcas9_gene_cutting", json={
                "sequence": "ACGTGACCTGAGGCTGATCCGTAGGCTAGCTAGG",
            })
            assert response.status_code == 202
            execution_id = response.json()["execution_id"]
            await asyncio.sleep(0.05)
            execution = (await client.get(f"/executions/{execution_id}")).json()
            assert execution["status"] == "completed"
            candidate = execution["skill_result"]["candidates"][0]
            assert candidate["strand"] == "-"
            assert candidate["protospacer"] == "CTAGCCTACGGATCAGCCTC"
            assert candidate["cut_site"]["relative"] == 17
            assert "cut=" in candidate["cutting_site_string"]
            stream = await client.get(f"/executions/{execution_id}/stream")
            assert "skill_started" in stream.text
            assert "candidate_evaluated" in stream.text
    asyncio.run(run())


def test_skill_rejects_invalid_input_before_execution():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/skills/spcas9_gene_cutting", json={"sequence": ""})
            assert response.status_code == 422
            assert response.json()["detail"]["error"] == "empty_sequence"
    asyncio.run(run())
