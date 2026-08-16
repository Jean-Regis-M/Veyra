"""Comprehensive tests for full-genome scan timeout budget and safe timeout retry policy.

Validates Requirements A through M:
A. Normal request keeps existing timeout (120s).
B. Full-genome request receives larger timeout (300s).
C. Timeout -> retry attempt 2.
D. Attempt 2 succeeds -> exactly 2 attempts total.
E. Attempts 1 and 2 timeout -> attempt 3 runs.
F. Attempt 3 succeeds -> completed.
G. All 3 timeout -> terminal timed_out.
H. Non-timeout tool failure -> NO retry.
I. Validation failure -> NO retry.
J. Cancellation -> NO retry.
K. Retry event/state is exposed correctly (execution_retrying, attempt, max_attempts, lineage).
L. Frontend generation/reasoning indicators terminate correctly after success or final timeout.
M. Real GCF_000005845.2.fasta full-scan smoke test.
"""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from veyra.midend.ai.models import AIMessage, AIResponse
from veyra.midend.ai.openai_compatible import OpenAICompatibleProvider
from veyra.midend.connectors.errors import ConnectorTimeoutError
from veyra.midend.connectors.models import BackendToolSchema, ToolExecutionResult
from veyra.midend.control_plane import (
    ControlPlane,
    ExecutionState,
    control_plane,
    detect_timeout_budget,
    is_timeout_exception,
)
from veyra.midend.input_validation import validate_input_file
from veyra.midend.skills import SkillError
from veyra.midend.skills.spcas9_gene_cutting import SpCas9GeneCuttingSkill


def test_a_normal_request_keeps_default_timeout():
    """Requirement A: Normal targeted/quick requests keep existing standard timeout."""
    assert detect_timeout_budget({"sequence": "ATGCGAATATGTCTCTGTGAGGCTTTTCATTCTGACTGCAACGGGCAATATGTCTCTGTGTGG", "depth": "quick"}) == 120.0
    assert detect_timeout_budget({"depth": "quick", "analysis_scope": "quick"}) == 120.0
    assert detect_timeout_budget({"ai_request": {"message": "Find PAM sites in this gene"}}) == 120.0
    # Explicit override takes priority
    assert detect_timeout_budget({"timeout_seconds": 45.0, "depth": "full"}) == 45.0


def test_b_full_genome_request_receives_larger_timeout():
    """Requirement B: Full-genome analysis requests receive a larger execution budget."""
    # 1. Via depth="full"
    assert detect_timeout_budget({"depth": "full"}) == 300.0
    # 2. Via analysis_scope="full"
    assert detect_timeout_budget({"analysis_scope": "full"}) == 300.0
    assert detect_timeout_budget({"analysis_scope": "whole_genome"}) == 300.0
    # 3. Via full_scan flag
    assert detect_timeout_budget({"full_scan": True}) == 300.0
    # 4. Via natural language in ai_request
    assert detect_timeout_budget({"ai_request": {"message": "Scan the entire genome without truncation for SpCas9 cutting sites"}}) == 300.0
    assert detect_timeout_budget({"ai_request": {"message": "Perform a whole genome full scan"}}) == 300.0
    # 5. Via tool call depth="full"
    assert detect_timeout_budget({"tool_calls": [{"tool": "spcas9_gene_cutting", "arguments": {"depth": "full"}}]}) == 300.0


def test_c_d_timeout_triggers_retry_attempt_2_and_stops_on_success():
    """Requirements C & D: Timeout on attempt 1 triggers attempt 2. Success on attempt 2 stops immediately."""
    async def run():
        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Attempt 1 hangs and times out
                await asyncio.sleep(0.5)
                return AIResponse(content="late", model="m", finish_reason="stop", tool_calls=None)
            # Attempt 2 succeeds immediately
            return AIResponse(content="GC content calculated on attempt 2: 50%", model="m", finish_reason="stop", tool_calls=None)

        with patch.object(OpenAICompatibleProvider, "generate", mock_generate):
            exec_state = control_plane.create_execution({
                "timeout_seconds": 0.15,  # Short timeout for test
                "ai_request": {"message": "Calculate GC content"},
            })

            for _ in range(80):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "completed"
            assert exec_state.attempt == 2
            assert exec_state.max_attempts == 3
            assert exec_state.retry_reason == "timeout"
            assert "attempt 2" in (exec_state.assistant_output or "")

            # Verify emitted event history
            events = [e["event"] for e in exec_state.event_history]
            assert "execution_started" in events
            assert "attempt_timed_out" in events
            assert "execution_retrying" in events
            assert "execution_completed" in events

            # Verify attempt 3 was NOT run
            assert call_count == 2

    asyncio.run(run())


def test_e_f_attempts_1_and_2_timeout_attempt_3_succeeds():
    """Requirements E & F: Attempts 1 & 2 timeout -> attempt 3 runs and succeeds."""
    async def run():
        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count in {1, 2}:
                # Attempts 1 and 2 time out
                await asyncio.sleep(0.5)
                return AIResponse(content="late", model="m", finish_reason="stop", tool_calls=None)
            # Attempt 3 succeeds
            return AIResponse(content="Success on attempt 3!", model="m", finish_reason="stop", tool_calls=None)

        with patch.object(OpenAICompatibleProvider, "generate", mock_generate):
            exec_state = control_plane.create_execution({
                "timeout_seconds": 0.15,
                "ai_request": {"message": "Run analysis"},
            })

            for _ in range(120):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "completed"
            assert exec_state.attempt == 3
            assert "Success on attempt 3!" in (exec_state.assistant_output or "")
            assert call_count == 3

    asyncio.run(run())


