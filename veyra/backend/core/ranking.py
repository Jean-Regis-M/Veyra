"""Core ranking service.

Wraps the existing MCP ranking tool into a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import RankCandidatesRequest, VeyraResult, ResultRow
from mcp.tools.rank_candidates import rank_candidates as _mcp_rank_candidates
from mcp.schemas import PAMSiteRow


def _convert_tool_result(tool_result) -> VeyraResult:
    """Convert MCP ToolResult to canonical VeyraResult."""
    return VeyraResult(
        tool=tool_result.tool,
        rows=[
            ResultRow(
                chrom=r.chrom,
                start=r.start,
                end=r.end,
                strand=r.strand,
                protospacer=r.protospacer,
                pam=r.pam,
                pam_type=r.pam_type,
                mismatch_count=r.mismatch_count,
                mismatch_positions=r.mismatch_positions,
                cfd_score=r.cfd_score,
                rs2_score=r.rs2_score,
            )
            for r in tool_result.rows
        ],
        summary=tool_result.summary,
        errors=tool_result.errors,
        warnings=tool_result.warnings,
        metadata=tool_result.metadata,
    )


def rank_candidates(request: RankCandidatesRequest) -> VeyraResult:
    """Rank candidate guides based on off-target evidence.

    Args:
        request: RankCandidatesRequest with guides, off_targets, etc.

    Returns:
        VeyraResult with ranked candidates.
    """
    guides = [
        PAMSiteRow(**g) if isinstance(g, dict) else g
        for g in request.guides
    ]
    off_targets = None
    if request.off_targets:
        off_targets = [
            PAMSiteRow(**ot) if isinstance(ot, dict) else ot
            for ot in request.off_targets
        ]

    result = _mcp_rank_candidates(
        guides=guides,
        off_targets=off_targets,
        on_target_scores=request.on_target_scores,
        sort_by=request.sort_by,
    )
    return _convert_tool_result(result)
