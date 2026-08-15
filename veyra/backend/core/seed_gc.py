"""Core seed GC service.

Wraps the MCP compute_seed_gc tool into a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import (
    ComputeSeedGCRequest,
    VeyraResult,
    ResultRow,
)
from mcp.tools.compute_seed_gc import compute_seed_gc as _mcp_compute_seed_gc


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


def compute_seed_gc(request: ComputeSeedGCRequest) -> VeyraResult:
    """Compute PAM-proximal seed GC content for a spacer sequence.

    Args:
        request: ComputeSeedGCRequest with sequence and parameters.

    Returns:
        VeyraResult with seed GC features.
    """
    result = _mcp_compute_seed_gc(
        sequence=request.sequence,
        seed_region_length=request.seed_region_length,
        seed_anchor=request.seed_anchor,
        seed_min_threshold=request.seed_min_threshold,
        seed_max_threshold=request.seed_max_threshold,
        compute_seed_distal_delta=request.compute_seed_distal_delta,
        round_decimals=request.round_decimals,
    )
    return _convert_tool_result(result)
