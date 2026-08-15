"""Process-local MIDEND control plane and observability state.

This module deliberately contains orchestration metadata only. Backend tool
implementations remain in the existing HTTP/MCP connectors.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_KNOWN_SECRETS: set[str] = set()


def register_secret(value: str | None) -> None:
    if value:
        _KNOWN_SECRETS.add(value)

try:
    from .ai.errors import AIProviderError, AIProviderNotConfiguredError
    from .ai.models import AIMessage
    from .ai.openai_compatible import OpenAICompatibleProvider
    from .config.ai_provider import AIConfigError, AIProviderConfig, get_ai_config, get_ai_config_manager, validate_config
    from .config.settings import get_settings
    from .connectors import get_backend_connector
    from .input_validation import InputRegistry, MIDENDInputError
    from .skills.registry import get_skill
except ImportError:  # pragma: no cover
    from ai.errors import AIProviderError, AIProviderNotConfiguredError
    from ai.models import AIMessage
    from ai.openai_compatible import OpenAICompatibleProvider
    from config.ai_provider import AIConfigError, AIProviderConfig, get_ai_config, get_ai_config_manager, validate_config
    from config.settings import get_settings
    from connectors import get_backend_connector
    from input_validation import InputRegistry, MIDENDInputError
    from skills.registry import get_skill


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def safe_value(value: Any) -> Any:
    """Remove common secret-shaped fields from public execution metadata."""
    secret_names = {"api_key", "apikey", "authorization", "token", "password", "secret"}
    if isinstance(value, dict):
        return {k: "[REDACTED]" if k.lower() in secret_names else safe_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_value(v) for v in value]
    if isinstance(value, str):
        for secret in _KNOWN_SECRETS:
            value = value.replace(secret, "[REDACTED]")
    return value


@dataclass
class ProviderRecord:
    provider_id: str
    display_name: str
    type: str
    config: AIProviderConfig
    models: list[str]
    default_model: str
    available: bool = True

    def public(self) -> dict[str, Any]:
        return {"provider_id": self.provider_id, "display_name": self.display_name,
                "type": self.type, "configured": self.config.configured,
                "available": self.available, "models": self.models,
                "default_model": self.default_model}


class ProviderRegistry:
    def __init__(self):
        config = get_ai_config()
        self.providers: dict[str, ProviderRecord] = {}
        self.active_provider_id = config.provider
        self.active_model = config.model
        self.providers[self.active_provider_id] = ProviderRecord(
            provider_id=self.active_provider_id, display_name="OpenAI-Compatible",
            type="openai_compatible", config=config, models=[config.model], default_model=config.model,
        )
        register_secret(config.api_key)
        self.current_execution_id: str | None = None
        self.current_request_id: str | None = None
        self.generation_active = False
        self.reasoning_active = False

    def list_public(self) -> list[dict[str, Any]]:
        return [record.public() for record in self.providers.values()]

    def active(self) -> ProviderRecord:
        return self.providers[self.active_provider_id]

    def status(self) -> dict[str, Any]:
        record = self.active()
        return {"provider": record.type, "provider_id": record.provider_id, "model": self.active_model,
                "base_url": record.config.base_url, "configured": record.config.configured,
                "available": record.available, "generation_active": self.generation_active,
                "reasoning_active": self.reasoning_active, "current_execution_id": self.current_execution_id,
                "current_request_id": self.current_request_id}

    def add(self, *, provider_id: str, provider_type: str, base_url: str, api_key: str,
            models: list[str] | None, default_model: str, persist: bool = False) -> ProviderRecord:
        if persist:
            raise AIConfigError("plaintext provider-key persistence is disabled")
        if provider_type != "openai_compatible":
            raise AIConfigError("only openai_compatible providers are currently supported")
        if not provider_id.strip():
            raise AIConfigError("provider_id must be non-empty")
        model_list = [m.strip() for m in (models or [default_model]) if m and m.strip()]
        if not model_list or not default_model.strip() or default_model not in model_list:
            raise AIConfigError("default_model must be included in models")
        validate_config(base_url, api_key, default_model)
        config = AIProviderConfig(base_url.strip(), api_key.strip(), default_model.strip(), source="runtime",
                                  provider=provider_type)
        register_secret(config.api_key)
        record = ProviderRecord(provider_id, provider_id, provider_type, config, model_list, default_model)
        self.providers[provider_id] = record
        return record

    def select(self, provider_id: str, model: str | None = None) -> ProviderRecord:
        if provider_id not in self.providers:
            raise AIConfigError(f"unknown provider: {provider_id}")
        record = self.providers[provider_id]
        selected_model = model or record.default_model
        if selected_model not in record.models:
            raise AIConfigError(f"model is not available for provider '{provider_id}'")
        self.active_provider_id, self.active_model = provider_id, selected_model
        return record


@dataclass
class ToolCallState:
    call_id: str
    execution_id: str
    tool: str
    connector: str
    arguments: dict[str, Any]
    status: str = "queued"
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: float = 0.0
    success: bool = False
    result: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return safe_value(self.__dict__.copy())


@dataclass
class AIRequestState:
    request_id: str
    provider: str
    model: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: float = 0.0
    status: str = "queued"
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str | None = None

    def public(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ExecutionState:
    execution_id: str
    status: str = "queued"
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_ms: float = 0.0
    connector: str = "http"
    provider: str | None = None
    model: str | None = None
    validated_inputs: list[dict[str, Any]] = field(default_factory=list)
    reasoning_active: bool = False
    generation_active: bool = False
    assistant_output: str | None = None
    deterministic_evidence: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[ToolCallState] = field(default_factory=list)
    ai_requests: list[AIRequestState] = field(default_factory=list)
    parallel_groups: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skill_result: dict[str, Any] | None = None
    event_history: list[dict[str, Any]] = field(default_factory=list)
    subscribers: list[asyncio.Queue] = field(default_factory=list, repr=False)

    def public(self) -> dict[str, Any]:
        return {"execution_id": self.execution_id, "status": self.status, "started_at": self.started_at,
                "finished_at": self.finished_at, "elapsed_ms": self.elapsed_ms,
                "active_tool_calls": sum(c.status == "running" for c in self.tool_calls),
                "completed_tool_calls": sum(c.status == "completed" for c in self.tool_calls),
                "failed_tool_calls": sum(c.status == "failed" for c in self.tool_calls),
                "active_ai_requests": sum(r.status == "running" for r in self.ai_requests),
                "completed_ai_requests": sum(r.status == "completed" for r in self.ai_requests),
                "reasoning_active": self.reasoning_active, "generation_active": self.generation_active,
                "connector": self.connector, "provider": self.provider, "model": self.model,
                "validated_inputs": safe_value(self.validated_inputs),
                "assistant_output": self.assistant_output, "deterministic_evidence": safe_value(self.deterministic_evidence),
                "skill_result": safe_value(self.skill_result),
                "tool_calls": [c.public() for c in self.tool_calls],
                "errors": self.errors, "warnings": self.warnings}


class ConversationStore:
    def __init__(self):
        self.items: dict[str, dict[str, Any]] = {}

    def create(self, provider: str | None = None, model: str | None = None) -> dict[str, Any]:
        identifier = new_id("conv")
        item = {"conversation_id": identifier, "created_at": now_iso(), "updated_at": now_iso(),
                "provider": provider, "model": model, "messages": [], "execution_ids": []}
        self.items[identifier] = item
        return item

    def get(self, identifier: str) -> dict[str, Any]:
        if identifier not in self.items:
            raise KeyError(identifier)
        return self.items[identifier]

    def append(self, identifier: str, role: str, content: str) -> None:
        item = self.get(identifier)
        item["messages"].append({"role": role, "content": content})
        item["updated_at"] = now_iso()

    def clear(self, identifier: str) -> dict[str, Any]:
        item = self.get(identifier)
        item["messages"] = []
        item["updated_at"] = now_iso()
        return item


class PromptBuilder:
    """Builds labeled public prompt context; never stores hidden reasoning."""

    def build(self, *, system_instructions: str, developer_context: str | None,
              history: list[dict[str, str]], user_message: str,
              tool_results: list[dict[str, Any]] | None = None) -> list[AIMessage]:
        messages = [AIMessage(role="system", content=system_instructions)]
        if developer_context:
            messages.append(AIMessage(role="system", content=f"DEVELOPER CONTEXT:\n{developer_context}"))
        messages.extend(AIMessage(role=m["role"], content=m["content"]) for m in history)
        if tool_results:
            messages.append(AIMessage(role="system", content=f"TOOL-PRODUCED EVIDENCE:\n{safe_value(tool_results)}"))
        messages.append(AIMessage(role="user", content=user_message))
        return messages


class ControlPlane:
    def __init__(self):
        self.providers = ProviderRegistry()
        self.conversations = ConversationStore()
        self.prompt_builder = PromptBuilder()
        self.executions: dict[str, ExecutionState] = {}
        self.inputs = InputRegistry()
        self.active_connector = get_settings().midend_backend_connector
        self._tasks: set[asyncio.Task] = set()

    async def backend_status(self) -> dict[str, Any]:
        connector = get_backend_connector(self.active_connector)
        try:
            tools = await connector.list_tools()
            tool_count = len(tools)
            mcp_connector = get_backend_connector("mcp")
            mcp_available = bool(await mcp_connector.list_tools())
        except Exception:
            tool_count = None
            mcp_available = False
        return {"active_connector": self.active_connector, "available_connectors": ["http", "mcp"],
                "backend_url": connector.base_url if self.active_connector == "http" else None,
                "mcp_available": mcp_available, "tool_count": tool_count}

    async def tools(self) -> dict[str, Any]:
        connector = get_backend_connector(self.active_connector)
        tools = await connector.list_tools()
        return {"total_tools": len(tools), "connector": self.active_connector,
                "tools": [safe_value(tool.model_dump()) for tool in tools]}

    def create_execution(self, payload: dict[str, Any], conversation_id: str | None = None) -> ExecutionState:
        if payload.get("provider_id"):
            self.providers.select(payload["provider_id"], payload.get("model"))
        identifier = new_id("exec")
        provider = self.providers.active()
        input_items = [self.inputs.get(input_id) for input_id in payload.get("input_ids", [])]
        all_calls = list(payload.get("tool_calls", []))
        all_calls.extend(call for group in payload.get("parallel_groups", []) for call in group.get("calls", []))
        for call in all_calls:
            if any(key.lower() in {"path", "file_path", "filepath", "input_path"} for key in call.get("arguments", {})):
                raise MIDENDInputError("unreadable_file", "Tool calls must reference validated input IDs, not filesystem paths.")
        execution = ExecutionState(identifier, connector=payload.get("connector") or self.active_connector,
                                   provider=provider.provider_id, model=payload.get("model") or self.providers.active_model,
                                   validated_inputs=[item.public() for item in input_items])
        self.executions[identifier] = execution
        if conversation_id:
            self.conversations.get(conversation_id)["execution_ids"].append(identifier)
        task = asyncio.create_task(self._run(execution, payload, conversation_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return execution

    def create_skill_execution(self, skill_id: str, payload: dict[str, Any]) -> ExecutionState:
        skill = get_skill(skill_id)
        skill.validate(payload, self)
        identifier = new_id("exec")
        provider = self.providers.active()
        execution = ExecutionState(identifier, connector=payload.get("connector") or self.active_connector,
                                   provider=provider.provider_id, model=payload.get("model") or self.providers.active_model)
        self.executions[identifier] = execution
        task = asyncio.create_task(self._run_skill(execution, skill, payload))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return execution

    async def _emit(self, execution: ExecutionState, event: str, **data: Any) -> None:
        item = {"event_id": new_id("event"), "event": event, "execution_id": execution.execution_id,
                "timestamp": now_iso(), **safe_value(data)}
        execution.event_history.append(item)
        for queue in list(execution.subscribers):
            await queue.put(item)

    async def _run(self, execution: ExecutionState, payload: dict[str, Any], conversation_id: str | None) -> None:
        started = time.perf_counter()
        execution.status, execution.started_at = "running", now_iso()
        self.providers.current_execution_id = execution.execution_id
        await self._emit(execution, "execution_started", status=execution.status)
        try:
            calls = payload.get("tool_calls") or []
            groups = payload.get("parallel_groups") or []
            if groups:
                for group in groups:
                    await self._run_group(execution, group.get("group_id") or new_id("group"), group.get("calls", []))
            elif calls:
                for call in calls:
                    await self._run_call(execution, call)
            ai_request = payload.get("ai_request")
            if ai_request:
                await self._run_ai(execution, ai_request, conversation_id)
            if execution.status != "failed":
                execution.status = "completed"
                await self._emit(execution, "execution_completed", assistant_output=execution.assistant_output)
        except Exception:
            execution.status = "failed"
            execution.errors.append("execution failed")
            await self._emit(execution, "execution_failed", errors=execution.errors)
        finally:
            execution.finished_at, execution.elapsed_ms = now_iso(), (time.perf_counter() - started) * 1000
            if self.providers.current_execution_id == execution.execution_id:
                self.providers.current_execution_id = None
                self.providers.current_request_id = None
                self.providers.generation_active = False
                self.providers.reasoning_active = False
            await self._emit(execution, "execution_finished", elapsed_ms=execution.elapsed_ms)
            for queue in list(execution.subscribers):
                await queue.put(None)

    async def _run_group(self, execution: ExecutionState, group_id: str, calls: list[dict[str, Any]]) -> None:
        started = time.perf_counter()
        states = [self._make_call(execution, call) for call in calls]
        await self._emit(execution, "parallel_group_started", group_id=group_id,
                         calls=[state.call_id for state in states])
        await asyncio.gather(*(self._run_call(execution, call, state) for call, state in zip(calls, states)))
        duration = (time.perf_counter() - started) * 1000
        execution.parallel_groups.append({"group_id": group_id, "calls": [s.public() for s in states], "duration_ms": duration})
        await self._emit(execution, "parallel_group_completed", group_id=group_id,
                         calls=[s.public() for s in states], duration_ms=duration)

    def _make_call(self, execution: ExecutionState, call: dict[str, Any]) -> ToolCallState:
        state = ToolCallState(call.get("call_id") or new_id("call"), execution.execution_id,
                              call.get("tool") or call.get("tool_name", ""), execution.connector,
                              safe_value(call.get("arguments", {})))
        execution.tool_calls.append(state)
        return state

    async def _run_call(self, execution: ExecutionState, call: dict[str, Any], state: ToolCallState | None = None):
        state = state or self._make_call(execution, call)
        state.status, state.started_at = "running", now_iso()
        await self._emit(execution, "tool_call_started", call=state.public())
        started = time.perf_counter()
        event_name = "tool_call_failed"
        result = None
        try:
            connector = get_backend_connector(execution.connector)
            result = await connector.call_tool(state.tool, state.arguments)
            state.result = safe_value(result.to_dict())
            state.errors, state.warnings, state.metadata = result.errors, result.warnings, safe_value(result.metadata)
            state.success = result.is_success
            state.status = "completed" if state.success else "failed"
            event_name = "tool_call_completed" if state.success else "tool_call_failed"
            execution.deterministic_evidence.append(state.result)
        except Exception as exc:
            # Keep connector diagnostics useful while still redacting any
            # accidentally surfaced secret-shaped value.
            state.status, state.errors = "failed", [safe_value(str(exc))]
        finally:
            state.finished_at, state.duration_ms = now_iso(), (time.perf_counter() - started) * 1000
            await self._emit(execution, event_name, call=state.public())
        return result

    async def _run_skill(self, execution: ExecutionState, skill: Any, payload: dict[str, Any]) -> None:
        started = time.perf_counter()
        execution.status, execution.started_at = "running", now_iso()
        self.providers.current_execution_id = execution.execution_id
        await self._emit(execution, "skill_started", skill=skill.metadata.skill_id, phase="input_validation")

        async def call_tool(tool: str, arguments: dict[str, Any]):
            result = await self._run_call(execution, {"tool": tool, "arguments": arguments})
            if result is None:
                # _run_call returns None only after an unexpected connector
                # exception; the recorded call state remains the evidence.
                raise RuntimeError(f"tool '{tool}' did not return a result")
            return result

        async def emit(event: str, **data: Any):
            await self._emit(execution, event, skill=skill.metadata.skill_id, **data)

        try:
            execution.skill_result = await skill.execute(payload, control_plane=self,
                                                         call_tool=call_tool, emit=emit)
            execution.deterministic_evidence.append(safe_value(execution.skill_result))
            execution.status = "completed" if execution.skill_result.get("status") == "complete" else "waiting"
            await self._emit(execution, "skill_completed", skill=skill.metadata.skill_id,
                             status=execution.skill_result.get("status"),
                             candidate_count=len(execution.skill_result.get("candidates", [])))
            if execution.status == "waiting":
                execution.status = "completed"
            await self._emit(execution, "execution_completed", skill=skill.metadata.skill_id)
        except Exception as exc:
            execution.status = "failed"
            if hasattr(exc, "code"):
                execution.errors.append(str(exc.code))
            else:
                execution.errors.append("skill_execution_failed")
            await self._emit(execution, "skill_failed", skill=skill.metadata.skill_id, errors=execution.errors)
            await self._emit(execution, "execution_failed", errors=execution.errors)
        finally:
            execution.finished_at, execution.elapsed_ms = now_iso(), (time.perf_counter() - started) * 1000
            if self.providers.current_execution_id == execution.execution_id:
                self.providers.current_execution_id = None
            await self._emit(execution, "execution_finished", elapsed_ms=execution.elapsed_ms)
            for queue in list(execution.subscribers):
                await queue.put(None)

    async def _run_ai(self, execution: ExecutionState, request: dict[str, Any], conversation_id: str | None) -> None:
        record = self.providers.active()
        req = AIRequestState(new_id("req"), record.provider_id, execution.model or record.default_model)
        execution.ai_requests.append(req)
        self.providers.current_request_id = req.request_id
        self.providers.generation_active = True
        self.providers.reasoning_active = True
        execution.generation_active = execution.reasoning_active = True
        req.status, req.started_at = "running", now_iso()
        ai_started = time.perf_counter()
        await self._emit(execution, "ai_request_started", request=req.public())
        await self._emit(execution, "ai_generation_started", request_id=req.request_id,
                         generation_active=True, reasoning_active=True)
        event_name = "ai_generation_failed"
        event_error: str | None = None
        try:
            conversation = self.conversations.get(conversation_id) if conversation_id else None
            history = conversation["messages"] if conversation else []
            message = request.get("message", "")
            messages = self.prompt_builder.build(system_instructions="You are the VEYRA MIDEND assistant.",
                                                 developer_context=None, history=history, user_message=message,
                                                 tool_results=execution.deterministic_evidence)
            if execution.validated_inputs:
                messages.insert(1, AIMessage(role="system", content=f"VALIDATED INPUT METADATA:\n{execution.validated_inputs}"))
            response = await OpenAICompatibleProvider(record.config).generate(messages, execution.model)
            execution.assistant_output = response.content
            req.status, req.usage, req.finish_reason = "completed", response.usage, response.finish_reason
            if request.get("stream"):
                await self._emit(execution, "ai_stream_chunk", request_id=req.request_id,
                                 delta=response.content, final=True)
            if conversation:
                self.conversations.append(conversation_id, "user", message)
                self.conversations.append(conversation_id, "assistant", response.content)
            event_name = "ai_generation_completed"
        except AIProviderNotConfiguredError as exc:
            req.status, execution.status = "failed", "failed"
            execution.errors.append(exc.code)
            event_error = exc.code
        except AIProviderError:
            req.status, execution.status = "failed", "failed"
            execution.errors.append("ai_provider_error")
            event_error = "ai_provider_error"
        finally:
            req.finished_at, req.duration_ms = now_iso(), (time.perf_counter() - ai_started) * 1000
            execution.generation_active = execution.reasoning_active = False
            self.providers.generation_active = self.providers.reasoning_active = False
            if event_name == "ai_generation_completed":
                await self._emit(execution, event_name, request=req.public(), output=execution.assistant_output)
            else:
                await self._emit(execution, event_name, request=req.public(), error=event_error or "ai_provider_error")

    async def stream(self, execution: ExecutionState):
        for event in execution.event_history:
            yield event
        if execution.status in {"queued", "running"}:
            queue: asyncio.Queue = asyncio.Queue()
            execution.subscribers.append(queue)
            try:
                while True:
                    event = await queue.get()
                    if event is None:
                        break
                    yield event
            finally:
                if queue in execution.subscribers:
                    execution.subscribers.remove(queue)


control_plane = ControlPlane()
