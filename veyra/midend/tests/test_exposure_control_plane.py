import asyncio

import httpx

from veyra.midend.connectors.models import BackendToolSchema, ToolExecutionResult
from veyra.midend.http_api.app import app
from veyra.midend.control_plane import control_plane


class FakeConnector:
    connector_type = "http"
    base_url = "http://fake"

    async def list_tools(self):
        return [BackendToolSchema(name="fake_tool", description="fake", connector_source="http", tier=1)]

    async def call_tool(self, tool_name, arguments):
        return ToolExecutionResult(tool=tool_name, rows=[{"value": 1}], summary={"ok": True}, metadata={"source": "fake"})


def test_public_provider_conversation_and_execution(monkeypatch):
    async def run():
        monkeypatch.setattr("veyra.midend.control_plane.get_backend_connector", lambda *_args, **_kwargs: FakeConnector())
        control_plane.active_connector = "http"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            added = await client.post("/ai/providers", json={
                "provider_id": "public-test", "base_url": "https://example.com/v1",
                "api_key": "never-return-this", "models": ["a", "b"], "default_model": "a",
            })
            assert added.status_code == 200
            assert "never-return-this" not in added.text
            selected = await client.post("/ai/active", json={"provider_id": "public-test", "model": "b"})
            assert selected.json()["model"] == "b"
            tools = await client.get("/tools")
            assert tools.json()["tools"][0]["name"] == "fake_tool"
            created = await client.post("/executions", json={"tool_calls": [
                {"tool": "fake_tool", "arguments": {"sequence": "ACGT"}}
            ]})
            execution_id = created.json()["execution_id"]
            await asyncio.sleep(0.03)
            execution = (await client.get(f"/executions/{execution_id}")).json()
            assert execution["status"] == "completed"
            assert execution["tool_calls"][0]["duration_ms"] >= 0
            assert execution["tool_calls"][0]["result"]["rows"] == [{"value": 1}]
            stream = await client.get(f"/executions/{execution_id}/stream")
            assert "tool_call_completed" in stream.text

            conversation = (await client.post("/conversations")).json()
            cid = conversation["conversation_id"]
            appended = await client.post(f"/conversations/{cid}/messages",
                                          json={"role": "user", "content": "hello"})
            assert appended.json()["messages"][0]["content"] == "hello"
    asyncio.run(run())


def test_plaintext_provider_persistence_rejected():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/ai/providers", json={
                "provider_id": "persist-test", "base_url": "https://example.com/v1",
                "api_key": "secret", "models": ["a"], "default_model": "a", "persist": True,
            })
            assert response.status_code == 422
            assert "secret" not in response.text
    asyncio.run(run())
