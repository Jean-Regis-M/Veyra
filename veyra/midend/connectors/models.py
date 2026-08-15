"""Data models for connector layer."""

from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


class BackendToolSchema(BaseModel):
    name: str
    description: str
    argument_schema: dict[str, Any] = Field(default_factory=dict)
    availability: str = "available"
    connector_source: str = "http"
    tier: Optional[int] = None
    cost: Optional[str] = None


class ToolExecutionResult(BaseModel):
    tool: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_response: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "rows": self.rows,
            "summary": self.summary,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }
