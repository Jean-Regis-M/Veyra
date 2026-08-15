"""FastAPI service for the optional AI provider and deterministic backend connector."""

from __future__ import annotations

from typing import Any

import json
import re
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

try:  # Supports both ``import http_api`` from midend and ``import veyra.midend``.
    from ..ai.errors import AIProviderNotConfiguredError, AIProviderError
    from ..ai.models import AIMessage
    from ..ai.openai_compatible import OpenAICompatibleProvider
    from ..config.ai_provider import AIConfigError, get_ai_config, get_ai_config_manager
    from ..config.settings import get_settings
    from ..connectors import get_backend_connector
    from ..control_plane import AIConfigError as ControlAIConfigError, control_plane, register_secret
    from ..input_validation import MAX_INPUT_BYTES, MIDENDInputError, validate_input_file
    from ..skills import SkillError, get_skill, list_skills
except ImportError:  # pragma: no cover - compatibility for the existing source layout
    from ai.errors import AIProviderNotConfiguredError, AIProviderError
    from ai.models import AIMessage
    from ai.openai_compatible import OpenAICompatibleProvider
    from config.ai_provider import AIConfigError, get_ai_config, get_ai_config_manager
    from config.settings import get_settings
    from connectors import get_backend_connector
    from control_plane import AIConfigError as ControlAIConfigError, control_plane, register_secret
    from input_validation import MAX_INPUT_BYTES, MIDENDInputError, validate_input_file
    from skills import SkillError, get_skill, list_skills


class AIConfigRequest(BaseModel):
    base_url: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    persist: bool = False


class AIProviderRequest(BaseModel):
    provider_id: str = Field(..., min_length=1)
    type: str = "openai_compatible"
    base_url: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    models: list[str] = Field(default_factory=list)
    default_model: str = Field(..., min_length=1)
    persist: bool = False


class AIActiveRequest(BaseModel):
    provider_id: str
    model: str | None = None


class BackendActiveRequest(BaseModel):
    connector: str


class AIChatBody(BaseModel):
    message: str = Field(..., min_length=1)
    model: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    conversation_id: str | None = None
    provider_id: str | None = None
    backend_connector: str | None = None
    stream: bool = False
    input_ids: list[str] = Field(default_factory=list)
    analysis_input_id: str | None = None
    calibration_input_id: str | None = None


class ExecutionBody(BaseModel):
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    parallel_groups: list[dict[str, Any]] = Field(default_factory=list)
    ai_request: dict[str, Any] | None = None
    connector: str | None = None
    provider_id: str | None = None
    model: str | None = None
    input_ids: list[str] = Field(default_factory=list)
    analysis_input_id: str | None = None
    analysis_input: str | None = None
    calibration_input_id: str | None = None
    calibration_input: str | None = None
    calibration_id: str | None = None


class SkillExecutionBody(BaseModel):
    sequence: str | None = None
    spacer_sequence: str | None = None
    input_id: str | None = None
    analysis_input_id: str | None = None
    analysis_input: str | None = None
    calibration_input_id: str | None = None
    calibration_input: str | None = None
    calibration_id: str | None = None
    genome_id: str | None = None
    chrom: str | None = None
    start: int | None = None
    end: int | None = None
    strand: str = "both"
    depth: str = "quick"
    model: str = "auto"
    model_id: str | None = None
    max_candidates: int = Field(default=100, ge=1, le=1000)
    max_mismatches: int = Field(default=4, ge=0, le=10)
    max_results: int = Field(default=1000, ge=1, le=100000)
    offtarget_backend: str = "bwa"
    backend: str = "bwa"
    features: dict[str, Any] = Field(default_factory=dict)
    coefficients: dict[str, Any] | None = None
    coefficient_model_id: str = "offtarget_toxicity_prototype"
    connector: str | None = None
    target_column: str | None = None
    guide_column: str | None = None
    sh_column: str | None = None
    binding_column: str | None = None
    ca_column: str | None = None
    derive_features: bool = True


app = FastAPI(title="VEYRA MIDEND", version="0.1.0")


