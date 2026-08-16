"""Process-local MIDEND control plane and observability state.

This module deliberately contains orchestration metadata only. Backend tool
implementations remain in the existing HTTP/MCP connectors.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_KNOWN_SECRETS: set[str] = set()


def register_secret(value: str | None) -> None:
    if value and isinstance(value, str) and value.strip():
        _KNOWN_SECRETS.add(value.strip())

try:
    from .ai.conversation_compaction import ConversationCompactor
    from .ai.errors import AIProviderError, AIProviderNotConfiguredError
    from .ai.evidence_compaction import compact_evidence, format_compact_evidence_for_ai
    from .ai.models import AIMessage
    from .ai.openai_compatible import OpenAICompatibleProvider
    from .ai.tool_catalog import (
        generate_compact_tool_directory,
        get_active_tool_schemas,
        get_tool_catalog,
        select_active_tool_names,
    )
    from .ai.tool_definitions import analyze_parameters_meta, get_native_tools
    from .config.ai_provider import AIConfigError, AIProviderConfig, get_ai_config, get_ai_config_manager, validate_config
    from .config.settings import get_settings
    from .connectors import get_backend_connector
    from .connectors.models import ToolExecutionResult
    from .input_validation import InputRegistry, MIDENDInputError
    from .skills.registry import get_skill
except ImportError:  # pragma: no cover
    from ai.conversation_compaction import ConversationCompactor
    from ai.errors import AIProviderError, AIProviderNotConfiguredError
    from ai.evidence_compaction import compact_evidence, format_compact_evidence_for_ai
    from ai.models import AIMessage
    from ai.openai_compatible import OpenAICompatibleProvider
    from ai.tool_catalog import (
        generate_compact_tool_directory,
        get_active_tool_schemas,
        get_tool_catalog,
        select_active_tool_names,
    )
    from ai.tool_definitions import analyze_parameters_meta, get_native_tools
    from config.ai_provider import AIConfigError, AIProviderConfig, get_ai_config, get_ai_config_manager, validate_config
    from config.settings import get_settings
    from connectors import get_backend_connector
    from connectors.models import ToolExecutionResult
    from input_validation import InputRegistry, MIDENDInputError
    from skills.registry import get_skill


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def safe_value(value: Any) -> Any:
    """Remove common secret-shaped fields from public execution metadata."""
    if not value or isinstance(value, (int, float, bool)):
        return value
    secret_names = {"api_key", "apikey", "authorization", "token", "password", "secret"}
    if isinstance(value, dict):
        return {k: "[REDACTED]" if k.lower() in secret_names else safe_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_value(v) for v in value]
    if isinstance(value, str):
        for secret in _KNOWN_SECRETS:
            if secret and len(secret) >= 4 and secret in value:
                value = value.replace(secret, "[REDACTED]")
    return value


def format_tool_result_for_ai(tool_name: str, result: Any) -> str:
    """Format compact structured evidence for LLM prompt context."""
    res_dict = result.to_dict() if hasattr(result, "to_dict") else safe_value(result or {})
    if not isinstance(res_dict, dict):
        return json.dumps(safe_value(res_dict))

    if tool_name == "spcas9_gene_cutting":
        cands = res_dict.get("candidates", [])
        compact_cands = [
            {
                "rank": c.get("rank"),
                "protospacer": c.get("protospacer"),
                "pam": c.get("pam"),
                "strand": c.get("strand"),
                "cut_site": c.get("cut_site"),
                "gc_content": c.get("features", {}).get("gc", {}).get("summary", {}).get("gc_content"),
                "ontarget_score": c.get("ontarget", {}).get("score"),
                "warnings": c.get("warnings", []),
            }
            for c in cands[:10]
        ]
        compact = {
            "skill": "spcas9_gene_cutting",
            "status": res_dict.get("status"),
            "total_candidates": len(cands),
            "top_candidates": compact_cands,
            "warnings": res_dict.get("warnings", []),
            "errors": res_dict.get("errors", []),
        }
        return json.dumps(compact)

    if tool_name == "pam_scan":
        rows = res_dict.get("rows", [])
        compact = {
            "total_sites": res_dict.get("summary", {}).get("total_sites", len(rows)),
            "top_sites": [
                {
                    "protospacer": r.get("protospacer") if isinstance(r, dict) else getattr(r, "protospacer", ""),
                    "pam": r.get("pam") if isinstance(r, dict) else getattr(r, "pam", ""),
                    "strand": r.get("strand") if isinstance(r, dict) else getattr(r, "strand", "+"),
                    "start": r.get("start") if isinstance(r, dict) else getattr(r, "start", None),
                    "end": r.get("end") if isinstance(r, dict) else getattr(r, "end", None),
                }
                for r in rows[:10]
            ],
            "summary": res_dict.get("summary", {}),
        }
        return json.dumps(compact)

    if tool_name == "offtarget_search":
        rows = res_dict.get("rows", [])
        compact = {
            "total_candidates": res_dict.get("summary", {}).get("total_candidates", len(rows)),
            "mismatch_distribution": res_dict.get("summary", {}).get("mismatch_distribution", {}),
            "top_hits": rows[:8],
        }
        return json.dumps(compact)

    return json.dumps(res_dict)


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
        return {
            "call_id": self.call_id,
            "execution_id": self.execution_id,
            "tool": self.tool,
            "connector": self.connector,
            "arguments": self.arguments,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "result": self.result,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


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
    analysis_input: dict[str, Any] | None = None
    calibration_input: dict[str, Any] | None = None
    calibration_status: str = "not_provided"
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
                "analysis_input": safe_value(self.analysis_input),
                "calibration_input": safe_value(self.calibration_input),
                "calibration_status": self.calibration_status,
                "assistant_output": self.assistant_output, "deterministic_evidence": safe_value(self.deterministic_evidence),
                "skill_result": safe_value(self.skill_result),
                "tool_calls": [c.public() for c in self.tool_calls],
                "parallel_groups": safe_value(self.parallel_groups),
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

    def __init__(self, compactor: ConversationCompactor | None = None):
        self.compactor = compactor or ConversationCompactor(max_recent_turns=4)

    def build(self, *, system_instructions: str, developer_context: str | None,
              history: list[dict[str, str]], user_message: str,
              tool_results: list[dict[str, Any]] | None = None,
              session_metadata: dict[str, Any] | None = None) -> list[AIMessage]:
        messages = [AIMessage(role="system", content=system_instructions)]
        if developer_context:
            messages.append(AIMessage(role="system", content=f"DEVELOPER CONTEXT:\n{developer_context}"))
        
        compacted_history = self.compactor.compact_history(history, session_metadata=session_metadata)
        messages.extend(AIMessage(role=m["role"], content=m["content"]) for m in compacted_history)
        
        if tool_results:
            # Inject compact representation of pre-existing evidence
            compact_ev = [
                compact_evidence(r.get("tool", "unknown"), r, execution_id=r.get("execution_id"))
                if isinstance(r, dict) else str(r)
                for r in tool_results
            ]
            messages.append(AIMessage(role="system", content=f"TOOL-PRODUCED EVIDENCE:\n{safe_value(compact_ev)}"))
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

        # Explicit analysis / calibration input handling
        analysis_item = None
        analysis_id = payload.get("analysis_input_id") or payload.get("analysis_input")
        if analysis_id:
            analysis_item = self.inputs.get_analysis_input(analysis_id)
            if analysis_item not in input_items:
                input_items.append(analysis_item)

        calibration_item = None
        calibration_id = (
            payload.get("calibration_input_id")
            or payload.get("calibration_input")
            or payload.get("calibration_id")
        )
        if calibration_id:
            calibration_item = self.inputs.get_calibration_input(calibration_id)
            if calibration_item not in input_items:
                input_items.append(calibration_item)

        # Distinguish from input_ids list if not explicitly provided
        for item in input_items:
            if item.input_class == "analysis_input" and analysis_item is None:
                analysis_item = item
            elif item.input_class == "calibration_input" and calibration_item is None:
                calibration_item = item

        calib_status = "not_provided"
        if calibration_item:
            calib_status = calibration_item.calibration_status or "user_supplied"

        all_calls = list(payload.get("tool_calls", []))
        all_calls.extend(call for group in payload.get("parallel_groups", []) for call in group.get("calls", []))
        for call in all_calls:
            if any(key.lower() in {"path", "file_path", "filepath", "input_path"} for key in call.get("arguments", {})):
                raise MIDENDInputError("unreadable_file", "Tool calls must reference validated input IDs, not filesystem paths.")

        execution = ExecutionState(
            identifier,
            connector=payload.get("connector") or self.active_connector,
            provider=provider.provider_id,
            model=payload.get("model") or self.providers.active_model,
            validated_inputs=[item.public() for item in input_items],
            analysis_input=analysis_item.public() if analysis_item else None,
            calibration_input=calibration_item.public() if calibration_item else None,
            calibration_status=calib_status,
        )
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

        analysis_item = None
        analysis_id = payload.get("input_id") or payload.get("analysis_input_id") or payload.get("analysis_input")
        if analysis_id:
            try:
                item = self.inputs.get(analysis_id)
                if item.input_class == "analysis_input":
                    analysis_item = item
            except Exception:
                pass

        calibration_item = None
        calib_id = (
            payload.get("calibration_input_id")
            or payload.get("calibration_input")
            or payload.get("calibration_id")
        )
        if calib_id:
            calibration_item = self.inputs.get_calibration_input(calib_id)

        calib_status = "not_provided"
        if calibration_item:
            calib_status = calibration_item.calibration_status or "user_supplied"
        elif skill_id in {"model_calibration", "calibration"}:
            calib_status = "uncalibrated"

        inputs_list = []
        if analysis_item:
            inputs_list.append(analysis_item.public())
        if calibration_item:
            inputs_list.append(calibration_item.public())

        execution = ExecutionState(
            identifier,
            connector=payload.get("connector") or self.active_connector,
            provider=provider.provider_id,
            model=payload.get("model") or self.providers.active_model,
            validated_inputs=inputs_list,
            analysis_input=analysis_item.public() if analysis_item else None,
            calibration_input=calibration_item.public() if calibration_item else None,
            calibration_status=calib_status,
        )
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
        timeout_sec = float(payload.get("timeout_seconds") or payload.get("timeout") or 120.0)
        execution.status, execution.started_at = "running", now_iso()
        self.providers.current_execution_id = execution.execution_id
        await self._emit(execution, "execution_started", status=execution.status)
        try:
            async with asyncio.timeout(timeout_sec):
                calls = list(payload.get("tool_calls") or [])
                groups = list(payload.get("parallel_groups") or [])
                ai_request = payload.get("ai_request")

                if groups:
                    for group in groups:
                        await self._run_group(execution, group.get("group_id") or new_id("group"), group.get("calls", []))
                elif calls:
                    for call in calls:
                        await self._run_call(execution, call)
                if ai_request:
                    await self._run_ai(execution, ai_request, conversation_id)
                if execution.status not in {"failed", "timed_out", "cancelled"}:
                    execution.status = "completed"
                    await self._emit(execution, "execution_completed", assistant_output=execution.assistant_output)
        except asyncio.TimeoutError:
            execution.status = "timed_out"
            execution.errors.append(f"execution_timed_out: operation exceeded {timeout_sec}s timeout limit")
            await self._emit(execution, "execution_timed_out", timeout_seconds=timeout_sec, errors=execution.errors)
        except asyncio.CancelledError:
            execution.status = "cancelled"
            await self._emit(execution, "execution_cancelled")
        except Exception as exc:
            execution.status = "failed"
            if not execution.errors:
                execution.errors.append(f"execution_error: {exc}")
            await self._emit(execution, "execution_failed", errors=execution.errors)
        finally:
            execution.finished_at, execution.elapsed_ms = now_iso(), (time.perf_counter() - started) * 1000
            execution.generation_active = execution.reasoning_active = False
            if self.providers.current_execution_id == execution.execution_id:
                self.providers.current_execution_id = None
                self.providers.current_request_id = None
                self.providers.generation_active = False
                self.providers.reasoning_active = False
            await self._emit(execution, "execution_finished", elapsed_ms=execution.elapsed_ms, status=execution.status)
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
        tool_name = call.get("tool") or call.get("tool_name", "")
        arguments = safe_value(call.get("arguments", {}))
        params_meta = analyze_parameters_meta(tool_name, arguments)
        metadata = safe_value(call.get("metadata", {}))
        metadata["parameters_meta"] = params_meta
        state = ToolCallState(
            call.get("call_id") or new_id("call"),
            execution.execution_id,
            tool_name,
            execution.connector,
            arguments,
            metadata=metadata,
        )
        execution.tool_calls.append(state)
        return state

    async def _run_call(self, execution: ExecutionState, call: dict[str, Any], state: ToolCallState | None = None):
        state = state or self._make_call(execution, call)

        # Clean up malformed sequence argument if model passed English text as sequence
        seq_val = state.arguments.get("sequence")
        if isinstance(seq_val, str) and any(c.upper() not in "ACGTRYSWKMBDHVN" for c in seq_val if not c.isspace()):
            state.arguments.pop("sequence", None)

        # Context inheritance for attached inputs or raw message sequence when tool call omits sequence/input_id
        if not state.arguments.get("sequence") and not state.arguments.get("input_id"):
            if execution.validated_inputs:
                for item_meta in execution.validated_inputs:
                    item_id = item_meta.get("input_id")
                    if item_id:
                        try:
                            val_item = self.inputs.get(item_id)
                            if val_item.input_class == "analysis_input":
                                if state.tool == "spcas9_gene_cutting":
                                    state.arguments["input_id"] = val_item.input_id
                                else:
                                    text = val_item._content[:5000].decode("utf-8", errors="replace")
                                    clean_seq = "".join(line.strip() for line in text.split("\n") if line.strip() and not line.startswith(">"))
                                    if clean_seq:
                                        state.arguments["sequence"] = clean_seq[:2000]
                                break
                        except Exception:
                            pass

        state.status, state.started_at = "running", now_iso()
        await self._emit(execution, "tool_call_started", call=state.public())
        started = time.perf_counter()
        event_name = "tool_call_failed"
        result = None

        if state.tool in {"spcas9_gene_cutting", "offtarget_toxicity_risk", "model_calibration"}:
            try:
                skill = get_skill(state.tool)
                skill_res = await skill.execute(
                    state.arguments,
                    control_plane=self,
                    call_tool=lambda t, a: self._run_call(execution, {"tool": t, "arguments": a}),
                    emit=lambda e, **d: self._emit(execution, e, skill=state.tool, **d),
                )
                state.result = safe_value(skill_res)
                state.success = skill_res.get("status") in {"complete", "prototype", "partial", "unavailable"}
                state.status = "completed" if state.success else "failed"
                state.errors = skill_res.get("errors", [])
                state.warnings = skill_res.get("warnings", [])
                execution.deterministic_evidence.append(state.result)
                event_name = "tool_call_completed" if state.success else "tool_call_failed"
                result = skill_res
            except Exception as exc:
                state.status, state.success, state.errors = "failed", False, [safe_value(str(exc))]
                result = {
                    "tool": state.tool,
                    "call_id": state.call_id,
                    "execution_id": execution.execution_id,
                    "status": "failed",
                    "success": False,
                    "errors": state.errors,
                    "warnings": state.warnings,
                }
                state.result = result
                execution.deterministic_evidence.append(result)
        else:
            try:
                connector = get_backend_connector(execution.connector)
                res = await connector.call_tool(state.tool, state.arguments)
                state.result = safe_value(res.to_dict())
                state.errors, state.warnings, state.metadata = res.errors, res.warnings, safe_value(res.metadata)
                state.metadata["parameters_meta"] = analyze_parameters_meta(state.tool, state.arguments)
                state.success = res.is_success
                state.status = "completed" if state.success else "failed"
                event_name = "tool_call_completed" if state.success else "tool_call_failed"
                execution.deterministic_evidence.append(state.result)
                result = res
            except Exception as exc:
                state.status, state.success, state.errors = "failed", False, [safe_value(str(exc))]
                result = ToolExecutionResult(
                    tool=state.tool,
                    errors=state.errors,
                    warnings=state.warnings,
                    metadata=state.metadata,
                )
                state.result = result.to_dict()
                execution.deterministic_evidence.append(state.result)
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
            raw_message = request.get("message", "")

            input_summaries = []
            analysis_input_meta = None
            calibration_input_meta = None

            if execution.validated_inputs:
                for item_meta in execution.validated_inputs:
                    item_id = item_meta.get("input_id")
                    if item_id:
                        try:
                            val_item = self.inputs.get(item_id)
                            if val_item.input_class == "analysis_input":
                                analysis_input_meta = val_item
                                text = val_item._content[:2000].decode("utf-8", errors="replace")
                                lines = text.split("\n")
                                first_line = lines[0] if lines else ""
                                clean_seq = "".join(line.strip() for line in lines if line.strip() and not line.startswith(">"))
                                preview = clean_seq[:200]
                                input_summaries.append(
                                    f"--- ATTACHED GENOMIC TARGET FILE ---\n"
                                    f"input_id: {val_item.input_id}\n"
                                    f"filename: {val_item.filename} ({val_item.detected_format}, {val_item.size_bytes:,} bytes)\n"
                                    f"header: {first_line}\n"
                                    f"sequence_preview (5' to 3', first {len(preview)} bp): {preview}\n"
                                    f"MANDATORY: Invoke tool `spcas9_gene_cutting` with argument `input_id='{val_item.input_id}'` to analyze this target.\n"
                                    f"--- END ATTACHED FILE ---"
                                )
                            elif val_item.input_class == "calibration_input":
                                calibration_input_meta = val_item
                                input_summaries.append(
                                    f"--- ATTACHED CALIBRATION DATASET ---\n"
                                    f"input_id: {val_item.input_id}\n"
                                    f"filename: {val_item.filename} ({val_item.detected_format}, {val_item.row_count} rows)\n"
                                    f"columns: {', '.join(val_item.columns or [])}\n"
                                    f"MANDATORY: Invoke tool `model_calibration` with argument `calibration_input_id='{val_item.input_id}'` to fit models on this dataset.\n"
                                    f"--- END CALIBRATION DATASET ---"
                                )
                        except Exception:
                            pass

            effective_user_message = (
                f"{raw_message}\n\n" + "\n\n".join(input_summaries)
                if input_summaries and not any(s in raw_message for s in input_summaries)
                else raw_message
            )

            compact_tool_dir = generate_compact_tool_directory()
            system_instructions = (
                "You are VEYRA — VEYRA Intelligence, an interpretable genomic intelligence engine for CRISPR/Cas9 guide design, sequence analysis, "
                "and empirical model calibration.\n\n"
                f"{compact_tool_dir}\n\n"
                "MANDATORY TOOL USE RULE:\n"
                "Whenever the user asks to find PAM sites, design/evaluate CRISPR guides, calculate sequence properties (GC, Tm, cut sites, homopolymers), "
                "search off-target loci, evaluate toxicity risk, or calibrate models, you MUST invoke the appropriate native tool or skill to obtain "
                "real deterministic evidence before providing your final answer. Ground all biological claims directly in deterministic tool evidence."
            )

            session_metadata = {
                "analysis_input_id": analysis_input_meta.input_id if analysis_input_meta else None,
                "analysis_filename": analysis_input_meta.filename if analysis_input_meta else None,
                "calibration_input_id": calibration_input_meta.input_id if calibration_input_meta else None,
                "active_skill": getattr(execution, "skill_result", {}).get("skill") if isinstance(execution.skill_result, dict) else None,
            }

            messages = self.prompt_builder.build(
                system_instructions=system_instructions,
                developer_context=None,
                history=history,
                user_message=effective_user_message,
                tool_results=execution.deterministic_evidence,
                session_metadata=session_metadata,
            )

            active_input_class = (
                "calibration_input" if calibration_input_meta
                else ("analysis_input" if analysis_input_meta else None)
            )

            catalog = get_tool_catalog()
            active_tool_names = set(select_active_tool_names(
                user_task=raw_message,
                active_skill=session_metadata["active_skill"],
                input_class=active_input_class,
                catalog=catalog,
            ))
            active_native_tools = catalog.get_native_schemas(list(active_tool_names))

            turn = 0
            max_turns = 6
            response = None

            while turn < max_turns:
                turn += 1
                await self._emit(execution, "ai_generation_started", request_id=req.request_id,
                                 generation_active=True, reasoning_active=True, turn=turn)
                response = await OpenAICompatibleProvider(record.config).generate(
                    messages, execution.model, tools=active_native_tools
                )
                req.usage = response.usage
                req.finish_reason = response.finish_reason

                if response.tool_calls:
                    tool_calls_list = response.tool_calls
                    messages.append(
                        AIMessage(
                            role="assistant",
                            content=response.content or None,
                            tool_calls=tool_calls_list,
                        )
                    )

                    await self._emit(execution, "ai_waiting_for_tool", request_id=req.request_id,
                                     tool_calls=[tc.get("function", {}).get("name") for tc in tool_calls_list],
                                     turn=turn)

                    for tc in tool_calls_list:
                        tc_id = tc.get("id") or new_id("tc")
                        func = tc.get("function") or {}
                        fn_name = func.get("name")
                        raw_args = func.get("arguments") or "{}"
                        try:
                            fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except Exception as parse_err:
                            fn_args = {"_malformed_arguments": raw_args, "_error": str(parse_err)}

                        # Dynamically expand active schemas if an unlisted tool was called
                        if fn_name and fn_name not in active_tool_names:
                            active_tool_names.add(fn_name)
                            tool_entry = catalog.get_tool(fn_name)
                            if tool_entry:
                                active_native_tools.append(tool_entry.schema)

                        call_res = await self._run_call(execution, {
                            "call_id": tc_id,
                            "tool": fn_name,
                            "arguments": fn_args,
                        })

                        tool_content = format_compact_evidence_for_ai(
                            fn_name, call_res, call_id=tc_id, execution_id=execution.execution_id
                        )
                        messages.append(
                            AIMessage(
                                role="tool",
                                tool_call_id=tc_id,
                                name=fn_name,
                                content=tool_content,
                            )
                        )
                else:
                    execution.assistant_output = response.content
                    break

            if response and not execution.assistant_output:
                execution.assistant_output = response.content

            req.status = "completed"
            if request.get("stream"):
                await self._emit(execution, "ai_stream_chunk", request_id=req.request_id,
                                 delta=execution.assistant_output or "", final=True)
            if conversation:
                self.conversations.append(conversation_id, "user", raw_message)
                self.conversations.append(conversation_id, "assistant", execution.assistant_output or "")
            event_name = "ai_generation_completed"
        except AIProviderNotConfiguredError as exc:
            req.status = "failed"
            execution.errors.append(exc.code)
            event_error = exc.code
            execution.assistant_output = "AI provider is not configured. Deterministic backend calculation tools remain available."
            execution.status = "completed" if execution.tool_calls else "failed"
        except AIProviderError as exc:
            req.status = "failed"
            execution.errors.append("ai_provider_error")
            event_error = "ai_provider_error"
            if execution.tool_calls:
                execution.status = "completed"
                execution.assistant_output = "AI provider network is temporarily unavailable. Deterministic tool evidence above was executed directly by the VEYRA backend."
            else:
                execution.status = "failed"
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
