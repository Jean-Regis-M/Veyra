"""VEYRA Python API.

Provides programmatic access to all VEYRA functionality.
All functions call the same core services used by CLI, HTTP, and MCP.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import (
    IngestRequest,
    PamScanRequest,
    PamScanRegionRequest,
    BuildIndexRequest,
    OfftargetSearchRequest,
    ScoreOfftargetsRequest,
    RankCandidatesRequest,
    ComputeGCContentRequest,
    VeyraResult,
)
from core.pam import pam_scan, pam_scan_region
from core.ingestion import ingest
from core.offtarget import build_index, offtarget_search, score_offtargets
from core.ranking import rank_candidates
from core.gc import compute_gc_content as _core_compute_gc
from core.genome import list_genomes, genome_info
from core.cache import cache_status, cache_clear


def ingest_file(
    input_path: str,
    pam_scan: bool = False,
    pam_names: list[str] | None = None,
) -> VeyraResult:
    """Ingest a genomic file.

    Args:
        input_path: Path to the input file.
        pam_scan: Enable PAM scanning.
        pam_names: Optional list of PAM types to scan for.

    Returns:
        VeyraResult with ingestion summary.
    """
    request = IngestRequest(
        input_path=input_path,
        pam_scan=pam_scan,
        pam_names=pam_names,
    )
    return ingest(request)


def pam_scan_raw(
    sequence: str,
    pam_pattern: str = "NGG",
    protospacer_len: int = 20,
    strand: str = "both",
    chrom: str | None = None,
) -> VeyraResult:
    """Scan a raw DNA sequence for PAM sites.

    Args:
        sequence: DNA sequence to scan.
        pam_pattern: IUPAC PAM pattern.
        protospacer_len: Protospacer length.
        strand: "both", "fwd", or "rev".
        chrom: Optional chromosome name.

    Returns:
        VeyraResult with PAM sites.
    """
    request = PamScanRequest(
        sequence=sequence,
        pam_pattern=pam_pattern,
        protospacer_len=protospacer_len,
        strand=strand,
        chrom=chrom,
    )
    return pam_scan(request)


def pam_scan_region(
    genome_id: str,
    chrom: str,
    start: int,
    end: int,
    pam_pattern: str = "NGG",
    protospacer_len: int = 20,
    strand: str = "both",
) -> VeyraResult:
    """Scan a genomic region for PAM sites.

    Args:
        genome_id: Genome identifier.
        chrom: Chromosome name.
        start: Start position (1-based).
        end: End position (exclusive).
        pam_pattern: IUPAC PAM pattern.
        protospacer_len: Protospacer length.
        strand: "both", "fwd", or "rev".

    Returns:
        VeyraResult with PAM sites.
    """
    request = PamScanRegionRequest(
        genome_id=genome_id,
        chrom=chrom,
        start=start,
        end=end,
        pam_pattern=pam_pattern,
        protospacer_len=protospacer_len,
        strand=strand,
    )
    return pam_scan_region(request)


def build_offtarget_index(
    genome_id: str,
    cas_variant: str = "SpCas9",
    force_rebuild: bool = False,
) -> VeyraResult:
    """Build or retrieve a cached BWA index.

    Args:
        genome_id: Genome identifier.
        cas_variant: Cas variant name.
        force_rebuild: Force rebuild even if cached.

    Returns:
        VeyraResult with index metadata.
    """
    request = BuildIndexRequest(
        genome_id=genome_id,
        cas_variant=cas_variant,
        force_rebuild=force_rebuild,
    )
    return build_index(request)


def search_offtargets(
    spacer_sequence: str,
    genome_id: str,
    pam_pattern: str = "NGG",
    max_mismatches: int = 4,
    allow_bulge: bool = False,
    cas_variant: str = "SpCas9",
) -> VeyraResult:
    """Search for off-target matches.

    Args:
        spacer_sequence: The guide/spacer sequence.
        genome_id: Genome identifier.
        pam_pattern: IUPAC PAM pattern.
        max_mismatches: Maximum mismatches allowed.
        allow_bulge: Allow bulges (not yet supported).
        cas_variant: Cas variant name.

    Returns:
        VeyraResult with off-target candidates.
    """
    request = OfftargetSearchRequest(
        spacer_sequence=spacer_sequence,
        genome_id=genome_id,
        pam_pattern=pam_pattern,
        max_mismatches=max_mismatches,
        allow_bulge=allow_bulge,
        cas_variant=cas_variant,
    )
    return offtarget_search(request)


def score_offtargets_cfd(
    spacer_sequence: str,
    candidates: list[dict],
    pam_pattern: str = "NGG",
) -> VeyraResult:
    """Score off-target candidates using CFD.

    Args:
        spacer_sequence: The wild-type spacer sequence.
        candidates: List of candidate dictionaries.
        pam_pattern: PAM pattern used.

    Returns:
        VeyraResult with scored candidates.
    """
    request = ScoreOfftargetsRequest(
        spacer_sequence=spacer_sequence,
        candidates=candidates,
        pam_pattern=pam_pattern,
    )
    return score_offtargets(request)


def rank_guides(
    guides: list[dict],
    off_targets: list[dict] | None = None,
    on_target_scores: dict[str, float] | None = None,
    sort_by: str = "composite",
) -> VeyraResult:
    """Rank candidate guides.

    Args:
        guides: List of guide dictionaries.
        off_targets: Optional off-target results.
        on_target_scores: Optional on-target scores.
        sort_by: Sort criterion.

    Returns:
        VeyraResult with ranked candidates.
    """
    request = RankCandidatesRequest(
        guides=guides,
        off_targets=off_targets,
        on_target_scores=on_target_scores,
        sort_by=sort_by,
    )
    return rank_candidates(request)


def get_genomes() -> VeyraResult:
    """List all registered genomes.

    Returns:
        VeyraResult with genome list.
    """
    return list_genomes()


def get_genome_info(genome_id: str) -> VeyraResult:
    """Get information about a genome.

    Args:
        genome_id: The genome identifier.

    Returns:
        VeyraResult with genome details.
    """
    return genome_info(genome_id)


def get_cache_info(tool_name: str | None = None) -> VeyraResult:
    """Get cache status.

    Args:
        tool_name: Optional tool name to filter by.

    Returns:
        VeyraResult with cache statistics.
    """
    return cache_status(tool_name=tool_name)


def clear_cache(tool_name: str | None = None) -> VeyraResult:
    """Clear cache entries.

    Args:
        tool_name: Optional tool name to clear.

    Returns:
        VeyraResult with clear results.
    """
    return cache_clear(tool_name=tool_name)


def compute_gc_content(
    sequence: str,
    gc_window_size: int = 5,
    gc_split_ratio: float = 0.5,
    gc_min_threshold: float = 0.20,
    gc_max_threshold: float = 0.80,
    include_sliding_window: bool = True,
    include_half_split: bool = True,
    round_decimals: int = 3,
) -> VeyraResult:
    """Compute GC content for a DNA sequence.

    Args:
        sequence: DNA sequence (IUPAC characters allowed).
        gc_window_size: Sliding window size in nucleotides.
        gc_split_ratio: Fraction of sequence for 5' half (0–1).
        gc_min_threshold: Minimum GC for pass filter.
        gc_max_threshold: Maximum GC for pass filter.
        include_sliding_window: Whether to compute sliding-window GC.
        include_half_split: Whether to compute 5'/3' split GC.
        round_decimals: Decimal places for rounding.

    Returns:
        VeyraResult with GC content features.
    """
    request = ComputeGCContentRequest(
        sequence=sequence,
        gc_window_size=gc_window_size,
        gc_split_ratio=gc_split_ratio,
        gc_min_threshold=gc_min_threshold,
        gc_max_threshold=gc_max_threshold,
        include_sliding_window=include_sliding_window,
        include_half_split=include_half_split,
        round_decimals=round_decimals,
    )
    return _core_compute_gc(request)


__all__ = [
    "ingest_file",
    "pam_scan_raw",
    "pam_scan_region",
    "build_offtarget_index",
    "search_offtargets",
    "score_offtargets_cfd",
    "rank_guides",
    "compute_gc_content",
    "get_genomes",
    "get_genome_info",
    "get_cache_info",
    "clear_cache",
    "VeyraResult",
]
