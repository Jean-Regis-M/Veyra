"""Data models for AI Provider layer."""

from __future__ import annotations
from typing import Any, AsyncGenerator, Optional
from pydantic import BaseModel, Field


class AIMessage(BaseModel):
    role: str = Field(..., description="'system', 'user', or 'assistant'")
    content: str = Field(..., description="Message text content")


class AIRequest(BaseModel):
    messages: list[AIMessage]
    model: Optional[str] = None
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    stream: bool = False


class AIResponse(BaseModel):
    content: str
    model: str
    provider: str = "openai_compatible"
    # OpenAI-compatible providers may add nested usage metadata and strings
    # such as service_tier; preserve it without exposing credentials.
    usage: dict[str, Any] = Field(default_factory=dict)
    finish_reason: Optional[str] = None
    latency_ms: float = 0.0
    request_id: Optional[str] = None
    raw_response: dict[str, Any] = Field(default_factory=dict)


class StreamChunk(BaseModel):
    delta: str
    finish_reason: Optional[str] = None
    request_id: Optional[str] = None
