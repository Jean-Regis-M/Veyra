"""Generic OpenAI-compatible provider; no vendor-specific orchestration logic."""

from __future__ import annotations

import time
from typing import AsyncGenerator, Optional

import httpx

from .errors import AIAuthenticationError, AITimeoutError, AIProviderNotConfiguredError, AIProviderError
from .models import AIMessage, AIResponse, StreamChunk
from ..config.ai_provider import AIProviderConfig, get_ai_config


class OpenAICompatibleProvider:
    provider_name = "openai_compatible"

    def __init__(self, config: AIProviderConfig | None = None):
        self.config = config or get_ai_config()

    def _require_key(self) -> None:
        pass

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key and self.config.api_key.strip():
            headers["Authorization"] = f"Bearer {self.config.api_key.strip()}"
        else:
            try:
                import google.auth
                import google.auth.transport.requests
                creds, _ = google.auth.default()
                req = google.auth.transport.requests.Request()
                creds.refresh(req)
                if creds.token:
                    headers["Authorization"] = f"Bearer {creds.token}"
            except Exception:
                pass
        return headers

    async def generate(self, messages: list[AIMessage], model: Optional[str] = None,
                       temperature: float = 0.0, max_tokens: Optional[int] = None,
                       tools: Optional[list[dict[str, Any]]] = None) -> AIResponse:
        self._require_key()
        started = time.perf_counter()
        
        # Serialize messages, excluding None fields
        serialized_messages = []
        for m in messages:
            dumped = m.model_dump(exclude_none=True)
            # Ensure content is never missing if tool_calls not present
            if "content" not in dumped and "tool_calls" not in dumped:
                dumped["content"] = ""
            serialized_messages.append(dumped)

        payload: dict[str, Any] = {
            "model": model or self.config.model,
            "messages": serialized_messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.config.base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=self._get_headers(),
                )
            if response.status_code in {401, 403}:
                raise AIAuthenticationError("AI provider authentication failed")
            if response.status_code >= 400:
                raise AIProviderError(f"AI provider request failed with status {response.status_code}")
            data = response.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            usage = data.get("usage") or {}
            tool_calls = message.get("tool_calls")
            
            return AIResponse(
                content=message.get("content") or "",
                model=data.get("model", payload["model"]),
                provider=self.provider_name,
                tool_calls=tool_calls,
                usage=usage,
                finish_reason=choice.get("finish_reason"),
                latency_ms=(time.perf_counter() - started) * 1000,
                request_id=data.get("id"),
                raw_response=data,
            )
        except httpx.TimeoutException as exc:
            raise AITimeoutError(60.0) from exc
        except (AIProviderError, AIAuthenticationError, AITimeoutError):
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise AIProviderError("AI provider request failed") from exc

    async def stream(self, messages: list[AIMessage], model: Optional[str] = None,
                     temperature: float = 0.0, max_tokens: Optional[int] = None) -> AsyncGenerator[StreamChunk, None]:
        # Streaming remains intentionally conservative until the service needs it.
        response = await self.generate(messages, model, temperature, max_tokens)
        yield StreamChunk(delta=response.content, request_id=response.request_id)

    async def test(self) -> dict:
        self._require_key()
        started = time.perf_counter()
        response = await self.generate([AIMessage(role="user", content="Reply with OK.")], max_tokens=8)
        return {"success": True, "provider": self.provider_name, "model": response.model,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "request_id": response.request_id, "error": None}
