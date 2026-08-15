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


def test_startup_without_key_and_safe_status(api_client):
    async def run():
        from veyra.midend.config.ai_provider import get_ai_config_manager
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
