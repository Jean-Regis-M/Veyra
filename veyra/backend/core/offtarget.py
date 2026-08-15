"""Core off-target service.

Wraps the existing MCP off-target tools into a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import (
    BuildIndexRequest,
    OfftargetSearchRequest,
    ScoreOfftargetsRequest,
    VeyraResult,
    ResultRow,
)
from mcp.tools.build_offtarget_index import build_offtarget_index as _mcp_build_index
from mcp.tools.offtarget_search import offtarget_search as _mcp_offtarget_search
from mcp.tools.score_offtargets import score_offtargets as _mcp_score_offtargets
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


def build_index(request: BuildIndexRequest) -> VeyraResult:
    """Build or retrieve a cached BWA index.

    Args:
        request: BuildIndexRequest with genome_id, cas_variant, force_rebuild.

    Returns:
        VeyraResult with index metadata.
    """
    result = _mcp_build_index(
        genome_id=request.genome_id,
        cas_variant=request.cas_variant,
        force_rebuild=request.force_rebuild,
    )
    return _convert_tool_result(result)


def offtarget_search(request: OfftargetSearchRequest) -> VeyraResult:
    """Search for off-target matches.

    Args:
        request: OfftargetSearchRequest with spacer_sequence, genome_id, etc.

    Returns:
        VeyraResult with off-target candidates.
    """
    result = _mcp_offtarget_search(
        spacer_sequence=request.spacer_sequence,
        genome_id=request.genome_id,
        pam_pattern=request.pam_pattern,
        max_mismatches=request.max_mismatches,
        allow_bulge=request.allow_bulge,
        cas_variant=request.cas_variant,
        backend=request.backend,
        max_dna_bulge=request.max_dna_bulge,
        max_rna_bulge=request.max_rna_bulge,
        search_scope=request.search_scope,
        chrom=request.chrom,
        start=request.start,
        end=request.end,
    )
    return _convert_tool_result(result)


def score_offtargets(request: ScoreOfftargetsRequest) -> VeyraResult:
    """Score off-target candidates using CFD.

    Args:
        request: ScoreOfftargetsRequest with spacer_sequence, candidates, pam_pattern.

    Returns:
        VeyraResult with scored candidates.
    """
    candidates = [
        PAMSiteRow(**c) if isinstance(c, dict) else c
        for c in request.candidates
    ]
    result = _mcp_score_offtargets(
        spacer_sequence=request.spacer_sequence,
        candidates=candidates,
        pam_pattern=request.pam_pattern,
    )
    return _convert_tool_result(result)
