"""Abstract base class for VEYRA Backend Connectors."""

from abc import ABC, abstractmethod
from typing import Any
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
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        """Execute a backend tool call with arguments and return full VeyraResult structure."""
        pass