async def _read_request_body_bounded(request: Request, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise MIDENDInputError("file_too_large", f"The uploaded request exceeds the {limit} byte limit.")
        chunks.append(chunk)
    return b"".join(chunks)


async def _extract_multipart_file(request: Request) -> tuple[str, bytes, str | None]:
    content_type = request.headers.get("content-type", "")
    match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", content_type, re.IGNORECASE)
    if not content_type.lower().startswith("multipart/form-data") or not match:
        raise MIDENDInputError("unsupported_file_type", "File input must use multipart/form-data.")
    boundary = (match.group(1) or match.group(2)).strip().encode("utf-8")
    body = await _read_request_body_bounded(request, MAX_INPUT_BYTES + 1024 * 1024)
    delimiter = b"--" + boundary
    for part in body.split(delimiter):
        if b"Content-Disposition:" not in part or b"\r\n\r\n" not in part:
            continue
        header_bytes, payload = part.split(b"\r\n\r\n", 1)
        disposition = header_bytes.decode("latin-1", errors="replace")
        filename_match = re.search(r'filename="([^"]*)"', disposition, re.IGNORECASE)
        if not filename_match:
            continue
        filename = filename_match.group(1)
        payload = payload.rstrip(b"\r\n-")
        mime_match = re.search(r"\r\nContent-Type:\s*([^\r\n]+)", header_bytes.decode("latin-1", errors="replace"), re.IGNORECASE)
        return filename, payload, mime_match.group(1).strip() if mime_match else None
    raise MIDENDInputError("unreadable_file", "The multipart request did not contain a file field.")


def _input_error(exc: MIDENDInputError) -> JSONResponse:
    return JSONResponse(status_code=400, content=exc.to_dict())


@app.post("/inputs/file", status_code=201)
async def upload_input_file(request: Request):
    try:
        filename, content, content_type = await _extract_multipart_file(request)
        item = validate_input_file(filename, content, content_type)
        control_plane.inputs.add(item)
        return item.public()
    except MIDENDInputError as exc:
        return _input_error(exc)


@app.post("/calibration/file", status_code=201)
@app.post("/inputs/calibration", status_code=201)
async def upload_calibration_file(request: Request):
    try:
        filename, content, content_type = await _extract_multipart_file(request)
        item = validate_input_file(filename, content, content_type, expected_class="calibration_input")
        control_plane.inputs.add(item)
        return item.public()
    except MIDENDInputError as exc:
        return _input_error(exc)


@app.get("/inputs/{input_id}")
async def get_validated_input(input_id: str):
    try:
        return control_plane.inputs.get(input_id).public()
    except MIDENDInputError as exc:
        return _input_error(exc)


@app.get("/calibration/status")
async def get_calibration_status():
    from ..skills.offtarget_toxicity_risk import COEFFICIENT_REGISTRY
    calib_inputs = control_plane.inputs.list_calibration_inputs()
    return {
        "registered_datasets_count": len(calib_inputs),
        "datasets": [item.public() for item in calib_inputs],
        "coefficient_models": [model.public() for model in COEFFICIENT_REGISTRY.values()],
        "status": "available",
    }


@app.get("/calibration/{calibration_id}")
async def get_calibration_dataset(calibration_id: str):
    try:
        return control_plane.inputs.get_calibration_input(calibration_id).public()
    except MIDENDInputError as exc:
        return _input_error(exc)


@app.post("/calibration/run", status_code=202)
async def run_calibration_explicit(request: SkillExecutionBody):
    try:
        payload = request.model_dump(exclude_none=True)
        execution = control_plane.create_skill_execution("model_calibration", payload)
    except SkillError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict()) from None
    except MIDENDInputError as exc:
        return _input_error(exc)
    return {"execution_id": execution.execution_id, "skill": "model_calibration", "status": "started"}


@app.get("/health")
async def health() -> dict[str, Any]:
    settings = get_settings()
    return {"status": "ok", "service": "veyra-midend", "connector": settings.midend_backend_connector,
            "ai_configured": get_ai_config().configured, "provider_status":
            "configured" if get_ai_config().configured else "not_configured"}


@app.get("/ai/config")
async def ai_config_status() -> dict[str, Any]:
    return get_ai_config().status()


@app.get("/ai/status")
async def ai_status() -> dict[str, Any]:
    return control_plane.providers.status()


@app.get("/ai/providers")
async def ai_providers() -> dict[str, Any]:
    return {"providers": control_plane.providers.list_public()}


@app.post("/ai/providers")
async def add_ai_provider(request: AIProviderRequest) -> dict[str, Any]:
    if request.persist:
        raise HTTPException(status_code=422, detail={"code": "secure_persistence_unavailable",
                                                     "message": "API keys are kept process-local; plaintext persistence is disabled"})
    try:
        record = control_plane.providers.add(provider_id=request.provider_id, provider_type=request.type,
                                             base_url=request.base_url, api_key=request.api_key,
                                             models=request.models, default_model=request.default_model,
                                             persist=request.persist)
    except (AIConfigError, ControlAIConfigError) as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_ai_provider", "message": str(exc)}) from None
    return {"provider_id": record.provider_id, "configured": record.config.configured,
            "available": record.available, "models": record.models, "default_model": record.default_model}


@app.get("/ai/active")
async def ai_active() -> dict[str, Any]:
    record = control_plane.providers.active()
    return {"provider_id": record.provider_id, "provider": record.type,
            "model": control_plane.providers.active_model}


@app.post("/ai/active")
async def select_ai_active(request: AIActiveRequest) -> dict[str, Any]:
    try:
        record = control_plane.providers.select(request.provider_id, request.model)
    except (AIConfigError, ControlAIConfigError) as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_ai_selection", "message": str(exc)}) from None
    return {"provider_id": record.provider_id, "provider": record.type,
            "model": control_plane.providers.active_model}


@app.post("/ai/config")
async def configure_ai(request: AIConfigRequest) -> dict[str, Any]:
    if request.persist:
        raise HTTPException(status_code=422, detail={"code": "secure_persistence_unavailable",
                                                     "message": "API keys are kept process-local; plaintext persistence is disabled"})
    try:
        config = get_ai_config_manager().configure(base_url=request.base_url, api_key=request.api_key,
                                                    model=request.model, persist=request.persist)
    except AIConfigError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_ai_provider_config", "message": str(exc)}) from None
    active = control_plane.providers.active()
    register_secret(config.api_key)
    control_plane.providers.providers[active.provider_id].config = config
    control_plane.providers.providers[active.provider_id].models = [config.model]
    control_plane.providers.providers[active.provider_id].default_model = config.model
    control_plane.providers.active_model = config.model
    return {"configured": config.configured, "provider": config.provider,
            "base_url": config.base_url, "model": config.model}


@app.post("/ai/test")
async def test_ai() -> dict[str, Any]:
    try:
        result = await OpenAICompatibleProvider(control_plane.providers.active().config).test()
        return result
    except AIProviderNotConfiguredError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from None
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail={"code": "ai_provider_error", "message": str(exc)}) from None


@app.post("/ai/chat")
async def ai_chat(request: AIChatBody) -> dict[str, Any]:
    conversation_id = request.conversation_id
    if conversation_id is None:
        conversation = control_plane.conversations.create()
        conversation_id = conversation["conversation_id"]
    else:
        try:
            control_plane.conversations.get(conversation_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="conversation not found") from None
    payload = {"ai_request": {"message": request.message, "temperature": request.temperature,
                               "max_tokens": request.max_tokens}, "connector": request.backend_connector,
               "model": request.model, "provider_id": request.provider_id, "input_ids": request.input_ids}
    try:
        execution = control_plane.create_execution(payload, conversation_id)
    except (AIConfigError, ControlAIConfigError, MIDENDInputError) as exc:
        if isinstance(exc, MIDENDInputError):
            return _input_error(exc)
        raise HTTPException(status_code=422, detail={"code": "invalid_ai_selection", "message": str(exc)}) from None
    return {"execution_id": execution.execution_id, "conversation_id": conversation_id, "status": "started"}


@app.get("/backend/status")
async def backend_status() -> dict[str, Any]:
    return await control_plane.backend_status()


@app.post("/backend/active")
async def select_backend(request: BackendActiveRequest) -> dict[str, Any]:
    if request.connector not in {"http", "mcp"}:
        raise HTTPException(status_code=422, detail="connector must be http or mcp")
    if any(ex.status == "running" and ex.connector == control_plane.active_connector
           for ex in control_plane.executions.values()):
        raise HTTPException(status_code=409, detail="cannot change connector while an execution is running")
    control_plane.active_connector = request.connector
    return await control_plane.backend_status()


@app.get("/tools")
async def list_backend_tools() -> dict[str, Any]:
    return await control_plane.tools()


@app.get("/skills")
async def list_midend_skills() -> dict[str, Any]:
    return {"skills": list_skills()}


@app.get("/skills/{skill_id}")
async def get_midend_skill(skill_id: str) -> dict[str, Any]:
    try:
        return get_skill(skill_id).describe()
    except SkillError as exc:
        raise HTTPException(status_code=404, detail=exc.to_dict()) from None


@app.get("/skills/{skill_id}/status")
async def get_midend_skill_status(skill_id: str) -> dict[str, Any]:
    try:
        skill = get_skill(skill_id)
    except SkillError as exc:
        raise HTTPException(status_code=404, detail=exc.to_dict()) from None
    status = getattr(skill, "model_status", None)
    return status() if status else {"skill": skill.describe(), "status": "available"}


