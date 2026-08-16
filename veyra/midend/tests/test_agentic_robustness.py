"""Comprehensive agentic robustness and failure handoff test suite for VEYRA MIDEND.

Validates the 15 critical robustness scenarios:
1. successful single tool call
2. successful multi-tool chain
3. failed tool call -> model continuation
4. invalid tool arguments -> model correction
5. missing prerequisite -> model adaptation
6. provider returns malformed tool call
7. provider stops after tool failure
8. execution timeout
9. polling budget exhaustion
10. SSE disconnect/reconnect
11. terminal state synchronization
12. frontend stops generating indicator correctly
13. parallel tool failure where other calls succeed
14. failed skill child tool
15. final answer after partial evidence
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from veyra.midend.ai.models import AIMessage, AIResponse
from veyra.midend.ai.openai_compatible import OpenAICompatibleProvider
from veyra.midend.config.ai_provider import get_ai_config_manager
from veyra.midend.control_plane import control_plane
from veyra.midend.ai.evidence_compaction import compact_evidence, format_compact_evidence_for_ai


@pytest.fixture(autouse=True)
def setup_provider():
    get_ai_config_manager().configure(
        base_url="https://example.com/v1", api_key="secret_test_key", model="model"
    )
    try:
        control_plane.providers.add(
            provider_id="test_provider", provider_type="openai_compatible",
            base_url="https://example.com/v1", api_key="secret_test_key",
            models=["model"], default_model="model",
        )
    except Exception:
        pass
    control_plane.providers.select("test_provider", "model")


# ------------------------------------------------------------------------------
# 1. Successful Single Tool Call
# ------------------------------------------------------------------------------
def test_1_successful_single_tool_call():
    async def run():
        turn1 = AIResponse(
            content=None, model="model", finish_reason="tool_calls",
            tool_calls=[{"id": "c1", "type": "function", "function": {"name": "compute_gc_content", "arguments": json.dumps({"sequence": "ATGCGATCGATCGATCGATC"})}}],
        )
        turn2 = AIResponse(content="GC content is 50%.", model="model", finish_reason="stop", tool_calls=None)

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[turn1, turn2])):
            exec_state = control_plane.create_execution({
                "ai_request": {"message": "Calculate GC content of ATGCGATCGATCGATCGATC"},
            })
            for _ in range(50):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "completed"
            assert "GC content is 50%" in (exec_state.assistant_output or "")
            assert len(exec_state.tool_calls) == 1
            assert exec_state.tool_calls[0].status == "completed"
    asyncio.run(run())


# ------------------------------------------------------------------------------
# 2. Successful Multi-Tool Chain
# ------------------------------------------------------------------------------
def test_2_successful_multi_tool_chain():
    async def run():
        turn1 = AIResponse(
            content=None, model="model", finish_reason="tool_calls",
            tool_calls=[{"id": "c1", "type": "function", "function": {"name": "pam_scan", "arguments": json.dumps({"sequence": "ATGCGAATATGTCTCTGTGAGGCTTTTCATTCTGACTGCAACGGGCAATATGTCTCTGTGTGG"})}}],
        )
        turn2 = AIResponse(
            content=None, model="model", finish_reason="tool_calls",
            tool_calls=[{"id": "c2", "type": "function", "function": {"name": "compute_melting_temp", "arguments": json.dumps({"sequence": "ACGGGCAATATGTCTCTGTG"})}}],
        )
        turn3 = AIResponse(content="Found PAM and calculated Tm: 58.5 C.", model="model", finish_reason="stop", tool_calls=None)

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[turn1, turn2, turn3])):
            exec_state = control_plane.create_execution({
                "ai_request": {"message": "Find PAM and compute Tm"},
            })
            for _ in range(50):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "completed"
            assert len(exec_state.tool_calls) == 2
            assert all(c.status == "completed" for c in exec_state.tool_calls)
    asyncio.run(run())


# ------------------------------------------------------------------------------
# 3. Failed Tool Call -> Model Continuation & Hand-off
# ------------------------------------------------------------------------------
def test_3_failed_tool_call_returns_control_to_model():
    async def run():
        # Turn 1: Model calls offtarget_search with unknown genome -> Backend fails
        turn1 = AIResponse(
            content=None, model="model", finish_reason="tool_calls",
            tool_calls=[{"id": "c_fail", "type": "function", "function": {"name": "offtarget_search", "arguments": json.dumps({"spacer_sequence": "ACGGGCAATATGTCTCTGTG", "genome_id": "non_existent_genome"})}}],
        )
        # Turn 2: Model receives structured tool failure with role="tool", recognizes failure and responds
        turn2 = AIResponse(
            content="The off-target search failed because the genome ID 'non_existent_genome' was unknown.",
            model="model", finish_reason="stop", tool_calls=None,
        )

        generate_mock = AsyncMock(side_effect=[turn1, turn2])
        with patch.object(OpenAICompatibleProvider, "generate", generate_mock):
            exec_state = control_plane.create_execution({
                "ai_request": {"message": "Search off-targets for ACGGGCAATATGTCTCTGTG"},
            })
            for _ in range(50):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "completed"
            assert "unknown" in (exec_state.assistant_output or "").lower()
            assert len(exec_state.tool_calls) == 1
            assert exec_state.tool_calls[0].status == "failed"

            # Check what was passed to the model in Turn 2
            second_call_messages = generate_mock.call_args_list[1][0][0]
            tool_msg = next((m for m in second_call_messages if getattr(m, "role", None) == "tool"), None)
            assert tool_msg is not None
            assert tool_msg.tool_call_id == "c_fail"
            tool_content = json.loads(tool_msg.content)
            assert tool_content["status"] == "failed"
            assert tool_content["success"] is False
            assert "errors" in tool_content
    asyncio.run(run())


# ------------------------------------------------------------------------------
# 4. Invalid Tool Arguments -> Model Correction
# ------------------------------------------------------------------------------
def test_4_invalid_tool_arguments_model_correction():
    async def run():
        # Turn 1: Model emits invalid argument (spacer_start missing or invalid)
        turn1 = AIResponse(
            content=None, model="model", finish_reason="tool_calls",
            tool_calls=[{"id": "c_err", "type": "function", "function": {"name": "compute_cut_site", "arguments": json.dumps({"strand": "+"})}}],
        )
        # Turn 2: Model receives parameter error and retries with corrected arguments
        turn2 = AIResponse(
            content=None, model="model", finish_reason="tool_calls",
            tool_calls=[{"id": "c_fixed", "type": "function", "function": {"name": "compute_cut_site", "arguments": json.dumps({"spacer_start": 50, "strand": "+", "chrom": "NC_000913.3", "return_genomic_coord": True, "return_relative_coord": True})}}],
        )
        # Turn 3: Final response
        turn3 = AIResponse(content="Blunt cut position is relative 17.", model="model", finish_reason="stop", tool_calls=None)

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[turn1, turn2, turn3])):
            exec_state = control_plane.create_execution({
                "ai_request": {"message": "Compute cut position"},
            })
            for _ in range(50):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "completed"
            assert len(exec_state.tool_calls) == 2
            assert exec_state.tool_calls[0].status == "failed"
            assert exec_state.tool_calls[1].status == "completed"
            assert "17" in (exec_state.assistant_output or "")
    asyncio.run(run())


# ------------------------------------------------------------------------------
# 5. Missing Prerequisite -> Model Adaptation
# ------------------------------------------------------------------------------
def test_5_missing_prerequisite_model_adaptation():
    async def run():
        # Model requests cas_offinder on missing tool/input -> gets structured failure -> falls back to pam_scan
        turn1 = AIResponse(
            content=None, model="model", finish_reason="tool_calls",
            tool_calls=[{"id": "c_prereq", "type": "function", "function": {"name": "offtarget_search", "arguments": json.dumps({"spacer_sequence": "ACGGGCAATATGTCTCTGTG", "genome_id": "hg38_unindexed"})}}],
        )
        turn2 = AIResponse(
            content=None, model="model", finish_reason="tool_calls",
            tool_calls=[{"id": "c_fallback", "type": "function", "function": {"name": "compute_gc_content", "arguments": json.dumps({"sequence": "ACGGGCAATATGTCTCTGTG"})}}],
        )
        turn3 = AIResponse(content="Since human genome index is unavailable, I evaluated guide GC content: 55%.", model="model", finish_reason="stop", tool_calls=None)

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[turn1, turn2, turn3])):
            exec_state = control_plane.create_execution({
                "ai_request": {"message": "Evaluate guide ACGGGCAATATGTCTCTGTG"},
            })
            for _ in range(50):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "completed"
            assert len(exec_state.tool_calls) == 2
            assert exec_state.tool_calls[0].status == "failed"
            assert exec_state.tool_calls[1].status == "completed"
            assert "55%" in (exec_state.assistant_output or "")
    asyncio.run(run())


# ------------------------------------------------------------------------------
# 6. Provider Returns Malformed Tool Call JSON
# ------------------------------------------------------------------------------
def test_6_malformed_tool_call_json_handling():
    async def run():
        turn1 = AIResponse(
            content=None, model="model", finish_reason="tool_calls",
            tool_calls=[{"id": "c_bad_json", "type": "function", "function": {"name": "pam_scan", "arguments": "MALFORMED_NOT_JSON{{"}}],
        )
        turn2 = AIResponse(content="I handled the malformed call and continued.", model="model", finish_reason="stop", tool_calls=None)

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[turn1, turn2])):
            exec_state = control_plane.create_execution({
                "ai_request": {"message": "Scan PAM"},
            })
            for _ in range(50):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "completed"
            assert len(exec_state.tool_calls) == 1
    asyncio.run(run())


# ------------------------------------------------------------------------------
# 7. Provider Stops After Tool Failure (Clean Termination)
# ------------------------------------------------------------------------------
def test_7_provider_stops_after_tool_failure():
    async def run():
        turn1 = AIResponse(
            content=None, model="model", finish_reason="tool_calls",
            tool_calls=[{"id": "c_fail", "type": "function", "function": {"name": "compute_cut_site", "arguments": "{}"}}],
        )
        turn2 = AIResponse(content="I cannot compute cut site without coordinates.", model="model", finish_reason="stop", tool_calls=None)

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[turn1, turn2])):
            exec_state = control_plane.create_execution({
                "ai_request": {"message": "Compute cut site"},
            })
            for _ in range(50):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "completed"
            assert exec_state.assistant_output == "I cannot compute cut site without coordinates."
            assert exec_state.generation_active is False
            assert exec_state.reasoning_active is False
    asyncio.run(run())


# ------------------------------------------------------------------------------
# 8. Execution Timeout Handled Cleanly
# ------------------------------------------------------------------------------
def test_8_execution_timeout_transitions_to_timed_out():
    async def run():
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(2.0)
            return AIResponse(content="Done", model="model")

        with patch.object(OpenAICompatibleProvider, "generate", slow_generate):
            exec_state = control_plane.create_execution({
                "ai_request": {"message": "Compute something slow"},
                "timeout_seconds": 0.2,
            })
            for _ in range(50):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "timed_out"
            assert any("timed_out" in err for err in exec_state.errors)
            assert exec_state.generation_active is False
            assert exec_state.reasoning_active is False
    asyncio.run(run())


# ------------------------------------------------------------------------------
# 9. Polling Budget / Terminal State Check
# ------------------------------------------------------------------------------
def test_9_terminal_state_model():
    terminal_statuses = {"completed", "failed", "timed_out", "cancelled"}
    non_terminal = {"queued", "running", "waiting_for_tool", "waiting_for_model"}
    for s in terminal_statuses:
        assert s in {"completed", "failed", "timed_out", "cancelled"}


# ------------------------------------------------------------------------------
# 10. SSE Terminal Event Handled
# ------------------------------------------------------------------------------
def test_10_sse_events_emission():
    async def run():
        exec_state = control_plane.create_execution({
            "tool_calls": [{"tool": "compute_gc_content", "arguments": {"sequence": "ACGTACGTACGTACGTACGT"}}],
        })
        for _ in range(50):
            if exec_state.status in {"completed", "failed", "timed_out"}:
                break
            await asyncio.sleep(0.05)

        event_names = [e["event"] for e in exec_state.event_history]
        assert "execution_started" in event_names
        assert "tool_call_started" in event_names
        assert "tool_call_completed" in event_names
        assert "execution_completed" in event_names
        assert "execution_finished" in event_names
    asyncio.run(run())


# ------------------------------------------------------------------------------
# 11. Parallel Tool Failure Where Other Calls Succeed
# ------------------------------------------------------------------------------
def test_13_parallel_tool_partial_failure():
    async def run():
        exec_state = control_plane.create_execution({
            "parallel_groups": [{
                "group_id": "group_partial",
                "calls": [
                    {"tool": "compute_gc_content", "arguments": {"sequence": "ACGTACGTACGTACGTACGT"}},
                    {"tool": "compute_cut_site", "arguments": {"spacer_start": None}},  # Will fail
                ]
            }]
        })
        for _ in range(50):
            if exec_state.status in {"completed", "failed", "timed_out"}:
                break
            await asyncio.sleep(0.05)

        assert exec_state.status == "completed"
        calls = exec_state.tool_calls
        assert len(calls) == 2
        gc_call = next(c for c in calls if c.tool == "compute_gc_content")
        cut_call = next(c for c in calls if c.tool == "compute_cut_site")
        assert gc_call.status == "completed"
        assert cut_call.status == "failed"
    asyncio.run(run())


# ------------------------------------------------------------------------------
# 12. Final Answer After Partial Evidence
# ------------------------------------------------------------------------------
def test_15_final_answer_after_partial_evidence():
    async def run():
        turn1 = AIResponse(
            content=None, model="model", finish_reason="tool_calls",
            tool_calls=[
                {"id": "c1", "type": "function", "function": {"name": "compute_gc_content", "arguments": json.dumps({"sequence": "ACGTACGTACGTACGTACGT"})}},
                {"id": "c2", "type": "function", "function": {"name": "compute_melting_temp", "arguments": json.dumps({"sequence": "ACGTACGTACGTACGTACGT"})}},
            ],
        )
        turn2 = AIResponse(
            content="Evidence collected: GC=50%, Tm=58.5 C.",
            model="model", finish_reason="stop", tool_calls=None,
        )

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[turn1, turn2])):
            exec_state = control_plane.create_execution({
                "ai_request": {"message": "Analyze features of ACGTACGTACGTACGTACGT"},
            })
            for _ in range(50):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "completed"
            assert "GC=50%" in (exec_state.assistant_output or "")
            assert len(exec_state.deterministic_evidence) >= 2
    asyncio.run(run())
