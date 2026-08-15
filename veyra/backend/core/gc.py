"""Core GC content service.

Wraps the MCP compute_gc_content tool into a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import (
    ComputeGCContentRequest,
    VeyraResult,
    ResultRow,
)
from mcp.tools.compute_gc_content import compute_gc_content as _mcp_compute_gc


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


def compute_gc_content(request: ComputeGCContentRequest) -> VeyraResult:
    """Compute GC content for a DNA sequence.

    Args:
        request: ComputeGCContentRequest with sequence and parameters.

    Returns:
        VeyraResult with GC content features.
    """
    result = _mcp_compute_gc(
        sequence=request.sequence,
        gc_window_size=request.gc_window_size,
        gc_split_ratio=request.gc_split_ratio,
        gc_min_threshold=request.gc_min_threshold,
        gc_max_threshold=request.gc_max_threshold,
        include_sliding_window=request.include_sliding_window,
        include_half_split=request.include_half_split,
        round_decimals=request.round_decimals,
    )
    return _convert_tool_result(result)