@app.post("/skills/{skill_id}", status_code=202)
async def execute_midend_skill(skill_id: str, request: SkillExecutionBody) -> dict[str, Any]:
    try:
        payload = request.model_dump(exclude_none=True)
        if payload.get("connector") and payload["connector"] not in {"http", "mcp"}:
            raise SkillError("invalid_connector", "connector must be 'http' or 'mcp'.", "connector")
        execution = control_plane.create_skill_execution(skill_id, payload)
    except SkillError as exc:
        status_code = 404 if exc.code == "unknown_skill" else 422
        raise HTTPException(status_code=status_code, detail=exc.to_dict()) from None
    except MIDENDInputError as exc:
        return _input_error(exc)
    return {"execution_id": execution.execution_id, "skill": skill_id, "status": "started"}


@app.post("/executions", status_code=202)
async def create_execution(request: ExecutionBody) -> dict[str, Any]:
    if request.connector and request.connector not in {"http", "mcp"}:
        raise HTTPException(status_code=422, detail="connector must be http or mcp")
    payload = request.model_dump(exclude_none=True)
    try:
        execution = control_plane.create_execution(payload)
    except (AIConfigError, ControlAIConfigError, MIDENDInputError) as exc:
        if isinstance(exc, MIDENDInputError):
            return _input_error(exc)
        raise HTTPException(status_code=422, detail={"code": "invalid_execution_config", "message": str(exc)}) from None
    return {"execution_id": execution.execution_id, "status": "started", "created_at": execution.started_at}


def _execution_or_404(execution_id: str):
    execution = control_plane.executions.get(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="execution not found")
    return execution


@app.get("/executions/{execution_id}")
async def get_execution(execution_id: str) -> dict[str, Any]:
    return _execution_or_404(execution_id).public()


@app.get("/executions")
async def list_executions() -> dict[str, Any]:
    return {"executions": [execution.public() for execution in control_plane.executions.values()]}


@app.get("/executions/{execution_id}/tools")
async def get_execution_tools(execution_id: str) -> dict[str, Any]:
    execution = _execution_or_404(execution_id)
    return {"execution_id": execution_id, "tools": [call.public() for call in execution.tool_calls],
            "parallel_groups": safe_public_groups(execution.parallel_groups)}


@app.get("/executions/{execution_id}/tools/{call_id}")
async def get_execution_tool(execution_id: str, call_id: str) -> dict[str, Any]:
    execution = _execution_or_404(execution_id)
    for call in execution.tool_calls:
        if call.call_id == call_id:
            return call.public()
    raise HTTPException(status_code=404, detail="tool call not found")


@app.get("/executions/{execution_id}/ai")
async def get_execution_ai(execution_id: str) -> dict[str, Any]:
    execution = _execution_or_404(execution_id)
    return {"execution_id": execution_id, "requests": [request.public() for request in execution.ai_requests]}


@app.get("/executions/{execution_id}/stream")
async def execution_stream(execution_id: str):
    execution = _execution_or_404(execution_id)

    async def events():
        async for event in control_plane.stream(execution):
            yield f"event: {event['event']}\ndata: {json.dumps(event, separators=(',', ':'))}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def safe_public_groups(groups):
    return [{"group_id": group.get("group_id"), "duration_ms": group.get("duration_ms"),
             "calls": [call for call in group.get("calls", [])]} for group in groups]


@app.post("/conversations", status_code=201)
async def create_conversation() -> dict[str, Any]:
    return control_plane.conversations.create()


@app.get("/conversations")
async def list_conversations() -> dict[str, Any]:
    return {"conversations": list(control_plane.conversations.items.values())}


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict[str, Any]:
    try:
        return control_plane.conversations.get(conversation_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="conversation not found") from None


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict[str, Any]:
    try:
        control_plane.conversations.clear(conversation_id)
        del control_plane.conversations.items[conversation_id]
    except KeyError:
        raise HTTPException(status_code=404, detail="conversation not found") from None
    return {"deleted": True, "conversation_id": conversation_id}


@app.post("/conversations/{conversation_id}/messages")
async def append_conversation_message(conversation_id: str, message: dict[str, str]) -> dict[str, Any]:
    try:
        control_plane.conversations.append(conversation_id, message.get("role", "user"), message["content"])
        return control_plane.conversations.get(conversation_id)
    except (KeyError, TypeError):
        raise HTTPException(status_code=404, detail="conversation or message not found") from None


@app.post("/prompts/preview")
async def preview_prompt(request: dict[str, Any]) -> dict[str, Any]:
    messages = control_plane.prompt_builder.build(
        system_instructions=request.get("system_instructions", "You are the VEYRA MIDEND assistant."),
        developer_context=request.get("developer_context"), history=request.get("history", []),
        user_message=request.get("user_message", ""), tool_results=request.get("tool_results"),
    )
    return {"messages": [message.model_dump() for message in messages]}


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
