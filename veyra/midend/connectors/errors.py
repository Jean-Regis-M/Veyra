"""Connector exception hierarchy for VEYRA Midend."""

class ConnectorError(Exception):
    """Base exception for all connector errors."""
    pass


class ToolNotFoundError(ConnectorError):
    """Raised when a requested tool is not found on the backend."""
    def __init__(self, tool_name: str, connector_type: str = "backend"):
        self.tool_name = tool_name
        self.connector_type = connector_type
        super().__init__(f"Tool '{tool_name}' not found on {connector_type} backend")


class ToolExecutionError(ConnectorError):
    """Raised when tool execution fails on the backend."""
    def __init__(self, tool_name: str, message: str, raw_result: dict = None):
        self.tool_name = tool_name
        self.message = message
        self.raw_result = raw_result or {}
        super().__init__(f"Execution of tool '{tool_name}' failed: {message}")


class ConnectorTimeoutError(ConnectorError):
    """Raised when connector request times out."""
    def __init__(self, tool_name: str, timeout: float):
        self.tool_name = tool_name
        self.timeout = timeout
        super().__init__(f"Call to tool '{tool_name}' timed out after {timeout} seconds")
