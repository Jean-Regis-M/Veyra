"""Base contracts for MIDEND skills.

Skills describe orchestration policy and delegate all domain calculations to
the backend connector supplied by the control plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


class SkillError(ValueError):
    def __init__(self, code: str, message: str, field: str | None = None):
        self.code = code
        self.message = message
        self.field = field
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        result = {"error": self.code, "message": self.message}
        if self.field:
            result["field"] = self.field
        return result


@dataclass(frozen=True)
class SkillMetadata:
    skill_id: str
    name: str
    description: str
    version: str
    required_inputs: list[dict[str, Any]]
    optional_inputs: list[dict[str, Any]]
    allowed_tools: list[str]
    workflow: list[str]
    output_schema: dict[str, Any]
    validation_rules: list[str]

    def public(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "required_inputs": self.required_inputs,
            "optional_inputs": self.optional_inputs,
            "allowed_tools": self.allowed_tools,
            "workflow": self.workflow,
            "output_schema": self.output_schema,
            "validation_rules": self.validation_rules,
        }


ToolCaller = Callable[[str, dict[str, Any]], Awaitable[Any]]
EventEmitter = Callable[..., Awaitable[None]]


class Skill:
    """Small interface implemented by each domain skill."""

    metadata: SkillMetadata

    def describe(self) -> dict[str, Any]:
        return self.metadata.public()

    def validate(self, request: dict[str, Any], control_plane: Any) -> None:
        raise NotImplementedError

    async def execute(self, request: dict[str, Any], *, control_plane: Any,
                      call_tool: ToolCaller, emit: EventEmitter) -> dict[str, Any]:
        raise NotImplementedError
