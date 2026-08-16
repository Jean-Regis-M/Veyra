import json
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from veyra.midend.ai.models import AIMessage
from veyra.midend.ai.openai_compatible import OpenAICompatibleProvider
from veyra.midend.config.ai_provider import AIProviderConfigManager
from veyra.midend.http_api.app import app
from veyra.midend.cli.main import main


@pytest.fixture
def api_client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def test_startup_without_key_and_safe_status(api_client, monkeypatch, tmp_path):
    async def run():
        monkeypatch.delenv("MIDEND_AI_API_KEY", raising=False)
        from veyra.midend.config.ai_provider import get_ai_config_manager
        monkeypatch.setattr(get_ai_config_manager(), "env_file", tmp_path / "empty.env")
        get_ai_config_manager().clear_runtime()
        async with api_client as client:
            response = await client.get("/ai/config")
            assert response.json()["configured"] is False
            assert "api_key" not in response.json() or response.json()["api_key"] is None
            chat = await client.post("/ai/chat", json={"message": "hello"})
            assert chat.status_code == 200
            assert chat.json()["status"] == "started"
    asyncio.run(run())


def test_runtime_precedence_and_restricted_dotenv(tmp_path: Path):
    manager = AIProviderConfigManager(tmp_path / ".env")
    manager.configure(base_url="https://example.com/v1", api_key="secret", model="m")
    assert manager.get().source == "runtime"
    assert not (tmp_path / ".env").exists()


def test_cli_status_does_not_print_secret(capsys):
    from veyra.midend.config.ai_provider import get_ai_config_manager
    get_ai_config_manager().clear_runtime()
    assert main(["ai", "status"]) == 0
    output = capsys.readouterr().out
    assert "api_key" not in output


def test_configured_provider_call_is_measured():
    async def run():
        config = AIProviderConfigManager().configure(
            base_url="https://example.com/v1", api_key="secret", model="model"
        )
        fake = MagicMock()
        fake.status_code = 200
        fake.json.return_value = {"id": "req", "model": "model", "choices": [
            {"message": {"content": "OK"}, "finish_reason": "stop"}
        ]}
        with patch("httpx.AsyncClient") as client_cls:
            client = client_cls.return_value
            client.__aenter__.return_value = client
            client.post = AsyncMock(return_value=fake)
            response = await OpenAICompatibleProvider(config).generate([AIMessage(role="user", content="x")])
        assert response.content == "OK"
        assert response.latency_ms >= 0
        assert "secret" not in response.model_dump_json()
    asyncio.run(run())


def test_multi_turn_native_tool_loop_with_evidence():
    from veyra.midend.control_plane import control_plane
    from veyra.midend.config.ai_provider import get_ai_config_manager
    from veyra.midend.ai.models import AIResponse

    async def run():
        get_ai_config_manager().configure(
            base_url="https://example.com/v1", api_key="secret_test_key", model="model"
        )
        try:
            control_plane.providers.add(
                provider_id="test_provider", provider_type="openai_compatible",
                base_url="https://example.com/v1", api_key="secret_test_key",
                models=["model"], default_model="model",
            )
        except Exception:
            pass
        control_plane.providers.select("test_provider", "model")

        # Mock provider multi-turn response: Turn 1 triggers tool_call 'pam_scan', Turn 2 gives final explanation
        turn1_resp = AIResponse(
            content=None,
            model="model",
            finish_reason="tool_calls",
            tool_calls=[{
                "id": "call_pam_123",
                "type": "function",
                "function": {
                    "name": "pam_scan",
                    "arguments": json.dumps({"sequence": "ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCG"}),
                },
            }],
            usage={"prompt_tokens": 350, "completion_tokens": 40, "total_tokens": 390},
        )

        turn2_resp = AIResponse(
            content="I scanned the sequence and identified 3 candidate SpCas9 target sites.",
            model="model",
            finish_reason="stop",
            tool_calls=None,
            usage={"prompt_tokens": 420, "completion_tokens": 35, "total_tokens": 455},
        )

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[turn1_resp, turn2_resp])):
            exec_state = control_plane.create_execution({
                "ai_request": {"message": "Find SpCas9 PAM sites in ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCG"},
            })

            # Wait for execution to finish
            for _ in range(50):
                if exec_state.status in {"completed", "failed"}:
                    break
                await asyncio.sleep(0.05)

            if exec_state.status == "failed":
                print("EXECUTION ERRORS:", exec_state.errors)
            assert exec_state.status == "completed"
            assert "identified 3 candidate" in (exec_state.assistant_output or "")
            assert len(exec_state.tool_calls) == 1
            assert exec_state.tool_calls[0].tool == "pam_scan"
            assert exec_state.tool_calls[0].status == "completed"

    asyncio.run(run())

