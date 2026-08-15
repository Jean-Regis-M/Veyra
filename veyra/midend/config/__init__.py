"""Midend configuration package."""

try:
    from .settings import Settings, get_settings
except ImportError:  # pragma: no cover
    from config.settings import Settings, get_settings
from .ai_provider import (
    AIConfigError,
    AIProviderConfig,
    AIProviderConfigManager,
    get_ai_config,
    get_ai_config_manager,
)

__all__ = [
    "Settings", "get_settings",
    "AIConfigError", "AIProviderConfig", "AIProviderConfigManager",
    "get_ai_config", "get_ai_config_manager",
]
