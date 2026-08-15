"""Core secondary structure service.

Wraps the MCP compute_secondary_structure tool into a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import (
    ComputeSecondaryStructureRequest,
    VeyraResult,
    ResultRow,
)
from mcp.tools.compute_secondary_structure import (
    compute_secondary_structure as _mcp_compute_ss,
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


def compute_secondary_structure(request: ComputeSecondaryStructureRequest) -> VeyraResult:
    """Compute secondary structure / MFE for a DNA sequence.

    Args:
        request: ComputeSecondaryStructureRequest with sequence and parameters.

    Returns:
        VeyraResult with MFE and optional structure.
    """
    result = _mcp_compute_ss(
        sequence=request.sequence,
        mfe_include_scaffold=request.mfe_include_scaffold,
        scaffold_sequence=request.scaffold_sequence,
        temperature_celsius=request.temperature_celsius,
        return_structure_string=request.return_structure_string,
        mfe_threshold=request.mfe_threshold,
    )
    return _convert_tool_result(result)
