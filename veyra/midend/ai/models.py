"""Data models for AI Provider layer."""

from __future__ import annotations
from typing import Any, AsyncGenerator, Optional
from pydantic import BaseModel, Field


class AIMessage(BaseModel):
    role: str = Field(..., description="'system', 'user', 'assistant', or 'tool'")
    content: Optional[str] = Field(default=None, description="Message text content")
    name: Optional[str] = Field(default=None, description="Function/tool name for tool responses")
    tool_call_id: Optional[str] = Field(default=None, description="ID of the tool call being answered")
    tool_calls: Optional[list[dict[str, Any]]] = Field(default=None, description="Native tool calls emitted by assistant")


class AIRequest(BaseModel):
    messages: list[AIMessage]
    model: Optional[str] = None
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    stream: bool = False
    tools: Optional[list[dict[str, Any]]] = None


class AIResponse(BaseModel):
    content: Optional[str] = ""
    model: str
    provider: str = "openai_compatible"
    tool_calls: Optional[list[dict[str, Any]]] = None
    usage: dict[str, Any] = Field(default_factory=dict)
    finish_reason: Optional[str] = None
    latency_ms: float = 0.0
    request_id: Optional[str] = None
    raw_response: dict[str, Any] = Field(default_factory=dict)


class StreamChunk(BaseModel):
    delta: str
    finish_reason: Optional[str] = None
    request_id: Optional[str] = None
