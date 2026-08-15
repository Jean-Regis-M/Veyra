"""Core dinucleotide composition service.

Wraps the MCP compute_dinucleotide_composition tool into a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import (
    ComputeDinucleotideCompositionRequest,
    VeyraResult,
    ResultRow,
)
from mcp.tools.compute_dinucleotide_composition import (
    compute_dinucleotide_composition as _mcp_compute_dinuc,
)


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


def compute_dinucleotide_composition(request: ComputeDinucleotideCompositionRequest) -> VeyraResult:
    """Compute dinucleotide composition for a spacer sequence.

    Args:
        request: ComputeDinucleotideCompositionRequest with sequence and parameters.

    Returns:
        VeyraResult with dinucleotide composition features.
    """
    result = _mcp_compute_dinuc(
        sequence=request.sequence,
        spacer_length=request.spacer_length,
        window_size=request.window_size,
        return_full_matrix=request.return_full_matrix,
        normalize_counts=request.normalize_counts,
        target_dinucleotides=request.target_dinucleotides,
    )
    return _convert_tool_result(result)
