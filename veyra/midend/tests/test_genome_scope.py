"""Tests for explicit genome-scale analysis scope: Quick Mode (25 kb) vs Whole-Genome Full Scan."""

import json
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch

from veyra.midend.skills.spcas9_gene_cutting import SpCas9GeneCuttingSkill
from veyra.midend.control_plane import control_plane
from veyra.midend.input_validation import validate_input_file
from veyra.midend.ai.evidence_compaction import compact_evidence, format_compact_evidence_for_ai
from veyra.midend.ai.openai_compatible import OpenAICompatibleProvider
from veyra.midend.ai.models import AIResponse


def _resolve_ecoli_fasta() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2] / "data" / "references" / "ecoli_k12" / "genome" / "GCF_000005845.2.fasta",
        Path(__file__).resolve().parents[3] / "data" / "references" / "ecoli_k12" / "genome" / "GCF_000005845.2.fasta",
        Path(__file__).resolve().parents[3] / "veyra" / "data" / "references" / "ecoli_k12" / "genome" / "GCF_000005845.2.fasta",
    ]
    for c in candidates:
        if c.is_file():
            return c
    try:
        from veyra.backend.references import get_genome
        return Path(get_genome("ecoli_k12_mg1655").fasta_path)
    except Exception:
        return candidates[0]


ECOLI_FASTA_PATH = _resolve_ecoli_fasta()


def test_1_large_fasta_default_quick_mode():
    skill = SpCas9GeneCuttingSkill()
    with open(ECOLI_FASTA_PATH, "rb") as f:
        fasta_bytes = f.read()
    item = control_plane.inputs.add(validate_input_file("GCF_000005845.2.fasta", fasta_bytes))

    # Request default quick mode
    request = {"input_id": item.input_id, "analysis_scope": "quick"}
    records, scope_info = skill._records(control_plane, request)

    assert scope_info["truncated"] is True
    assert scope_info["quick_mode"] is True
    assert scope_info["analysis_scope"] == "first_25000_bp"
    assert scope_info["full_input_length"] > 4_000_000
    assert scope_info["analyzed_length"] == 25_000
    assert "bounded to the first 25,000 bp" in scope_info["warning"]
    assert len(records[0][1]) == 25_000


def test_2_explicit_full_mode_on_large_fasta():
    skill = SpCas9GeneCuttingSkill()
    with open(ECOLI_FASTA_PATH, "rb") as f:
        fasta_bytes = f.read()
    item = control_plane.inputs.add(validate_input_file("GCF_000005845.2.fasta", fasta_bytes))

    # Request explicit full scan
    request = {"input_id": item.input_id, "analysis_scope": "full"}
    records, scope_info = skill._records(control_plane, request)

    assert scope_info["truncated"] is False
    assert scope_info["quick_mode"] is False
    assert scope_info["analysis_scope"] == "full_genome"
    assert scope_info["full_input_length"] > 4_000_000
    assert scope_info["analyzed_length"] == scope_info["full_input_length"]
    assert scope_info["warning"] is None
    assert len(records[0][1]) == scope_info["full_input_length"]


def test_3_small_fasta_no_truncation():
    skill = SpCas9GeneCuttingSkill()
    small_bytes = b">small_gene\nATGCGAATATGTCTCTGTGAGGCTTTTCATTCTGACTGCAACGGGCAATATGTCTCTGTGTGG\n"
    item = control_plane.inputs.add(validate_input_file("small.fasta", small_bytes))

    request = {"input_id": item.input_id}
    records, scope_info = skill._records(control_plane, request)

    assert scope_info["truncated"] is False
    assert scope_info["analysis_scope"] == "whole_sequence"
    assert scope_info["full_input_length"] == 63
    assert scope_info["analyzed_length"] == 63
    assert scope_info["warning"] is None


def test_4_evidence_compaction_preserves_scope_metadata():
    raw_skill_res = {
        "skill": "spcas9_gene_cutting",
        "status": "complete",
        "analysis_scope": "first_25000_bp",
        "full_input_length": 4641652,
        "analyzed_length": 25000,
        "truncated": True,
        "quick_mode": True,
        "scope_warning": "Genome-scale input was bounded to the first 25,000 bp for quick analysis.",
        "candidates": [{"rank": 1, "protospacer": "ACGGGCAATATGTCTCTGTG", "cut_site": 17}],
    }

    evidence = compact_evidence("spcas9_gene_cutting", raw_skill_res)
    assert evidence["analysis_scope"] == "first_25000_bp"
    assert evidence["full_input_length"] == 4641652
    assert evidence["analyzed_length"] == 25000
    assert evidence["truncated"] is True
    assert evidence["quick_mode"] is True
    assert "bounded to the first 25,000 bp" in evidence["scope_warning"]
    assert "scope_instruction" in evidence


def test_5_ai_receives_scope_instruction_and_explains():
    import asyncio
    async def run():
        with open(ECOLI_FASTA_PATH, "rb") as f:
            fasta_bytes = f.read()
        item = control_plane.inputs.add(validate_input_file("GCF_000005845.2.fasta", fasta_bytes))

        # Mock Turn 1: Model emits quick spcas9 call
        turn1 = AIResponse(
            content=None, model="model", finish_reason="tool_calls",
            tool_calls=[{"id": "tc1", "type": "function", "function": {"name": "spcas9_gene_cutting", "arguments": json.dumps({"input_id": item.input_id, "analysis_scope": "quick"})}}],
        )
        # Mock Turn 2: Model qualifies the bounded 25 kb scope
        turn2 = AIResponse(
            content="I performed a quick scan of the first 25 kb of the 4.64 Mb genome and identified 5 top candidate sites.",
            model="model", finish_reason="stop", tool_calls=None,
        )

        with patch.object(OpenAICompatibleProvider, "generate", AsyncMock(side_effect=[turn1, turn2])):
            exec_state = control_plane.create_execution({
                "input_ids": [item.input_id],
                "ai_request": {"message": "Find SpCas9 cutting sites in the attached genome."},
            })
            for _ in range(50):
                if exec_state.status in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.05)

            assert exec_state.status == "completed"
            assert "25 kb" in (exec_state.assistant_output or "")
            assert len(exec_state.tool_calls) >= 1
            spcas9_call = next(c for c in exec_state.tool_calls if c.tool == "spcas9_gene_cutting")
            call_res = spcas9_call.result
            assert call_res.get("truncated") is True
            assert call_res.get("analysis_scope") == "first_25000_bp"
            assert "bounded to the first 25,000 bp" in call_res.get("scope_warning")
    asyncio.run(run())
