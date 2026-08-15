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
    CheckHomopolymerRunsRequest,
    ComputeMeltingTempRequest,
    ComputeSecondaryStructureRequest,
    ComputePositionalFeaturesRequest,
    ComputeDinucleotideCompositionRequest,
    ComputeSeedGCRequest,
    ComputeOnTargetEfficiencyRequest,
    VeyraResult,
)
from core.pam import pam_scan as _core_pam_scan, pam_scan_region as _core_pam_scan_region
from core.ingestion import ingest
from core.offtarget import build_index, offtarget_search, score_offtargets
from core.ranking import rank_candidates
from core.gc import compute_gc_content as _core_compute_gc
from core.homopolymer import check_homopolymer_runs as _core_check_homopolymer
from core.tm import compute_melting_temp as _core_compute_tm
from core.ss import compute_secondary_structure as _core_compute_ss
from core.positional_features import compute_positional_features as _core_compute_pf
from core.dinucleotide import compute_dinucleotide_composition as _core_compute_dinuc
from core.seed_gc import compute_seed_gc as _core_compute_seed_gc
from core.ontarget import predict_ontarget_efficiency as _core_predict_ontarget
from core.model_runtime import (
    provision_model as _provision_model,
    verify_model as _verify_model,
    ensure_model_ready as _ensure_model_ready,
    get_model_status as _get_model_status,
    list_model_runtimes as _list_model_runtimes,
    get_model_spec as _get_model_spec,
    RuntimeState,
)
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
    return _core_pam_scan(request)


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
    return _core_pam_scan_region(request)


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
    backend: str = "bwa",
    max_dna_bulge: int = 0,
    max_rna_bulge: int = 0,
    search_scope: str = "genome",
    chrom: str | None = None,
    start: int | None = None,
    end: int | None = None,
    strand_search: str = "both",
    max_results: int = 1000,
    device: str = "auto",
) -> VeyraResult:
    """Search for off-target matches.

    Args:
        spacer_sequence: The guide/spacer sequence.
        genome_id: Genome identifier.
        pam_pattern: IUPAC PAM pattern.
        max_mismatches: Maximum mismatches allowed.
        allow_bulge: Allow bulges (uses cas_offinder backend).
        cas_variant: Cas variant name.
        backend: "bwa" or "cas_offinder".
        max_dna_bulge: Maximum DNA bulge size (cas_offinder only).
        max_rna_bulge: Maximum RNA bulge size (cas_offinder only).
        search_scope: "genome" or "region" (cas_offinder only).
        chrom: Chromosome name (required when search_scope="region").
        start: Start position, 1-based (required when search_scope="region").
        end: End position, exclusive (required when search_scope="region").
        strand_search: Filter by strand: "both", "fwd" (+), or "rev" (-).
        max_results: Maximum results to return. Truncates and sets results_truncated flag.
        device: Execution device. "auto" or "cpu". "gpu" is rejected for cas_offinder.

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
        backend=backend,
        max_dna_bulge=max_dna_bulge,
        max_rna_bulge=max_rna_bulge,
        search_scope=search_scope,
        chrom=chrom,
        start=start,
        end=end,
        strand_search=strand_search,
        max_results=max_results,
        device=device,
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


def check_homopolymer_runs(
    sequence: str,
    homopolymer_min_run: int = 4,
    polyT_strict: bool = True,
    polyG_strict: bool = False,
    check_bases: str = "ACGT",
    return_run_positions: bool = False,
) -> VeyraResult:
    """Check homopolymer runs in a DNA sequence.

    Args:
        sequence: DNA sequence (IUPAC characters allowed).
        homopolymer_min_run: Minimum run length to flag (>= 2).
        polyT_strict: If True, poly-T runs cause passes_filter=False.
        polyG_strict: If True, poly-G runs cause passes_filter=False.
        check_bases: Bases to scan for runs (subset of ACGT).
        return_run_positions: If True, include run position details.

    Returns:
        VeyraResult with homopolymer analysis.
    """
    request = CheckHomopolymerRunsRequest(
        sequence=sequence,
        homopolymer_min_run=homopolymer_min_run,
        polyT_strict=polyT_strict,
        polyG_strict=polyG_strict,
        check_bases=check_bases,
        return_run_positions=return_run_positions,
    )
    return _core_check_homopolymer(request)


def compute_melting_temp(
    sequence: str,
    tm_method: str = "nearest_neighbor",
    na_conc: float = 50.0,
    mg_conc: float = 0.0,
    primer_conc: float = 250.0,
    seed_region_length: int = 10,
    compute_seed_tm: bool = False,
    round_decimals: int = 2,
) -> VeyraResult:
    """Compute melting temperature for a DNA sequence.

    Args:
        sequence: DNA sequence (standard ACGT).
        tm_method: "nearest_neighbor", "wallace", or "gc_percent".
        na_conc: Na+ concentration in mM.
        mg_conc: Mg2+ concentration in mM.
        primer_conc: Primer concentration in nM.
        seed_region_length: Length of seed region for seed Tm.
        compute_seed_tm: Whether to compute Tm for the 3' seed region.
        round_decimals: Decimal places for rounding.

    Returns:
        VeyraResult with melting temperature.
    """
    request = ComputeMeltingTempRequest(
        sequence=sequence,
        tm_method=tm_method,
        na_conc=na_conc,
        mg_conc=mg_conc,
        primer_conc=primer_conc,
        seed_region_length=seed_region_length,
        compute_seed_tm=compute_seed_tm,
        round_decimals=round_decimals,
    )
    return _core_compute_tm(request)


def compute_secondary_structure(
    sequence: str,
    mfe_include_scaffold: bool = False,
    scaffold_sequence: str = "",
    temperature_celsius: float = 37.0,
    return_structure_string: bool = False,
    mfe_threshold: float = -5.0,
) -> VeyraResult:
    """Compute secondary structure / MFE for a DNA sequence.

    Args:
        sequence: DNA sequence (standard ACGT).
        mfe_include_scaffold: If True, fold sequence + scaffold together.
        scaffold_sequence: Scaffold RNA sequence (required when mfe_include_scaffold=True).
        temperature_celsius: Folding temperature in °C.
        return_structure_string: If True, include dot-bracket structure.
        mfe_threshold: MFE threshold for pass/fail filter.

    Returns:
        VeyraResult with MFE and optional structure.
    """
    request = ComputeSecondaryStructureRequest(
        sequence=sequence,
        mfe_include_scaffold=mfe_include_scaffold,
        scaffold_sequence=scaffold_sequence,
        temperature_celsius=temperature_celsius,
        return_structure_string=return_structure_string,
        mfe_threshold=mfe_threshold,
    )
    return _core_compute_ss(request)


def compute_positional_features(
    sequence: str,
    spacer_length: int = 20,
    return_onehot: bool = True,
    check_position20_bias: bool = True,
    custom_check_positions: list[int] | None = None,
    onehot_alphabet: str = "ACGT",
) -> VeyraResult:
    """Compute positional nucleotide features for a spacer sequence.

    Args:
        sequence: DNA sequence (already in scoring orientation).
        spacer_length: Expected spacer length (default 20 for SpCas9).
        return_onehot: Whether to include per-position one-hot encoding.
        check_position20_bias: Whether to check position-20 PAM-proximal bias.
        custom_check_positions: Optional list of 1-based positions to extract.
        onehot_alphabet: Alphabet for one-hot encoding (default "ACGT").

    Returns:
        VeyraResult with positional features.
    """
    if custom_check_positions is None:
        custom_check_positions = []
    request = ComputePositionalFeaturesRequest(
        sequence=sequence,
        spacer_length=spacer_length,
        return_onehot=return_onehot,
        check_position20_bias=check_position20_bias,
        custom_check_positions=custom_check_positions,
        onehot_alphabet=onehot_alphabet,
    )
    return _core_compute_pf(request)


def compute_dinucleotide_composition(
    sequence: str,
    spacer_length: int = 20,
    window_size: int = 2,
    return_full_matrix: bool = False,
    normalize_counts: bool = False,
    target_dinucleotides: list[str] | None = None,
) -> VeyraResult:
    """Compute dinucleotide composition for a spacer sequence.

    Args:
        sequence: DNA sequence (already in scoring orientation).
        spacer_length: Expected spacer length (default 20 for SpCas9).
        window_size: k-mer window size (default 2 for dinucleotides).
        return_full_matrix: Whether to include per-position anchored rows.
        normalize_counts: Whether to include normalized frequencies.
        target_dinucleotides: Optional list of specific k-mers to report.

    Returns:
        VeyraResult with dinucleotide composition features.
    """
    if target_dinucleotides is None:
        target_dinucleotides = []
    request = ComputeDinucleotideCompositionRequest(
        sequence=sequence,
        spacer_length=spacer_length,
        window_size=window_size,
        return_full_matrix=return_full_matrix,
        normalize_counts=normalize_counts,
        target_dinucleotides=target_dinucleotides,
    )
    return _core_compute_dinuc(request)


def compute_seed_gc(
    sequence: str,
    seed_region_length: int = 10,
    seed_anchor: str = "pam_proximal",
    seed_min_threshold: float = 0.20,
    seed_max_threshold: float = 0.80,
    compute_seed_distal_delta: bool = False,
    round_decimals: int = 3,
) -> VeyraResult:
    """Compute PAM-proximal seed GC content for a spacer sequence.

    Args:
        sequence: DNA sequence (already in scoring orientation).
        seed_region_length: Length of the seed region (default 10).
        seed_anchor: Anchor point for seed extraction ("pam_proximal").
        seed_min_threshold: Minimum GC fraction for pass filter.
        seed_max_threshold: Maximum GC fraction for pass filter.
        compute_seed_distal_delta: Whether to compute distal GC and delta.
        round_decimals: Decimal places for rounding output values.

    Returns:
        VeyraResult with seed GC features.
    """
    request = ComputeSeedGCRequest(
        sequence=sequence,
        seed_region_length=seed_region_length,
        seed_anchor=seed_anchor,
        seed_min_threshold=seed_min_threshold,
        seed_max_threshold=seed_max_threshold,
        compute_seed_distal_delta=compute_seed_distal_delta,
        round_decimals=round_decimals,
    )
    return _core_compute_seed_gc(request)


def analyze_mismatch_seed(
    spacer_sequence: str,
    candidate_sequence: str,
    bulge_type: str = "X",
    bulge_size: int = 0,
    bulge_position: int | None = None,
    aligned_guide: str | None = None,
    aligned_candidate: str | None = None,
    seed_region_length: int = 10,
    pam_pattern: str = "NGG",
) -> VeyraResult:
    """Analyze mismatches and bulges in the seed region of an off-target candidate.

    Args:
        spacer_sequence: The wild-type guide/spacer sequence (20nt).
        candidate_sequence: The candidate off-target sequence.
        bulge_type: "X" (no bulge), "DNA", or "RNA".
        bulge_size: Size of the bulge (0 for no bulge).
        bulge_position: Position of the bulge in the alignment (0-based).
        aligned_guide: Aligned guide sequence with gaps (from Cas-OFFinder).
        aligned_candidate: Aligned candidate sequence with gaps (from Cas-OFFinder).
        seed_region_length: Length of the seed region (default 10).
        pam_pattern: PAM pattern for context.

    Returns:
        VeyraResult with seed analysis summary.
    """
    from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed as _mcp_analyze
    result = _mcp_analyze(
        spacer_sequence=spacer_sequence,
        candidate_sequence=candidate_sequence,
        bulge_type=bulge_type,
        bulge_size=bulge_size,
        bulge_position=bulge_position,
        aligned_guide=aligned_guide,
        aligned_candidate=aligned_candidate,
        seed_region_length=seed_region_length,
        pam_pattern=pam_pattern,
    )
    return VeyraResult(
        tool=result.tool,
        rows=[],
        summary=result.summary,
        errors=result.errors,
        warnings=result.warnings,
        metadata=result.metadata,
    )


def compute_cut_site(
    spacer_start: int,
    spacer_length: int = 20,
    strand: str = "+",
    pam_position: str = "3prime",
    cut_offset_from_pam: int = -3,
    return_genomic_coord: bool = True,
    return_relative_coord: bool = True,
    chrom: str = "",
) -> VeyraResult:
    """Compute canonical SpCas9 cleavage-site position.

    Deterministic coordinate/geometry tool. Reports a predicted canonical
    SpCas9 cleavage anchor — NOT cleavage efficiency, NOT repair outcome.

    Args:
        spacer_start: 0-based start coordinate of the protospacer.
        spacer_length: Length of the protospacer (default 20).
        strand: "+" or "-" indicating which strand the guide targets.
        pam_position: PAM orientation (currently only "3prime" supported).
        cut_offset_from_pam: Offset from PAM start to cleavage boundary.
        return_genomic_coord: Whether to compute absolute genomic coordinate.
        return_relative_coord: Whether to compute spacer-relative cut position.
        chrom: Chromosome label (required when return_genomic_coord=True).

    Returns:
        VeyraResult with cut_site_genomic, cut_site_relative, and metadata.
    """
    from core.cut_site import compute_cut_site as _core_cut_site
    from schemas.canonical import ComputeCutSiteRequest

    request = ComputeCutSiteRequest(
        spacer_start=spacer_start,
        spacer_length=spacer_length,
        strand=strand,
        pam_position=pam_position,
        cut_offset_from_pam=cut_offset_from_pam,
        return_genomic_coord=return_genomic_coord,
        return_relative_coord=return_relative_coord,
        chrom=chrom,
    )
    return _core_cut_site(request)


def predict_ontarget_efficiency(
    context_sequence: str,
    model: str = "rule_set_2",
    context_upstream: int = 4,
    context_downstream: int = 3,
    spacer_length: int = 20,
    normalize_score: bool = False,
    round_decimals: int = 3,
    precomputed_features: dict | None = None,
) -> VeyraResult:
    """Predict on-target SpCas9 efficiency.
    
    This is fundamentally different from CFD/off-target specificity.
    It answers: "How efficiently is this intended guide expected to cut?"
    
    Available models:
    - rule_set_2: Doench 2016 / Fusi / Azimuth (AdaBoost, 0-1 scale)
    - rule_set_3: NOT IMPLEMENTED (model files not available)
    - both: Run both independently (Rule Set 3 will be null)
    
    Args:
        context_sequence: Full context sequence (upstream + spacer + PAM + downstream).
        model: "rule_set_2", "rule_set_3", or "both".
        context_upstream: Number of nucleotides upstream of spacer.
        context_downstream: Number of nucleotides downstream of PAM.
        spacer_length: Length of the spacer/protospacer.
        normalize_score: Whether to normalize score to [0,1].
        round_decimals: Decimal places for rounding output values.
        precomputed_features: Optional precomputed features to reuse.
    
    Returns:
        VeyraResult with on-target efficiency scores.
    """
    request = ComputeOnTargetEfficiencyRequest(
        context_sequence=context_sequence,
        model=model,
        context_upstream=context_upstream,
        context_downstream=context_downstream,
        spacer_length=spacer_length,
        normalize_score=normalize_score,
        round_decimals=round_decimals,
        precomputed_features=precomputed_features,
    )
    return _core_predict_ontarget(request)


__all__ = [
    "ingest_file",
    "pam_scan_raw",
    "pam_scan_region",
    "build_offtarget_index",
    "search_offtargets",
    "score_offtargets_cfd",
    "rank_guides",
    "compute_gc_content",
    "check_homopolymer_runs",
    "compute_melting_temp",
    "compute_secondary_structure",
    "compute_positional_features",
     "compute_dinucleotide_composition",
    "compute_seed_gc",
    "analyze_mismatch_seed",
    "compute_cut_site",
    "predict_ontarget_efficiency",
    "get_genomes",
    "get_genome_info",
    "get_cache_info",
    "clear_cache",
    # Model runtime management
    "provision_model",
    "verify_model",
    "ensure_model_ready",
    "get_model_status",
    "list_model_runtimes",
    "get_model_spec",
    "RuntimeState",
    "get_model_registry",
    "get_model_info",
    "select_model",
    "VeyraResult",
]


def provision_model(model_id: str, force: bool = False) -> dict:
    """Provision an isolated runtime for a model.

    Creates a virtualenv under data/model_envs/<model_id>/ and installs
    the model's required dependencies.

    Args:
        model_id: Model to provision (rule_set_2, rule_set_3, doench_2014)
        force: If True, recreate even if runtime exists

    Returns:
        Dict with provisioning outcome (action, runtime_status, runtime_path, etc.)
    """
    return _provision_model(model_id, force=force)


def verify_model(model_id: str) -> dict:
    """Verify a model runtime with health check.

    Args:
        model_id: Model to verify

    Returns:
        Dict with verification result (pass/fail, error details)
    """
    return _verify_model(model_id)


def ensure_model_ready(model_id: str) -> tuple[str | None, dict]:
    """Ensure a model is ready for use, provisioning if needed.

    Args:
        model_id: Model to check/provision

    Returns:
        (model_id_or_none, status_dict)
    """
    return _ensure_model_ready(model_id)


def get_model_status(model_id: str) -> dict:
    """Get the runtime status for a model.

    Args:
        model_id: Model identifier

    Returns:
        Dict with state, runtime_path, python_version, dependency_status, verification_status
    """
    return _get_model_status(model_id)


def list_model_runtimes() -> list[dict]:
    """List all model runtime states.

    Returns:
        List of runtime status dicts for all models
    """
    return _list_model_runtimes()


def get_model_spec(model_id: str) -> dict | None:
    """Get the trusted specification for a model.

    Args:
        model_id: Model identifier

    Returns:
        Dict with model specification (dependencies, resources, verification case, etc.)
    """
    return _get_model_spec(model_id)
