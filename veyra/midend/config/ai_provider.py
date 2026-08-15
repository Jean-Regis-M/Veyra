"""Runtime configuration for the optional OpenAI-compatible AI provider."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_BASE_URL = "https://api.llm7.io/v1"
DEFAULT_MODEL = "default"
ENV_BASE_URL = "MIDEND_AI_BASE_URL"
ENV_API_KEY = "MIDEND_AI_API_KEY"
ENV_MODEL = "MIDEND_AI_MODEL"


class AIConfigError(ValueError):
    """Raised when user-supplied provider configuration is invalid."""


@dataclass(frozen=True)
class AIProviderConfig:
    base_url: str = DEFAULT_BASE_URL
    api_key: str | None = None
    model: str = DEFAULT_MODEL
    source: str = "default"
    provider: str = "openai_compatible"

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "configured": self.configured,
            "source": self.source,
            "api_key_configured": self.configured,
        }


def validate_config(base_url: str, api_key: str | None, model: str) -> None:
    parsed = urlparse((base_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AIConfigError("base_url must be a valid HTTP or HTTPS URL")
    if not (model or "").strip():
        raise AIConfigError("model must be non-empty")
    # Empty keys are allowed at startup, but not by an explicit configuration call.
    if api_key is not None and not api_key.strip():
        raise AIConfigError("api_key must be non-empty when supplied")


def _dotenv_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


class AIProviderConfigManager:
    """Process-local configuration with runtime > environment > defaults precedence."""

    def __init__(self, env_file: str | Path | None = None):
        self.env_file = Path(env_file) if env_file else Path(__file__).resolve().parents[1] / ".env"
        self._runtime: AIProviderConfig | None = None

    def get(self) -> AIProviderConfig:
        if self._runtime is not None:
            return self._runtime
        dotenv = _dotenv_values(self.env_file)
        base_url = os.getenv(ENV_BASE_URL, dotenv.get(ENV_BASE_URL, DEFAULT_BASE_URL)).strip()
        model = os.getenv(ENV_MODEL, dotenv.get(ENV_MODEL, DEFAULT_MODEL)).strip()
        api_key = os.getenv(ENV_API_KEY, dotenv.get(ENV_API_KEY, "")).strip() or None
        # Invalid environment values should make status useful without preventing startup.
        try:
            validate_config(base_url, api_key, model)
        except AIConfigError:
            base_url = DEFAULT_BASE_URL
            model = DEFAULT_MODEL
            api_key = None
        source = "environment" if any(
            os.getenv(k) or dotenv.get(k) for k in (ENV_BASE_URL, ENV_API_KEY, ENV_MODEL)
        ) else "default"
        return AIProviderConfig(base_url, api_key, model, source=source)

    def configure(self, *, base_url: str, api_key: str, model: str, persist: bool = False) -> AIProviderConfig:
        if persist:
            raise AIConfigError("plaintext API-key persistence is disabled")
        base_url, model, api_key = base_url.strip(), model.strip(), api_key.strip()
        validate_config(base_url, api_key, model)
        self._runtime = AIProviderConfig(base_url, api_key, model, source="runtime")
        if persist:
            self.save_dotenv(self._runtime)
        return self._runtime

    def save_dotenv(self, config: AIProviderConfig) -> None:
        """Reject plaintext secret persistence; use deployment secret storage instead."""
        raise AIConfigError("plaintext API-key persistence is disabled")

    def clear_runtime(self) -> None:
        self._runtime = None


_manager = AIProviderConfigManager()


def get_ai_config() -> AIProviderConfig:
    return _manager.get()


def get_ai_config_manager() -> AIProviderConfigManager:
    return _manager
