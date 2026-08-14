"""MCP Tool: rank_candidates

Produce a final sortable/rankable candidate table by aggregating
off-target evidence per candidate guide.

Tier: MODERATE

Design: Supports future scoring layers. Does NOT invent arbitrary
"VEYRA scientific scores" — uses transparent, source-attributed evidence.
"""

from __future__ import annotations

import sys
import os
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import PAMSiteRow, ToolResult


@dataclass
class CandidateGuide:
    """A guide candidate with aggregated off-target evidence."""

    chrom: str | None = None
    start: int | None = None
    end: int | None = None
    strand: str | None = None
    protospacer: str | None = None
    pam: str | None = None
    pam_type: str | None = None
    on_target_score: float | None = None
    total_offtargets: int = 0
    max_mismatches_found: int = 0
    mean_cfd: float | None = None
    max_cfd: float | None = None
    cfd_above_05_count: int = 0
    cfd_above_01_count: int = 0
    # Future scoring layers
    rs2_score: float | None = None
    evidence_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "chrom": self.chrom,
            "start": self.start,
            "end": self.end,
            "strand": self.strand,
            "protospacer": self.protospacer,
            "pam": self.pam,
            "pam_type": self.pam_type,
            "on_target_score": self.on_target_score,
            "total_offtargets": self.total_offtargets,
            "max_mismatches_found": self.max_mismatches_found,
            "mean_cfd": self.mean_cfd,
            "max_cfd": self.max_cfd,
            "cfd_above_05_count": self.cfd_above_05_count,
            "cfd_above_01_count": self.cfd_above_01_count,
            "rs2_score": self.rs2_score,
            "evidence_sources": self.evidence_sources,
        }


