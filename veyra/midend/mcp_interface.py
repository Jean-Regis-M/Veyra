"""Small public MCP-facing capability registry for the MIDEND control plane.

An MCP transport can bind these capability functions without exposing private
provider or execution implementation objects.
"""

from __future__ import annotations

from typing import Any

from .control_plane import control_plane
from .skills import get_skill, list_skills


async def ai_status() -> dict[str, Any]:
    return control_plane.providers.status()


async def list_ai_providers() -> dict[str, Any]:
    return {"providers": control_plane.providers.list_public()}


async def backend_status() -> dict[str, Any]:
    return await control_plane.backend_status()


async def list_tools() -> dict[str, Any]:
    return await control_plane.tools()


async def execution_status(execution_id: str) -> dict[str, Any]:
    execution = control_plane.executions.get(execution_id)
    if execution is None:
        raise KeyError(execution_id)
    return execution.public()


async def list_skills() -> dict[str, Any]:
    from .skills import list_skills as _list_skills
    return {"skills": _list_skills()}


async def skill_metadata(skill_id: str) -> dict[str, Any]:
    return get_skill(skill_id).describe()


async def execute_skill(skill_id: str, request: dict[str, Any]) -> dict[str, Any]:
    execution = control_plane.create_skill_execution(skill_id, request)
    return {"execution_id": execution.execution_id, "skill": skill_id, "status": "started"}


MIDEND_MCP_CAPABILITIES = {
    "ai_status": ai_status,
    "list_ai_providers": list_ai_providers,
    "backend_status": backend_status,
    "list_tools": list_tools,
    "execution_status": execution_status,
    "list_skills": list_skills,
    "skill_metadata": skill_metadata,
    "execute_skill": execute_skill,
}
