"""MCP Backend Connector for VEYRA MCP Tool Registry."""

from __future__ import annotations
import asyncio
import os
import sys
from typing import Any, Optional
try:
    from ..config.settings import get_settings
    from .base import BackendConnector
    from .errors import ToolNotFoundError, ToolExecutionError, ConnectorTimeoutError
    from .models import BackendToolSchema, ToolExecutionResult
except ImportError:  # pragma: no cover
    from config.settings import get_settings
    from connectors.base import BackendConnector
    from connectors.errors import ToolNotFoundError, ToolExecutionError, ConnectorTimeoutError
    from connectors.models import BackendToolSchema, ToolExecutionResult

# Ensure backend directory is in sys.path for direct import of VEYRA mcp.server
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


class MCPBackendConnector(BackendConnector):
    """MCP-based connector executing tools via VEYRA MCP registry."""

    def __init__(self, timeout: Optional[float] = None):
        settings = get_settings()
        self.timeout = timeout or settings.midend_mcp_timeout
        self._registry = self._load_registry()

    def _load_registry(self) -> dict[str, dict]:
        try:
            from mcp.server import TOOL_REGISTRY
            return TOOL_REGISTRY
        except ImportError as e:
            # Provide mock registry fallback if backend dependencies missing
            return {}

    @property
    def connector_type(self) -> str:
        return "mcp"

    async def list_tools(self) -> list[BackendToolSchema]:
        schemas = []
        for name, info in self._registry.items():
            schemas.append(
                BackendToolSchema(
                    name=name,
                    description=info.get("description", ""),
                    argument_schema={},
                    availability="available",
                    connector_source="mcp",
                    tier=info.get("tier"),
                    cost=info.get("cost"),
                )
            )
        return schemas

    async def get_tool_schema(self, tool_name: str) -> BackendToolSchema:
        if tool_name not in self._registry:
            raise ToolNotFoundError(tool_name, "mcp")
        info = self._registry[tool_name]
        return BackendToolSchema(
            name=tool_name,
            description=info.get("description", ""),
            argument_schema={},
            availability="available",
            connector_source="mcp",
            tier=info.get("tier"),
            cost=info.get("cost"),
        )

    def _execute_sync(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        if tool_name not in self._registry:
            raise ToolNotFoundError(tool_name, "mcp")

        func = self._registry[tool_name]["function"]
        try:
            res = func(**arguments)
            
            # Convert VeyraResult to dict structure
            tool_res_name = getattr(res, "tool", tool_name)
            raw_rows = getattr(res, "rows", [])
            rows_dict = []
            for r in raw_rows:
                if hasattr(r, "to_dict"):
                    rows_dict.append(r.to_dict())
                elif isinstance(r, dict):
                    rows_dict.append(r)
                else:
                    rows_dict.append(dict(r))

            summary = getattr(res, "summary", {})
            errors = getattr(res, "errors", [])
            warnings = getattr(res, "warnings", [])
            metadata = getattr(res, "metadata", {})

            return ToolExecutionResult(
                tool=tool_res_name,
                rows=rows_dict,
                summary=summary if isinstance(summary, dict) else {"raw": summary},
                errors=errors or [],
                warnings=warnings or [],
                metadata=metadata if isinstance(metadata, dict) else {},
                raw_response={
                    "tool": tool_res_name,
                    "rows": rows_dict,
                    "summary": summary,
                    "errors": errors,
                    "warnings": warnings,
                    "metadata": metadata,
                },
            )
        except TypeError as e:
            return ToolExecutionResult(
                tool=tool_name,
                rows=[],
                summary={},
                errors=[f"Invalid arguments for tool '{tool_name}': {e}"],
                warnings=[],
                metadata={},
                raw_response={"error": str(e)},
            )
        except Exception as e:
            return ToolExecutionResult(
                tool=tool_name,
                rows=[],
                summary={},
                errors=[f"MCP tool execution failed: {e}"],
                warnings=[],
                metadata={},
                raw_response={"error": str(e)},
            )

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        if tool_name not in self._registry:
            raise ToolNotFoundError(tool_name, "mcp")

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self._execute_sync, tool_name, arguments),
                timeout=self.timeout,
            )
            return result
        except asyncio.TimeoutError:
            raise ConnectorTimeoutError(tool_name, self.timeout)
