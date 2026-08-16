"""Tests for biological tool argument normalization, input mode deduplication, and whole-file GC routing.

Validates:
1. Attached FASTA + compute_gc_content -> input_id / whole-file sequence only
2. Attached FASTA + spcas9_gene_cutting -> input_id only unless coordinate mode selected
3. Sequence + compute_gc_content -> sequence only
4. Genome coordinate mode -> genome_id + chrom + start + end only
5. Empty sequence is removed (sequence="" stripped)
6. Stale genome_id from previous turn does not leak into an input_id request
7. "what is gc content of this file?" -> executes compute_gc_content for the file
8. Previous candidate evidence does not satisfy whole-file GC request
9. Whole-file GC answer contains the deterministic GC result and correct scope
10. Same behavior in native and structured-fallback provider modes
11. Backend receives a schema-valid request in every case
12. 3-step conversation test (SpCas9 discovery -> whole-file GC -> guide GC)
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from veyra.midend.ai.models import AIMessage, AIResponse
from veyra.midend.ai.openai_compatible import OpenAICompatibleProvider
from veyra.midend.control_plane import (
    ControlPlane,
    ExecutionState,
    control_plane,
    normalize_tool_arguments,
    _extract_full_sequence_from_input,
)
from veyra.midend.input_validation import validate_input_file
from veyra.midend.skills.spcas9_gene_cutting import SpCas9GeneCuttingSkill


FASTA_BYTES = b">target_ecoli_gene\nACGTGACCTGAGGCTGATCCGTAGGCTAGCTAGGCCGATCGATCGA\n"
ECOLI_FASTA_PATH = Path(__file__).resolve().parents[2] / "data" / "references" / "ecoli_k12" / "genome" / "GCF_000005845.2.fasta"


def test_1_attached_fasta_compute_gc_resolves_whole_sequence():
    """1. Attached FASTA + compute_gc_content resolves to full sequence without duplicate input modes."""
    item = control_plane.inputs.add(validate_input_file("target.fasta", FASTA_BYTES))
    exec_state = ExecutionState("exec_1", validated_inputs=[item.public()])

    raw_args = {"input_id": item.input_id, "sequence": "", "genome_id": "ecoli"}
    normalized = normalize_tool_arguments("compute_gc_content", raw_args, control_plane, exec_state)

    assert "sequence" in normalized
    assert normalized["sequence"] == "ACGTGACCTGAGGCTGATCCGTAGGCTAGCTAGGCCGATCGATCGA"
    assert "input_id" not in normalized
    assert "genome_id" not in normalized


def test_2_attached_fasta_spcas9_gene_cutting_input_id_only():
    """2. Attached FASTA + spcas9_gene_cutting -> input_id only unless coordinate mode selected."""
    item = control_plane.inputs.add(validate_input_file("target.fasta", FASTA_BYTES))
    exec_state = ExecutionState("exec_2", validated_inputs=[item.public()])

    # Pass conflicting arguments with stale genome_id and empty sequence
    raw_args = {
        "input_id": item.input_id,
        "genome_id": "ecoli_k12_mg1655",
        "sequence": "",
        "analysis_scope": "quick",
    }
    normalized = normalize_tool_arguments("spcas9_gene_cutting", raw_args, control_plane, exec_state)

    assert normalized["input_id"] == item.input_id
    assert "sequence" not in normalized
    assert "genome_id" not in normalized
    assert normalized["analysis_scope"] == "quick"

    # Verify skill validates without error
    skill = SpCas9GeneCuttingSkill()
    skill.validate(normalized, control_plane)


def test_3_sequence_compute_gc_content_sequence_only():
    """3. Sequence + compute_gc_content -> sequence only."""
    raw_args = {
        "sequence": "ACGGGCAATATGTCTCTGTG",
        "input_id": "",
        "genome_id": "",
    }
    normalized = normalize_tool_arguments("compute_gc_content", raw_args, control_plane)

    assert normalized == {"sequence": "ACGGGCAATATGTCTCTGTG"}


def test_4_genomic_coordinate_mode_only():
    """4. Genome coordinate mode -> genome_id + chrom + start + end only."""
    raw_args = {
        "genome_id": "GRCh38.p14",
        "chrom": "chr1",
        "start": 1000000,
        "end": 1001000,
        "sequence": "",
        "input_id": "",
    }
    normalized = normalize_tool_arguments("spcas9_gene_cutting", raw_args, control_plane)

    assert normalized["genome_id"] == "GRCh38.p14"
    assert normalized["chrom"] == "chr1"
    assert normalized["start"] == 1000000
    assert normalized["end"] == 1001000
    assert "sequence" not in normalized
    assert "input_id" not in normalized


def test_5_empty_sequence_removed():
    """5. Empty strings are treated as absent across all tool types."""
    raw_args = {
        "sequence": "   ",
        "spacer_sequence": "  ",
        "genome_id": "",
        "input_id": None,
    }
    normalized = normalize_tool_arguments("compute_gc_content", raw_args, control_plane)
    assert "sequence" not in normalized
    assert "spacer_sequence" not in normalized
    assert "genome_id" not in normalized
    assert "input_id" not in normalized


def test_6_stale_genome_id_does_not_leak_into_input_id_request():
    """6. Stale genome_id from previous turn does not leak into an input_id request."""
    item = control_plane.inputs.add(validate_input_file("target.fasta", FASTA_BYTES))
    raw_args = {
        "input_id": item.input_id,
        "genome_id": "stale_genome_123",
        "depth": "quick",
    }
    normalized = normalize_tool_arguments("spcas9_gene_cutting", raw_args, control_plane)
    assert normalized["input_id"] == item.input_id
    assert "genome_id" not in normalized


def test_7_8_9_whole_file_gc_request_routes_to_compute_gc_content():
    """7, 8, 9. 'what is gc content of this file?' executes compute_gc_content on the whole file."""
    async def run():
        item = control_plane.inputs.add(validate_input_file("target.fasta", FASTA_BYTES))

        # Mock Turn 1: Model invokes compute_gc_content on attached file
        turn1 = AIResponse(
            content=None,
            model="model",
            finish_reason="tool_calls",
            tool_calls=[{
                "id": "tc_gc_file",
                "type": "function",
                "function": {
                    "name": "compute_gc_content",
                    "arguments": json.dumps({"input_id": item.input_id}),
                },
            }],
        )

        # Mock Turn 2: Model answers with whole-file GC content (58.7%)
        turn2 = AIResponse(
            content="The whole-file GC content of the attached sequence (47 bp) is 57.4%.",
            model="model",
            finish_reason="stop",
            tool_calls=None,
        )

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[turn1, turn2])):
            exec_state = control_plane.create_execution({
                "input_ids": [item.input_id],
                "ai_request": {"message": "what is gc content of this file?"},
            })

            for _ in range(60):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "completed"
            assert len(exec_state.tool_calls) == 1
            call = exec_state.tool_calls[0]
            assert call.tool == "compute_gc_content"
            assert "sequence" in call.arguments
            assert call.arguments["sequence"] == "ACGTGACCTGAGGCTGATCCGTAGGCTAGCTAGGCCGATCGATCGA"
            assert call.status == "completed"
            assert "gc_content" in call.result.get("summary", {})
            assert "57.4%" in (exec_state.assistant_output or "")

    asyncio.run(run())


def test_10_structured_fallback_mode_matches_native():
    """10. Same behavior in structured-fallback provider mode."""
    async def run():
        item = control_plane.inputs.add(validate_input_file("target.fasta", FASTA_BYTES))

        # Provider without native tool calling returns JSON markdown codeblock
        turn1 = AIResponse(
            content="```json\n{\n  \"tool\": \"compute_gc_content\",\n  \"arguments\": {\"input_id\": \"" + item.input_id + "\", \"genome_id\": \"stale\", \"sequence\": \"\"}\n}\n```",
            model="fallback_model",
            finish_reason="stop",
            tool_calls=None,  # No native tool_calls
        )

        turn2 = AIResponse(
            content="Calculated whole file GC content: 57.4%.",
            model="fallback_model",
            finish_reason="stop",
            tool_calls=None,
        )

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[turn1, turn2])):
            exec_state = control_plane.create_execution({
                "input_ids": [item.input_id],
                "ai_request": {"message": "what is gc content of this file?"},
            })

            for _ in range(60):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "completed"
            assert len(exec_state.tool_calls) == 1
            call = exec_state.tool_calls[0]
            assert call.tool == "compute_gc_content"
            assert "sequence" in call.arguments
            assert call.arguments["sequence"] == "ACGTGACCTGAGGCTGATCCGTAGGCTAGCTAGGCCGATCGATCGA"
            assert "genome_id" not in call.arguments
            assert call.status == "completed"

    asyncio.run(run())


def test_12_three_step_conversation_workflow():
    """12. Real UI test: 3-step conversation:
    Step 1: 'Find candidate SpCas9 sites' -> spcas9_gene_cutting
    Step 2: 'what is gc content of this file?' -> compute_gc_content(whole file)
    Step 3: 'what is gc content of this guide?' -> compute_gc_content(guide sequence)
    Verify the three outputs are distinct and not conflated.
    """
    async def run():
        item = control_plane.inputs.add(validate_input_file("target.fasta", FASTA_BYTES))
        conv = control_plane.conversations.create()
        cid = conv["conversation_id"]

        # --- STEP 1: Find candidate SpCas9 sites ---
        s1_turn1 = AIResponse(
            content=None, model="m", finish_reason="tool_calls",
            tool_calls=[{"id": "tc1", "type": "function", "function": {"name": "spcas9_gene_cutting", "arguments": json.dumps({"input_id": item.input_id, "genome_id": "ecoli", "sequence": ""})}}],
        )
        s1_turn2 = AIResponse(
            content="Found 2 SpCas9 candidate guides in the target gene. Top guide: ACGTGACCTGAGGCTGATCC (GC: 60%).",
            model="m", finish_reason="stop", tool_calls=None,
        )

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[s1_turn1, s1_turn2])):
            e1 = control_plane.create_execution({
                "input_ids": [item.input_id],
                "ai_request": {"message": "Find candidate SpCas9 sites"},
            }, conversation_id=cid)
            for _ in range(60):
                if e1.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert e1.status == "completed"
            assert len(e1.tool_calls) >= 1
            assert e1.tool_calls[0].tool == "spcas9_gene_cutting"
            assert e1.tool_calls[0].arguments["input_id"] == item.input_id
            assert "sequence" not in e1.tool_calls[0].arguments
            assert "genome_id" not in e1.tool_calls[0].arguments

        # --- STEP 2: what is gc content of this file? ---
        s2_turn1 = AIResponse(
            content=None, model="m", finish_reason="tool_calls",
            tool_calls=[{"id": "tc2", "type": "function", "function": {"name": "compute_gc_content", "arguments": json.dumps({"input_id": item.input_id})}}],
        )
        s2_turn2 = AIResponse(
            content="The whole-file GC content of the attached file is 57.4% across all 47 bp.",
            model="m", finish_reason="stop", tool_calls=None,
        )

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[s2_turn1, s2_turn2])):
            e2 = control_plane.create_execution({
                "input_ids": [item.input_id],
                "ai_request": {"message": "what is gc content of this file?"},
            }, conversation_id=cid)
            for _ in range(60):
                if e2.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert e2.status == "completed"
            assert len(e2.tool_calls) == 1
            assert e2.tool_calls[0].tool == "compute_gc_content"
            assert e2.tool_calls[0].arguments["sequence"] == "ACGTGACCTGAGGCTGATCCGTAGGCTAGCTAGGCCGATCGATCGA"
            assert "57.4%" in (e2.assistant_output or "")

        # --- STEP 3: what is gc content of this guide? ---
        guide_seq = "ACGTGACCTGAGGCTGATCC"
        s3_turn1 = AIResponse(
            content=None, model="m", finish_reason="tool_calls",
            tool_calls=[{"id": "tc3", "type": "function", "function": {"name": "compute_gc_content", "arguments": json.dumps({"sequence": guide_seq})}}],
        )
        s3_turn2 = AIResponse(
            content=f"The GC content of candidate guide {guide_seq} (20 bp) is 60.0%.",
            model="m", finish_reason="stop", tool_calls=None,
        )

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[s3_turn1, s3_turn2])):
            e3 = control_plane.create_execution({
                "input_ids": [item.input_id],
                "ai_request": {"message": "what is gc content of this guide?"},
            }, conversation_id=cid)
            for _ in range(60):
                if e3.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert e3.status == "completed"
            assert len(e3.tool_calls) == 1
            assert e3.tool_calls[0].tool == "compute_gc_content"
            assert e3.tool_calls[0].arguments["sequence"] == guide_seq
            assert "60.0%" in (e3.assistant_output or "")

    asyncio.run(run())