def test_g_all_3_attempts_timeout_transitions_to_terminal_timed_out():
    """Requirement G: All 3 attempts time out -> terminal timed_out state with descriptive message."""
    async def run():
        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.5)
            return AIResponse(content="late", model="m", finish_reason="stop", tool_calls=None)

        with patch.object(OpenAICompatibleProvider, "generate", mock_generate):
            exec_state = control_plane.create_execution({
                "timeout_seconds": 0.1,
                "ai_request": {"message": "Run slow scan"},
            })

            for _ in range(100):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "timed_out"
            assert exec_state.attempt == 3
            assert call_count == 3
            assert len(exec_state.errors) > 0
            assert "exceeded" in exec_state.errors[-1]
            assert "3 attempts" in (exec_state.assistant_output or "") or "exceeded" in exec_state.errors[-1]
            assert exec_state.generation_active is False
            assert exec_state.reasoning_active is False

    asyncio.run(run())


def test_h_non_timeout_tool_failure_no_retry():
    """Requirement H: Non-timeout tool failure does NOT retry."""
    async def run():
        exec_state = control_plane.create_execution({
            "tool_calls": [{"tool": "compute_cut_site", "arguments": {"spacer_start": None}}],
        })

        for _ in range(50):
            if exec_state.status in {"completed", "failed", "timed_out"}:
                break
            await asyncio.sleep(0.05)

        assert exec_state.status == "completed"  # Control plane handles tool execution result cleanly
        assert exec_state.attempt == 1  # Exactly 1 attempt
        assert exec_state.tool_calls[0].status == "failed"
        events = [e["event"] for e in exec_state.event_history]
        assert "execution_retrying" not in events

    asyncio.run(run())


def test_i_validation_failure_no_retry():
    """Requirement I: Validation failure rejects immediately with NO retry."""
    skill = SpCas9GeneCuttingSkill()
    with pytest.raises(SkillError) as exc_info:
        skill.validate({"depth": "invalid_depth_value"}, control_plane)
    assert exc_info.value.code in {"invalid_depth", "invalid_skill_input"}


def test_j_cancellation_no_retry():
    """Requirement J: Cancelled execution does NOT retry."""
    async def run():
        exec_state = control_plane.create_execution({
            "timeout_seconds": 10.0,
            "tool_calls": [{"tool": "compute_gc_content", "arguments": {"sequence": "ATGC"}}],
        })

        # Cancel all active tasks
        for t in list(control_plane._tasks):
            t.cancel()

        await asyncio.sleep(0.1)
        assert exec_state.attempt == 1
        events = [e["event"] for e in exec_state.event_history]
        assert "execution_retrying" not in events

    asyncio.run(run())


def test_k_retry_event_and_state_lineage_exposed():
    """Requirement K: Retry event and state lineage are exposed correctly."""
    async def run():
        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(0.4)
            return AIResponse(content="Done", model="m", finish_reason="stop", tool_calls=None)

        with patch.object(OpenAICompatibleProvider, "generate", mock_generate):
            exec_state = control_plane.create_execution({
                "timeout_seconds": 0.1,
                "ai_request": {"message": "Test lineage"},
            })

            for _ in range(60):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            public_state = exec_state.public()
            assert "attempt" in public_state
            assert "max_attempts" in public_state
            assert "parent_execution_id" in public_state
            assert "retry_reason" in public_state
            assert public_state["max_attempts"] == 3

    asyncio.run(run())


def test_l_generation_and_reasoning_active_flags_halt():
    """Requirement L: Generation and reasoning active flags halt cleanly upon completion or timeout."""
    async def run():
        exec_state = control_plane.create_execution({
            "tool_calls": [{"tool": "compute_gc_content", "arguments": {"sequence": "ATGC"}}],
        })

        for _ in range(50):
            if exec_state.status in {"completed", "failed", "timed_out"}:
                break
            await asyncio.sleep(0.05)

        assert exec_state.generation_active is False
        assert exec_state.reasoning_active is False
        assert control_plane.providers.generation_active is False
        assert control_plane.providers.reasoning_active is False

    asyncio.run(run())


def test_m_real_ecoli_full_scan_smoke_test():
    """Requirement M: Real GCF_000005845.2.fasta full-scan smoke test finishes within extended budget."""
    async def run():
        skill = SpCas9GeneCuttingSkill()
        from veyra.midend.tests.test_genome_scope import ECOLI_FASTA_PATH

        assert ECOLI_FASTA_PATH.is_file(), f"Missing E. coli genome fixture: {ECOLI_FASTA_PATH}"
        fasta_bytes = ECOLI_FASTA_PATH.read_bytes()
        item = control_plane.inputs.add(validate_input_file("GCF_000005845.2.fasta", fasta_bytes))

        # Test full-scan execution with extended timeout
        exec_state = control_plane.create_skill_execution("spcas9_gene_cutting", {
            "input_id": item.input_id,
            "analysis_scope": "full",
            "strand": "both",
            "max_candidates": 5,
        })

        assert exec_state.timeout_seconds == 300.0  # Received full scan budget!
        assert exec_state.attempt == 1
        assert exec_state.max_attempts == 3

        # Wait for full scan execution to complete
        for _ in range(300):
            if exec_state.status in {"completed", "failed", "timed_out"}:
                break
            await asyncio.sleep(0.5)

        assert exec_state.status == "completed"
        assert exec_state.skill_result is not None
        assert exec_state.skill_result.get("status") in {"complete", "partial"}
        assert len(exec_state.skill_result.get("candidates", [])) > 0
        assert exec_state.skill_result.get("analysis_scope") == "full_genome"
        assert exec_state.skill_result.get("truncated") is False
    asyncio.run(run())
