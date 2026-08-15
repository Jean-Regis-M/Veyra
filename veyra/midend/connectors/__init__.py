"""VEYRA Midend Connectors Package."""

from typing import Optional
try:
    from ..config.settings import get_settings
    from .base import BackendConnector
    from .http_backend import HTTPBackendConnector
    from .mcp_backend import MCPBackendConnector
    from .models import BackendToolSchema, ToolExecutionResult
    from .errors import ConnectorError, ToolNotFoundError, ToolExecutionError, ConnectorTimeoutError
except ImportError:  # pragma: no cover
    from config.settings import get_settings
    from connectors.base import BackendConnector
    from connectors.http_backend import HTTPBackendConnector
    from connectors.mcp_backend import MCPBackendConnector
    from connectors.models import BackendToolSchema, ToolExecutionResult
    from connectors.errors import ConnectorError, ToolNotFoundError, ToolExecutionError, ConnectorTimeoutError


def get_backend_connector(
    connector_type: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> BackendConnector:
    """Factory function to get appropriate BackendConnector based on configuration or argument."""
    settings = get_settings()
    c_type = (connector_type or settings.midend_backend_connector).lower()

    if c_type == "mcp":
        return MCPBackendConnector(timeout=timeout)
    elif c_type == "http":
        return HTTPBackendConnector(base_url=base_url, timeout=timeout)
    else:
        raise ValueError(f"Unknown connector type: '{c_type}'. Supported: 'http', 'mcp'")


__all__ = [
    "BackendConnector",
    "HTTPBackendConnector",
    "MCPBackendConnector",
    "BackendToolSchema",
    "ToolExecutionResult",
    "ConnectorError",
    "ToolNotFoundError",
    "ToolExecutionError",
    "ConnectorTimeoutError",
    "get_backend_connector",
]
