"""Core homopolymer service.

Wraps the MCP check_homopolymer_runs tool into a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import (
    CheckHomopolymerRunsRequest,
    VeyraResult,
    ResultRow,
)
from mcp.tools.check_homopolymer_runs import check_homopolymer_runs as _mcp_check_homopolymer


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


def check_homopolymer_runs(request: CheckHomopolymerRunsRequest) -> VeyraResult:
    """Check homopolymer runs in a DNA sequence.

    Args:
        request: CheckHomopolymerRunsRequest with sequence and parameters.

    Returns:
        VeyraResult with homopolymer analysis.
    """
    result = _mcp_check_homopolymer(
        sequence=request.sequence,
        homopolymer_min_run=request.homopolymer_min_run,
        polyT_strict=request.polyT_strict,
        polyG_strict=request.polyG_strict,
        check_bases=request.check_bases,
        return_run_positions=request.return_run_positions,
    )
    return _convert_tool_result(result)
