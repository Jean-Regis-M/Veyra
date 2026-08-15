"""Request schemas for Midend API."""

from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


class ToolCallRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the backend tool to invoke")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    call_id: Optional[str] = Field(default=None, description="Optional caller-supplied unique call ID")


class ParallelToolGroupRequest(BaseModel):
    group_id: Optional[str] = Field(default=None, description="Optional group ID")
    calls: list[ToolCallRequest] = Field(..., description="List of tool calls to execute in parallel")


class ExecutionCreateRequest(BaseModel):
    tool_calls: Optional[list[ToolCallRequest]] = Field(default=None, description="Sequential tool calls")
    parallel_groups: Optional[list[ParallelToolGroupRequest]] = Field(default=None, description="Parallel tool groups")
    ai_request: Optional[dict[str, Any]] = Field(default=None, description="Optional AI request specification")
    connector: Optional[str] = Field(default=None, description="Override backend connector ('http' or 'mcp')")


class AIChatRequest(BaseModel):
    message: str = Field(..., description="User message or prompt for AI")
    conversation_id: Optional[str] = Field(default=None, description="Conversation identifier")
    model: Optional[str] = Field(default=None, description="Model identifier override")
    backend_connector: Optional[str] = Field(default=None, description="Backend connector type override ('http' or 'mcp')")
    stream: bool = Field(default=False, description="Whether to stream response")
