"""MCP Tool: score_offtargets

Calculate CFD-style specificity scores for off-target candidates.
Integrates with existing CRISPOR CFD scoring resources.

Tier: MODERATE (pickle loading + computation)
"""

from __future__ import annotations

import os
import pickle
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import PAMSiteRow, ToolResult
from references import get_cfd_resources
from parsers.pam import _complement


# Module-level caches for loaded pickle data
_mm_scores = None
_pam_scores = None


def _load_cfd_data() -> tuple[dict, dict]:
    """Load CFD scoring data from pickle files. Cached after first load."""
    global _mm_scores, _pam_scores
    if _mm_scores is not None and _pam_scores is not None:
        return _mm_scores, _pam_scores

    mm_path, pam_path = get_cfd_resources()
    with open(mm_path, "rb") as f:
        _mm_scores = pickle.load(f)
    with open(pam_path, "rb") as f:
        _pam_scores = pickle.load(f)
    return _mm_scores, _pam_scores


def _revcom(s: str) -> str:
    """Reverse complement."""
    basecomp = {"A": "T", "C": "G", "G": "C", "T": "A", "U": "A"}
    return "".join(basecomp.get(b, "N") for b in reversed(s.upper()))


def calc_cfd(wt: str, sg: str, pam: str) -> float:
    """Calculate CFD score for a single off-target.

    Args:
        wt: Wild-type 20nt spacer sequence (DNA).
        sg: Off-target 20nt sequence (DNA, without PAM).
        pam: Off-target PAM (2nt for SpCas9 NGG).

    Returns:
        CFD score between 0 and 1. Higher = more likely to be cut.
    """
    mm_scores, pam_scores = _load_cfd_data()

    # Convert T→U for RNA-based scoring
    sg_rna = sg.replace("T", "U")
    wt_rna = wt.replace("T", "U")

    score = 1.0
    s_list = list(sg_rna)
    wt_list = list(wt_rna)

    for i, sl in enumerate(s_list):
        if i >= len(wt_list):
            break
        if wt_list[i] != sl:
            # Mismatch key format: r<WT>:d<RC>,<position>
            key = f"r{wt_list[i]}:d{_revcom(sl)},{i + 1}"
            if key in mm_scores:
                score *= mm_scores[key]
            else:
                score *= 0.5  # default penalty for unknown mismatch

    # PAM score
    pam_upper = pam.upper()
    if pam_upper in pam_scores:
        score *= pam_scores[pam_upper]

    return score


def score_offtargets(
    spacer_sequence: str,
    candidates: list[PAMSiteRow],
    pam_pattern: str = "NGG",
) -> ToolResult:
    """Score off-target candidates using CFD scoring.

    Takes candidate off-target rows (e.g. from offtarget_search) and
    calculates CFD-style specificity scores for each.

    NOTE: CFD scoring is derived from the Doench et al. 2016 method.
    It is NOT experimentally validated by VEYRA. Provenance is preserved
    in the output metadata.

    Args:
        spacer_sequence: The wild-type 20nt spacer sequence.
        candidates: List of PAMSiteRow candidates to score.
        pam_pattern: The PAM pattern used (for PAM scoring context).

    Returns:
        ToolResult with cfd_score added to each row.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Validate spacer
    if not spacer_sequence or len(spacer_sequence) < 15:
        return ToolResult(
            tool="score_offtargets",
            errors=[f"Spacer sequence too short or empty: {len(spacer_sequence or '')}nt"],
        )

    wt = spacer_sequence.upper().replace("U", "T")

    # Try to load CFD data
    try:
        _load_cfd_data()
    except FileNotFoundError as e:
        return ToolResult(
            tool="score_offtargets",
            errors=[f"CFD scoring resources not found: {e}"],
        )
    except Exception as e:
        return ToolResult(
            tool="score_offtargets",
            errors=[f"Failed to load CFD scoring data: {e}"],
        )

    scored_rows: list[PAMSiteRow] = []
    for cand in candidates:
        # Extract the protospacer for scoring
        if cand.protospacer and len(cand.protospacer) >= 20:
            sg = cand.protospacer[:20]
        else:
            # If no protospacer, try to determine from context
            # For now, skip scoring
            cand.cfd_score = None
            scored_rows.append(cand)
            continue

        # Get PAM
        pam = cand.pam or "NG"

        try:
            cfd = calc_cfd(wt, sg, pam)
            cand.cfd_score = round(cfd, 6)
        except Exception as e:
            warnings.append(f"CFD scoring failed for {cand.chrom}:{cand.start}: {e}")
            cand.cfd_score = None

        scored_rows.append(cand)

    # Sort by CFD score (higher = more concerning)
    scored_rows.sort(key=lambda r: -(r.cfd_score or 0))

    summary = {
        "total_scored": len(scored_rows),
        "spacer_length": len(wt),
        "scoring_method": "CFD (Doench et al. 2016)",
        "scoring_note": "CFD scores are NOT experimentally validated by VEYRA. Source: CRISPOR.",
        "mean_cfd": round(np.mean([r.cfd_score for r in scored_rows if r.cfd_score is not None]), 4) if scored_rows else 0,
        "max_cfd": round(max((r.cfd_score for r in scored_rows if r.cfd_score is not None), default=0), 4),
        "min_cfd": round(min((r.cfd_score for r in scored_rows if r.cfd_score is not None), default=0), 4),
    }

    return ToolResult(
        tool="score_offtargets",
        rows=scored_rows,
        summary=summary,
        errors=errors,
        warnings=warnings,
        metadata={
            "scoring_source": "CRISPOR CFD",
            "reference": "Doench et al. 2016",
            "provenance": "mismatch_score.pkl + pam_scores.pkl from crisporPaper/CFD_Scoring",
        },
    )


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="VEYRA score_offtargets tool")
    parser.add_argument("--spacer", "-s", required=True, help="WT spacer (20nt)")
    parser.add_argument("--candidates-json", required=True, help="JSON file with candidate rows")
    parser.add_argument("--pam", default="NGG")
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    with open(args.candidates_json) as f:
        cand_data = json.load(f)
    candidates = [PAMSiteRow(**c) for c in cand_data]

    result = score_offtargets(args.spacer, candidates, args.pam)
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
