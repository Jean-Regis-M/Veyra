"""Authoritative evidence compaction for AI context efficiency.

Produces concise, high-signal evidence summaries for the AI model while
preserving complete raw results for UI rendering and execution history.
"""

from __future__ import annotations

import json
from typing import Any


def compact_evidence(
    tool_name: str,
    result: Any,
    call_id: str | None = None,
    execution_id: str | None = None,
    max_items: int = 5,
) -> dict[str, Any]:
    """Return compact evidence dictionary for AI reasoning turns."""
    res_dict = result.to_dict() if hasattr(result, "to_dict") else (result or {})
    if not isinstance(res_dict, dict):
        return {
            "tool": tool_name,
            "call_id": call_id,
            "execution_id": execution_id,
            "raw_output": str(res_dict),
        }

    is_failed = (
        bool(res_dict.get("errors"))
        or res_dict.get("status") == "failed"
        or res_dict.get("success") is False
    )

    evidence: dict[str, Any] = {
        "tool": tool_name,
        "call_id": call_id,
        "execution_id": execution_id,
        "success": not is_failed,
        "status": "failed" if is_failed else res_dict.get("status", "completed"),
        "warnings": res_dict.get("warnings", []),
        "errors": res_dict.get("errors", []),
    }

    if is_failed:
        err_list = evidence["errors"] or (res_dict.get("errors") or [])
        if not err_list and res_dict.get("error"):
            err_list = [str(res_dict["error"])]
        evidence["errors"] = err_list
        evidence["diagnostic"] = (
            f"Tool '{tool_name}' failed with errors: {'; '.join(str(e) for e in err_list)}. "
            "You may retry with corrected parameters, select an alternative tool, or explain the limitation to the user."
        )
        return evidence

    if tool_name == "spcas9_gene_cutting":
        cands = res_dict.get("candidates", [])
        evidence["total_candidates"] = len(cands)
        evidence["returned_count"] = min(len(cands), max_items)
        evidence["has_more"] = len(cands) > max_items
        evidence["analysis_scope"] = res_dict.get("analysis_scope", "whole_sequence")
        evidence["full_input_length"] = res_dict.get("full_input_length")
        evidence["analyzed_length"] = res_dict.get("analyzed_length")
        evidence["truncated"] = res_dict.get("truncated", False)
        evidence["quick_mode"] = res_dict.get("quick_mode", False)
        if res_dict.get("scope_warning"):
            evidence["scope_warning"] = res_dict.get("scope_warning")
            evidence["scope_instruction"] = (
                "Genome-scale input was bounded to the first 25,000 bp for quick analysis. "
                "In your final response, explicitly state that a quick scan of the first 25 kb was performed "
                "and that this is not an exhaustive whole-genome ranking."
            )
        evidence["top_candidates"] = [
            {
                "rank": c.get("rank"),
                "protospacer": c.get("protospacer"),
                "pam": c.get("pam"),
                "strand": c.get("strand"),
                "cut_site": c.get("cut_site"),
                "guide_gc_content": c.get("features", {}).get("gc", {}).get("summary", {}).get("gc_content")
                if isinstance(c.get("features"), dict) else None,
                "gc_content": c.get("features", {}).get("gc", {}).get("summary", {}).get("gc_content")
                if isinstance(c.get("features"), dict) else None,
                "ontarget_score": c.get("ontarget", {}).get("score")
                if isinstance(c.get("ontarget"), dict) else None,
                "warnings": c.get("warnings", []),
            }
            for c in cands[:max_items]
        ]
        return evidence

    if tool_name in {"pam_scan", "pam_scan_region"}:
        rows = res_dict.get("rows", [])
        evidence["total_sites"] = res_dict.get("summary", {}).get("total_sites", len(rows))
        evidence["returned_count"] = min(len(rows), max_items)
        evidence["has_more"] = len(rows) > max_items
        evidence["summary"] = res_dict.get("summary", {})
        evidence["top_sites"] = [
            {
                "protospacer": r.get("protospacer") if isinstance(r, dict) else getattr(r, "protospacer", ""),
                "pam": r.get("pam") if isinstance(r, dict) else getattr(r, "pam", ""),
                "strand": r.get("strand") if isinstance(r, dict) else getattr(r, "strand", "+"),
                "start": r.get("start") if isinstance(r, dict) else getattr(r, "start", None),
                "end": r.get("end") if isinstance(r, dict) else getattr(r, "end", None),
            }
            for r in rows[:max_items]
        ]
        return evidence

    if tool_name == "offtarget_search":
        rows = res_dict.get("rows", [])
        evidence["total_candidates"] = res_dict.get("summary", {}).get("total_candidates", len(rows))
        evidence["returned_count"] = min(len(rows), max_items)
        evidence["has_more"] = len(rows) > max_items
        evidence["mismatch_distribution"] = res_dict.get("summary", {}).get("mismatch_distribution", {})
        evidence["top_hits"] = [
            {
                "sequence": r.get("sequence") or r.get("target_sequence"),
                "mismatches": r.get("mismatches"),
                "chrom": r.get("chrom"),
                "position": r.get("position") or r.get("start"),
                "strand": r.get("strand"),
            }
            for r in rows[:max_items]
        ]
        return evidence

    if tool_name == "score_offtargets":
        hits = res_dict.get("scored_candidates", []) or res_dict.get("hits", [])
        evidence["total_scored"] = len(hits)
        evidence["returned_count"] = min(len(hits), max_items)
        evidence["has_more"] = len(hits) > max_items
        evidence["aggregate_cfd"] = res_dict.get("aggregate_cfd") or res_dict.get("summary", {}).get("aggregate_cfd")
        evidence["top_scored_hits"] = hits[:max_items]
        return evidence

    if tool_name == "rank_candidates":
        guides = res_dict.get("ranked_guides", []) or res_dict.get("guides", [])
        evidence["total_ranked"] = len(guides)
        evidence["returned_count"] = min(len(guides), max_items)
        evidence["has_more"] = len(guides) > max_items
        evidence["sort_by"] = res_dict.get("sort_by")
        evidence["top_ranked"] = guides[:max_items]
        return evidence

    if tool_name == "compute_gc_content":
        evidence["gc_content"] = res_dict.get("gc_content") or res_dict.get("summary", {}).get("gc_content")
        evidence["gc_count"] = res_dict.get("gc_count") or res_dict.get("summary", {}).get("gc_count")
        evidence["sequence_length"] = res_dict.get("sequence_length") or res_dict.get("summary", {}).get("sequence_length") or res_dict.get("summary", {}).get("length")
        evidence["gc_5prime"] = res_dict.get("summary", {}).get("gc_5prime")
        evidence["gc_3prime"] = res_dict.get("summary", {}).get("gc_3prime")
        evidence["passes_basic_filter"] = res_dict.get("summary", {}).get("passes_basic_filter")
        evidence["sliding_window_min"] = res_dict.get("sliding_window_min") or res_dict.get("summary", {}).get("sliding_window_min")
        evidence["sliding_window_max"] = res_dict.get("sliding_window_max") or res_dict.get("summary", {}).get("sliding_window_max")
        return evidence

    if tool_name == "compute_melting_temp":
        evidence["tm"] = res_dict.get("tm") or res_dict.get("melting_temperature")
        evidence["method"] = res_dict.get("method")
        evidence["seed_tm"] = res_dict.get("seed_tm")
        return evidence

    if tool_name == "check_homopolymer_runs":
        evidence["has_homopolymer"] = res_dict.get("has_homopolymer")
        evidence["runs"] = res_dict.get("runs", [])
        evidence["polyT_terminated"] = res_dict.get("polyT_terminated", False)
        return evidence

    if tool_name == "compute_secondary_structure":
        evidence["mfe"] = res_dict.get("mfe") or res_dict.get("structure_mfe")
        evidence["structure"] = res_dict.get("structure")
        evidence["stable_hairpin"] = res_dict.get("stable_hairpin", False)
        return evidence

    if tool_name == "predict_ontarget_efficiency":
        evidence["score"] = res_dict.get("score") or res_dict.get("efficiency_score")
        evidence["model"] = res_dict.get("model")
        evidence["percentile"] = res_dict.get("percentile")
        return evidence

    if tool_name == "offtarget_toxicity_risk":
        evidence["risk_score"] = res_dict.get("risk_score") or res_dict.get("toxicity_probability")
        evidence["risk_tier"] = res_dict.get("risk_tier")
        evidence["formula_contributions"] = res_dict.get("contributions", {})
        evidence["coefficients_used"] = res_dict.get("coefficients", {})
        return evidence

    if tool_name == "model_calibration":
        evidence["calibration_status"] = res_dict.get("calibration_status")
        evidence["metrics"] = res_dict.get("metrics", {})
        evidence["fitted_coefficients"] = res_dict.get("fitted_coefficients", {})
        evidence["sample_count"] = res_dict.get("sample_count")
        return evidence

    # Generic fallback: include summary or top fields without large arrays
    filtered = {}
    for k, v in res_dict.items():
        if isinstance(v, list) and len(v) > max_items:
            filtered[k] = v[:max_items]
            filtered[f"{k}_total_count"] = len(v)
            filtered[f"{k}_has_more"] = True
        else:
            filtered[k] = v
    evidence.update(filtered)
    return evidence


def format_compact_evidence_for_ai(
    tool_name: str,
    result: Any,
    call_id: str | None = None,
    execution_id: str | None = None,
    max_items: int = 5,
) -> str:
    """Format compact evidence as a clean JSON string for LLM tool messages."""
    evidence_dict = compact_evidence(
        tool_name=tool_name,
        result=result,
        call_id=call_id,
        execution_id=execution_id,
        max_items=max_items,
    )
    return json.dumps(evidence_dict)