def rank_candidates(
    guides: list[PAMSiteRow],
    off_targets: list[PAMSiteRow] | None = None,
    on_target_scores: dict[str, float] | None = None,
    sort_by: str = "composite",
) -> ToolResult:
    """Aggregate off-target evidence and rank candidate guides.

    The ranking is based on transparent aggregation of available evidence.
    It does NOT claim to be a validated predictive model.

    Future VEYRA reasoning layers will consume this ranked table
    and apply additional scoring.

    Args:
        guides: Candidate guide rows (from pam_scan).
        off_targets: Off-target search results (from offtarget_search + score_offtargets).
        on_target_scores: Optional dict mapping protospacer → on-target efficiency score.
        sort_by: Sort criterion — "composite", "cfd_max", "offtarget_count", or "on_target".

    Returns:
        ToolResult with CandidateGuide rows sorted by the chosen criterion.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not guides:
        return ToolResult(tool="rank_candidates", errors=["No candidate guides provided"])

    # Build candidate map
    candidate_map: dict[str, CandidateGuide] = {}
    for guide in guides:
        key = guide.protospacer or f"{guide.chrom}:{guide.start}"
        candidate_map[key] = CandidateGuide(
            chrom=guide.chrom,
            start=guide.start,
            end=guide.end,
            strand=guide.strand,
            protospacer=guide.protospacer,
            pam=guide.pam,
            pam_type=guide.pam_type,
        )

    # Attach on-target scores
    if on_target_scores:
        for key, cg in candidate_map.items():
            if key in on_target_scores:
                cg.on_target_score = on_target_scores[key]
                cg.evidence_sources.append("on_target_score")

    # Aggregate off-target evidence
    if off_targets:
        # Group off-targets by protospacer (or by matching)
        ot_by_spacer: dict[str, list[PAMSiteRow]] = {}
        for ot in off_targets:
            # Match off-target to guide by protospacer similarity
            # In practice, the off-target search uses the guide as query,
            # so all results belong to that guide
            for key in candidate_map:
                if key in ot_by_spacer:
                    ot_by_spacer[key].append(ot)
                else:
                    ot_by_spacer[key] = [ot]

        # For single-guide queries, assign all off-targets to that guide
        if len(candidate_map) == 1 and off_targets:
            key = list(candidate_map.keys())[0]
            ot_by_spacer[key] = off_targets

        for key, cands in ot_by_spacer.items():
            if key not in candidate_map:
                continue
            cg = candidate_map[key]
            cg.total_offtargets = len(cands)
            cg.evidence_sources.append("offtarget_search")

            cfd_scores = [c.cfd_score for c in cands if c.cfd_score is not None]
            if cfd_scores:
                cg.mean_cfd = round(sum(cfd_scores) / len(cfd_scores), 4)
                cg.max_cfd = round(max(cfd_scores), 4)
                cg.cfd_above_05_count = sum(1 for s in cfd_scores if s > 0.5)
                cg.cfd_above_01_count = sum(1 for s in cfd_scores if s > 0.1)
                cg.evidence_sources.append("score_offtargets")

            mismatch_counts = [c.mismatch_count for c in cands if c.mismatch_count is not None]
            if mismatch_counts:
                cg.max_mismatches_found = max(mismatch_counts)

    candidates = list(candidate_map.values())

    # Sort
    if sort_by == "cfd_max":
        candidates.sort(key=lambda c: -(c.max_cfd or 0))
    elif sort_by == "offtarget_count":
        candidates.sort(key=lambda c: c.total_offtargets)
    elif sort_by == "on_target":
        candidates.sort(key=lambda c: -(c.on_target_score or 0))
    elif sort_by == "composite":
        # Composite: lower CFD max + fewer off-targets = better
        # Sort by a transparent combination
        def _composite_key(c: CandidateGuide) -> tuple:
            return (
                -(c.max_cfd or 0),  # higher CFD max first (more concerning)
                c.total_offtargets,  # fewer off-targets first
                -(c.on_target_score or 0),
            )
        candidates.sort(key=_composite_key)
    else:
        warnings.append(f"Unknown sort_by '{sort_by}', using composite")
        candidates.sort(key=lambda c: (-(c.max_cfd or 0), c.total_offtargets))

    # Convert to PAMSiteRow for uniform output
    rows = []
    for cg in candidates:
        d = cg.to_dict()
        rows.append(PAMSiteRow(
            chrom=d["chrom"],
            start=d["start"],
            end=d["end"],
            strand=d["strand"],
            protospacer=d["protospacer"],
            pam=d["pam"],
            pam_type=d["pam_type"],
            mismatch_count=d["total_offtargets"],
            cfd_score=d["max_cfd"],
            rs2_score=d["rs2_score"],
        ))

    summary = {
        "total_candidates": len(candidates),
        "sort_by": sort_by,
        "ranking_note": (
            "Ranking uses transparent evidence aggregation, NOT a validated "
            "predictive model. Future VEYRA reasoning layers will refine rankings."
        ),
        "evidence_sources": list(set(
            s for c in candidates for s in c.evidence_sources
        )),
    }

    return ToolResult(
        tool="rank_candidates",
        rows=rows,
        summary=summary,
        errors=errors,
        warnings=warnings,
        metadata={
            "ranking_method": "transparent_aggregation",
            "validation_status": "NOT validated — evidence aggregation only",
        },
    )


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="VEYRA rank_candidates tool")
    parser.add_argument("--guides-json", required=True, help="JSON file with guide rows")
    parser.add_argument("--offtargets-json", default=None, help="JSON file with off-target rows")
    parser.add_argument("--on-target-json", default=None, help="JSON file with on-target scores")
    parser.add_argument("--sort-by", default="composite",
                        choices=["composite", "cfd_max", "offtarget_count", "on_target"])
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    with open(args.guides_json) as f:
        guides = [PAMSiteRow(**r) for r in json.load(f)]

    off_targets = None
    if args.offtargets_json:
        with open(args.offtargets_json) as f:
            off_targets = [PAMSiteRow(**r) for r in json.load(f)]

    on_target = None
    if args.on_target_json:
        with open(args.on_target_json) as f:
            on_target = json.load(f)

    result = rank_candidates(guides, off_targets, on_target, args.sort_by)
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
