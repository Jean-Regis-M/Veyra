"""Event schemas for Midend live telemetry and streaming."""

from __future__ import annotations
import time
from typing import Any, Optional
from pydantic import BaseModel, Field


class TelemetryEvent(BaseModel):
    event: str = Field(..., description="Event type string, e.g. tool_call_completed")
    execution_id: str = Field(..., description="Execution identifier")
    call_id: Optional[str] = Field(default=None, description="Tool call identifier")
    group_id: Optional[str] = Field(default=None, description="Parallel group identifier")
    request_id: Optional[str] = Field(default=None, description="AI request identifier")
    tool: Optional[str] = Field(default=None, description="Tool name")
    connector: Optional[str] = Field(default=None, description="Connector type ('http' or 'mcp')")
    started_at: Optional[str] = Field(default=None, description="ISO timestamp of start")
    finished_at: Optional[str] = Field(default=None, description="ISO timestamp of finish")
    duration_ms: Optional[float] = Field(default=None, description="Duration in milliseconds")
    success: Optional[bool] = Field(default=None, description="Whether operation succeeded")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    output: Optional[Any] = Field(default=None, description="Output result summary or content")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Additional metadata")
    timestamp: float = Field(default_factory=time.time, description="Epoch timestamp")

    def to_dict(self) -> dict[str, Any]:
        d = self.model_dump(exclude_none=True)
        return d
