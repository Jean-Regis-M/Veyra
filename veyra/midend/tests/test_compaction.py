"""Tests for evidence compaction and conversation history compaction."""

import pytest
from veyra.midend.ai.evidence_compaction import compact_evidence, format_compact_evidence_for_ai
from veyra.midend.ai.conversation_compaction import ConversationCompactor


def test_evidence_compaction_pam_scan():
    raw_pam_result = {
        "summary": {"total_sites": 45, "fwd_count": 25, "rev_count": 20},
        "rows": [
            {"protospacer": f"ACGTACGTACGTACGTACG{i}", "pam": "TGG", "strand": "+", "start": i*10, "end": i*10+23}
            for i in range(45)
        ],
        "warnings": [],
        "errors": [],
    }

    evidence = compact_evidence("pam_scan", raw_pam_result, call_id="call_pam1", execution_id="exec_123", max_items=5)
    assert evidence["tool"] == "pam_scan"
    assert evidence["call_id"] == "call_pam1"
    assert evidence["execution_id"] == "exec_123"
    assert evidence["total_sites"] == 45
    assert evidence["returned_count"] == 5
    assert evidence["has_more"] is True
    assert len(evidence["top_sites"]) == 5

    formatted_str = format_compact_evidence_for_ai("pam_scan", raw_pam_result, call_id="call_pam1")
    assert "ACGTACGTACGTACGTACG0" in formatted_str
    assert '"total_sites": 45' in formatted_str
    # Raw result retains all 45 rows for UI
    assert len(raw_pam_result["rows"]) == 45


def test_evidence_compaction_offtarget_search():
    raw_offtarget_result = {
        "summary": {"total_candidates": 350, "mismatch_distribution": {"0": 1, "1": 4, "2": 45, "3": 300}},
        "rows": [
            {"target_sequence": f"ACGTACGTACGTACGTACG{i}", "mismatches": 2, "chrom": "chr1", "start": 1000 + i, "strand": "+"}
            for i in range(350)
        ],
        "warnings": [],
    }

    evidence = compact_evidence("offtarget_search", raw_offtarget_result, max_items=4)
    assert evidence["total_candidates"] == 350
    assert evidence["returned_count"] == 4
    assert evidence["has_more"] is True
    assert len(evidence["top_hits"]) == 4
    assert evidence["mismatch_distribution"]["2"] == 45


def test_evidence_compaction_spcas9_gene_cutting():
    raw_skill_result = {
        "status": "complete",
        "candidates": [
            {
                "rank": i + 1,
                "protospacer": f"ACGGGCAATATGTCTCTGT{i}",
                "pam": "AGG",
                "strand": "+",
                "cut_site": 17,
                "features": {"gc": {"summary": {"gc_content": 0.55}}},
                "ontarget": {"score": 0.85 - i * 0.05},
                "warnings": [],
            }
            for i in range(25)
        ],
        "warnings": [],
        "errors": [],
    }

    evidence = compact_evidence("spcas9_gene_cutting", raw_skill_result, max_items=5)
    assert evidence["total_candidates"] == 25
    assert evidence["returned_count"] == 5
    assert evidence["has_more"] is True
    assert len(evidence["top_candidates"]) == 5
    assert evidence["top_candidates"][0]["rank"] == 1
    assert evidence["top_candidates"][0]["protospacer"] == "ACGGGCAATATGTCTCTGT0"


def test_conversation_compactor_short_history():
    compactor = ConversationCompactor(max_recent_turns=3)
    short_history = [
        {"role": "user", "content": "Hello VEYRA"},
        {"role": "assistant", "content": "How can I assist your CRISPR design?"},
    ]

    compacted = compactor.compact_history(short_history)
    assert len(compacted) == 2
    assert compacted[0]["content"] == "Hello VEYRA"
    assert compacted[1]["content"] == "How can I assist your CRISPR design?"


def test_conversation_compactor_long_history():
    compactor = ConversationCompactor(max_recent_turns=2)
    long_history = [
        {"role": "user", "content": "Analyze target sequence in exec_001 with candidate ACGGGCAATATGTCTCTGTG"},
        {"role": "assistant", "content": "I identified 5 target sites in exec_001."},
        {"role": "user", "content": "What about off-targets for ACGGGCAATATGTCTCTGTG?"},
        {"role": "assistant", "content": "Found 3 low-risk off-target loci in exec_002."},
        {"role": "user", "content": "Can you compute the GC content?"},
        {"role": "assistant", "content": "GC content is 50%."},
        {"role": "user", "content": "What is the melting temperature?"},
        {"role": "assistant", "content": "Melting temperature is 62.4 C."},
    ]

    session_meta = {
        "analysis_input_id": "input_target_123",
        "analysis_filename": "ecoli_gene.fasta",
        "active_skill": "spcas9_gene_cutting",
    }

    compacted = compactor.compact_history(long_history, session_metadata=session_meta)

    # First message should be the summary
    assert compacted[0]["role"] == "system"
    summary = compacted[0]["content"]
    assert "SESSION STATE SUMMARY" in summary
    assert "input_target_123" in summary
    assert "exec_001" in summary or "exec_002" in summary
    assert "ACGGGCAATATGTCTCTGTG" in summary

    # Recent turns preserved verbatim (last 4 messages)
    assert len(compacted) == 5
    assert compacted[1]["content"] == "Can you compute the GC content?"
    assert compacted[4]["content"] == "Melting temperature is 62.4 C."
