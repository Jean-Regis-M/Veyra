"""Core PAM scanning service.

Wraps the existing MCP PAM scanning tools into a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import (
    PamScanRequest,
    PamScanRegionRequest,
    VeyraResult,
    ResultRow,
)
from mcp.tools.pam_scan import pam_scan as _mcp_pam_scan
from mcp.tools.pam_scan_region import pam_scan_region as _mcp_pam_scan_region


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


def pam_scan(request: PamScanRequest) -> VeyraResult:
    """Scan a raw DNA sequence for PAM sites.

    Args:
        request: PamScanRequest with sequence, pam_pattern, etc.

    Returns:
        VeyraResult with PAM sites.
    """
    result = _mcp_pam_scan(
        sequence=request.sequence,
        pam_pattern=request.pam_pattern,
        protospacer_len=request.protospacer_len,
        strand=request.strand,
        chrom=request.chrom,
    )
    return _convert_tool_result(result)


def pam_scan_region(request: PamScanRegionRequest) -> VeyraResult:
    """Scan a genomic region for PAM sites.

    Args:
        request: PamScanRegionRequest with genome_id, chrom, start, end, etc.

    Returns:
        VeyraResult with PAM sites.
    """
    result = _mcp_pam_scan_region(
        genome_id=request.genome_id,
        chrom=request.chrom,
        start=request.start,
        end=request.end,
        pam_pattern=request.pam_pattern,
        protospacer_len=request.protospacer_len,
        strand=request.strand,
    )
    return _convert_tool_result(result)
