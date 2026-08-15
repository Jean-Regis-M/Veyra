"""Core positional features service.

Wraps the MCP compute_positional_features tool into a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import (
    ComputePositionalFeaturesRequest,
    VeyraResult,
    ResultRow,
)
from mcp.tools.compute_positional_features import (
    compute_positional_features as _mcp_compute_pf,
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


def compute_positional_features(request: ComputePositionalFeaturesRequest) -> VeyraResult:
    """Compute positional nucleotide features for a spacer sequence.

    Args:
        request: ComputePositionalFeaturesRequest with sequence and parameters.

    Returns:
        VeyraResult with positional features.
    """
    result = _mcp_compute_pf(
        sequence=request.sequence,
        spacer_length=request.spacer_length,
        return_onehot=request.return_onehot,
        check_position20_bias=request.check_position20_bias,
        custom_check_positions=request.custom_check_positions,
        onehot_alphabet=request.onehot_alphabet,
    )
    return _convert_tool_result(result)
