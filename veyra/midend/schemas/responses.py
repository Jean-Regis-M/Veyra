"""Response schemas for Midend API."""

from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "veyra-midend"
    connector: str
    ai_configured: bool
    version: str = "0.1.0"


class ToolInfo(BaseModel):
    name: str
    description: str
    argument_schema: dict[str, Any] = Field(default_factory=dict)
    availability: str = "available"
    connector_source: str = "backend"
    tier: Optional[int] = None
    cost: Optional[str] = None


class ToolsListResponse(BaseModel):
    total_tools: int
    connector: str
    tools: list[ToolInfo]


class ExecutionResponse(BaseModel):
    execution_id: str
    status: str
    created_at: str


class ExecutionStatusResponse(BaseModel):
    execution_id: str
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    completed_calls: int = 0
    active_calls: int = 0
    failed_calls: int = 0
    elapsed_ms: float = 0.0
    results: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class AIChatResponse(BaseModel):
    execution_id: str
    status: str
    output: Optional[str] = None
    latency_ms: Optional[float] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    request_id: Optional[str] = None
