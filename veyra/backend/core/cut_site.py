"""Core cut-site service.

Wraps the MCP compute_cut_site tool into a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import (
    ComputeCutSiteRequest,
    VeyraResult,
    ResultRow,
)
from mcp.tools.compute_cut_site import compute_cut_site as _mcp_compute_cut_site


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
                bulge_type=r.bulge_type,
                bulge_size=r.bulge_size,
                bulge_position=r.bulge_position,
                aligned_guide=r.aligned_guide,
                aligned_candidate=r.aligned_candidate,
                cfd_status=r.cfd_status,
            )
            for r in tool_result.rows
        ],
        summary=tool_result.summary,
        errors=tool_result.errors,
        warnings=tool_result.warnings,
        metadata=tool_result.metadata,
    )


def compute_cut_site(request: ComputeCutSiteRequest) -> VeyraResult:
    """Compute canonical SpCas9 cleavage-site position.

    This is a deterministic coordinate/geometry tool. It reports a predicted
    canonical SpCas9 cleavage anchor — NOT cleavage efficiency, NOT repair
    outcome, NOT experimental certainty.

    Args:
        request: ComputeCutSiteRequest with coordinate parameters.

    Returns:
        VeyraResult with cut_site_genomic, cut_site_relative, and metadata.
    """
    result = _mcp_compute_cut_site(
        spacer_start=request.spacer_start,
        spacer_length=request.spacer_length,
        strand=request.strand,
        pam_position=request.pam_position,
        cut_offset_from_pam=request.cut_offset_from_pam,
        return_genomic_coord=request.return_genomic_coord,
        return_relative_coord=request.return_relative_coord,
        chrom=request.chrom,
    )
    return _convert_tool_result(result)
