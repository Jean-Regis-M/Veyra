"""Abstract base class for VEYRA Backend Connectors."""

from abc import ABC, abstractmethod
from typing import Any
try:
    from .models import BackendToolSchema, ToolExecutionResult
except ImportError:  # pragma: no cover
    from connectors.models import BackendToolSchema, ToolExecutionResult


class BackendConnector(ABC):
    """Unified abstraction for VEYRA backend communication."""

    @property
    @abstractmethod
    def connector_type(self) -> str:
        """Returns 'http' or 'mcp'."""
        pass

    @abstractmethod
    async def list_tools(self) -> list[BackendToolSchema]:
        """Discover available tools from the backend."""
        pass

    @abstractmethod
    async def get_tool_schema(self, tool_name: str) -> BackendToolSchema:
        """Get schema and metadata for a specific tool."""
        pass

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict[str, Any], timeout: float | None = None) -> ToolExecutionResult:
        """Execute a backend tool call with arguments and return full VeyraResult structure."""
        pass
