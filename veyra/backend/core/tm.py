"""Core melting temperature service.

Wraps the MCP compute_melting_temp tool into a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import (
    ComputeMeltingTempRequest,
    VeyraResult,
    ResultRow,
)
from mcp.tools.compute_melting_temp import compute_melting_temp as _mcp_compute_tm


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


def compute_melting_temp(request: ComputeMeltingTempRequest) -> VeyraResult:
    """Compute melting temperature for a DNA sequence.

    Args:
        request: ComputeMeltingTempRequest with sequence and parameters.

    Returns:
        VeyraResult with melting temperature.
    """
    result = _mcp_compute_tm(
        sequence=request.sequence,
        tm_method=request.tm_method,
        na_conc=request.na_conc,
        mg_conc=request.mg_conc,
        primer_conc=request.primer_conc,
        seed_region_length=request.seed_region_length,
        compute_seed_tm=request.compute_seed_tm,
        round_decimals=request.round_decimals,
    )
    return _convert_tool_result(result)
