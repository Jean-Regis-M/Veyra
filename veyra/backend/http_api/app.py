"""VEYRA FastAPI HTTP API.

Provides REST endpoints for all VEYRA functionality.
All endpoints call the same core services used by CLI, MCP, and Python API.

Usage:
    uvicorn http.app:app --host 0.0.0.0 --port 8000
    python -m http.app
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Any, Optional

app = FastAPI(
    title="VEYRA API",
    description="VEYRA Genomic Intelligence Backend — HTTP API",
    version="0.1.0",
)


# ============================================================================
# Pydantic request/response models
# ============================================================================

class IngestRequestModel(BaseModel):
    input_path: str
    pam_scan: bool = False
    pam_names: Optional[list[str]] = None


class PamScanRequestModel(BaseModel):
    sequence: str
    pam_pattern: str = "NGG"
    protospacer_len: int = 20
    strand: str = "both"
    chrom: Optional[str] = None


class PamScanRegionRequestModel(BaseModel):
    genome_id: str
    chrom: str
    start: int
    end: int
    pam_pattern: str = "NGG"
    protospacer_len: int = 20
    strand: str = "both"


class BuildIndexRequestModel(BaseModel):
    genome_id: str
    cas_variant: str = "SpCas9"
    force_rebuild: bool = False


class OfftargetSearchRequestModel(BaseModel):
    spacer_sequence: str
    genome_id: str
    pam_pattern: str = "NGG"
    max_mismatches: int = 4
    allow_bulge: bool = False
    cas_variant: str = "SpCas9"
    backend: str = "bwa"
    max_dna_bulge: int = 0
    max_rna_bulge: int = 0
    search_scope: str = "genome"
    chrom: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None
    strand_search: str = "both"
    max_results: int = 1000
    device: str = "auto"


class ScoreOfftargetsRequestModel(BaseModel):
    spacer_sequence: str
    candidates: list[dict[str, Any]] = []
    pam_pattern: str = "NGG"


class RankCandidatesRequestModel(BaseModel):
    guides: list[dict[str, Any]] = []
    off_targets: Optional[list[dict[str, Any]]] = None
    on_target_scores: Optional[dict[str, float]] = None
    sort_by: str = "composite"


class CacheClearRequestModel(BaseModel):
    tool_name: Optional[str] = None


class ComputeGCContentRequestModel(BaseModel):
    sequence: str
    gc_window_size: int = 5
    gc_split_ratio: float = 0.5
    gc_min_threshold: float = 0.20
    gc_max_threshold: float = 0.80
    include_sliding_window: bool = True
    include_half_split: bool = True
    round_decimals: int = 3


class CheckHomopolymerRunsRequestModel(BaseModel):
    sequence: str
    homopolymer_min_run: int = 4
    polyT_strict: bool = True
    polyG_strict: bool = False
    check_bases: str = "ACGT"
    return_run_positions: bool = False


class ComputeMeltingTempRequestModel(BaseModel):
    sequence: str
    tm_method: str = "nearest_neighbor"
    na_conc: float = 50.0
    mg_conc: float = 0.0
    primer_conc: float = 250.0
    seed_region_length: int = 10
    compute_seed_tm: bool = False
    round_decimals: int = 2


class ComputeSecondaryStructureRequestModel(BaseModel):
    sequence: str
    mfe_include_scaffold: bool = False
    scaffold_sequence: str = ""
    temperature_celsius: float = 37.0
    return_structure_string: bool = False
    mfe_threshold: float = -5.0


class ComputePositionalFeaturesRequestModel(BaseModel):
    sequence: str
    spacer_length: int = 20
    return_onehot: bool = True
    check_position20_bias: bool = True
    custom_check_positions: list[int] = []
    onehot_alphabet: str = "ACGT"


class ComputeDinucleotideCompositionRequestModel(BaseModel):
    sequence: str
    spacer_length: int = 20
    window_size: int = 2
    return_full_matrix: bool = False
    normalize_counts: bool = False
    target_dinucleotides: list[str] = []


class ComputeSeedGCRequestModel(BaseModel):
    sequence: str
    seed_region_length: int = 10
    seed_anchor: str = "pam_proximal"
    seed_min_threshold: float = 0.20
    seed_max_threshold: float = 0.80
    compute_seed_distal_delta: bool = False
    round_decimals: int = 3


class AnalyzeMismatchSeedRequestModel(BaseModel):
    spacer_sequence: str
    candidate_sequence: str
    bulge_type: str = "X"
    bulge_size: int = 0
    bulge_position: Optional[int] = None
    aligned_guide: Optional[str] = None
    aligned_candidate: Optional[str] = None
    seed_region_length: int = 10
    pam_pattern: str = "NGG"


class ComputeCutSiteRequestModel(BaseModel):
    spacer_start: int
    spacer_length: int = 20
    strand: str = "+"
    pam_position: str = "3prime"
    cut_offset_from_pam: int = -3
    return_genomic_coord: bool = True
    return_relative_coord: bool = True
    chrom: str = ""


class PredictOnTargetEfficiencyRequestModel(BaseModel):
    context_sequence: str
    model: str = "auto"
    context_upstream: int = 4
    context_downstream: int = 3
    spacer_length: int = 20
    normalize_score: bool = False
    round_decimals: int = 3
    precomputed_features: Optional[dict[str, Any]] = None


def _result_to_response(result) -> dict:
    """Convert VeyraResult to dict for JSON response."""
    return {
        "tool": result.tool,
        "rows": [r.to_dict() for r in result.rows],
        "summary": result.summary,
        "errors": result.errors,
        "warnings": result.warnings,
        "metadata": result.metadata,
    }


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "veyra"}


@app.post("/ingest")
async def ingest(request: IngestRequestModel):
    """Ingest a genomic file."""
    from core.ingestion import ingest
    from schemas.canonical import IngestRequest

    req = IngestRequest(
        input_path=request.input_path,
        pam_scan=request.pam_scan,
        pam_names=request.pam_names,
    )
    result = ingest(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/pam/scan")
async def pam_scan(request: PamScanRequestModel):
    """Scan a raw DNA sequence for PAM sites."""
    from core.pam import pam_scan
    from schemas.canonical import PamScanRequest

    req = PamScanRequest(
        sequence=request.sequence,
        pam_pattern=request.pam_pattern,
        protospacer_len=request.protospacer_len,
        strand=request.strand,
        chrom=request.chrom,
    )
    result = pam_scan(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/pam/scan-region")
async def pam_scan_region(request: PamScanRegionRequestModel):
    """Scan a genomic region for PAM sites."""
    from core.pam import pam_scan_region
    from schemas.canonical import PamScanRegionRequest

    req = PamScanRegionRequest(
        genome_id=request.genome_id,
        chrom=request.chrom,
        start=request.start,
        end=request.end,
        pam_pattern=request.pam_pattern,
        protospacer_len=request.protospacer_len,
        strand=request.strand,
    )
    result = pam_scan_region(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/index/build")
async def build_index(request: BuildIndexRequestModel):
    """Build or retrieve a cached BWA index."""
    from core.offtarget import build_index
    from schemas.canonical import BuildIndexRequest

    req = BuildIndexRequest(
        genome_id=request.genome_id,
        cas_variant=request.cas_variant,
        force_rebuild=request.force_rebuild,
    )
    result = build_index(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/offtarget/search")
async def offtarget_search(request: OfftargetSearchRequestModel):
    """Search for off-target matches."""
    from core.offtarget import offtarget_search
    from schemas.canonical import OfftargetSearchRequest

    req = OfftargetSearchRequest(
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
        strand_search=request.strand_search,
        max_results=request.max_results,
        device=request.device,
    )
    result = offtarget_search(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/offtarget/score")
async def score_offtargets(request: ScoreOfftargetsRequestModel):
    """Score off-target candidates using CFD."""
    from core.offtarget import score_offtargets
    from schemas.canonical import ScoreOfftargetsRequest

    req = ScoreOfftargetsRequest(
        spacer_sequence=request.spacer_sequence,
        candidates=request.candidates,
        pam_pattern=request.pam_pattern,
    )
    result = score_offtargets(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/rank")
async def rank_candidates(request: RankCandidatesRequestModel):
    """Rank candidate guides."""
    from core.ranking import rank_candidates
    from schemas.canonical import RankCandidatesRequest

    req = RankCandidatesRequest(
        guides=request.guides,
        off_targets=request.off_targets,
        on_target_scores=request.on_target_scores,
        sort_by=request.sort_by,
    )
    result = rank_candidates(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.get("/genomes")
async def list_genomes():
    """List all registered genomes."""
    from core.genome import list_genomes

    result = list_genomes()
    return _result_to_response(result)


@app.get("/genomes/{genome_id}")
async def get_genome_info(genome_id: str):
    """Get information about a genome."""
    from core.genome import genome_info

    result = genome_info(genome_id)
    if result.errors:
        raise HTTPException(status_code=404, detail={"errors": result.errors})
    return _result_to_response(result)


@app.get("/cache/status")
async def cache_status(tool_name: Optional[str] = None):
    """Get cache status."""
    from core.cache import cache_status

    result = cache_status(tool_name=tool_name)
    return _result_to_response(result)


@app.post("/cache/clear")
async def clear_cache(request: CacheClearRequestModel):
    """Clear cache entries."""
    from core.cache import cache_clear

    result = cache_clear(tool_name=request.tool_name)
    return _result_to_response(result)


@app.get("/tools")
async def list_tools():
    """List available tools."""
    from mcp.server import TOOL_REGISTRY

    tools = []
    for name, info in TOOL_REGISTRY.items():
        tools.append({
            "name": name,
            "tier": info.get("tier"),
            "cost": info.get("cost"),
        })

    return {"total_tools": len(tools), "tools": tools}


@app.post("/sequence/gc")
async def compute_gc_content(request: ComputeGCContentRequestModel):
    """Compute GC content for a DNA sequence."""
    from core.gc import compute_gc_content
    from schemas.canonical import ComputeGCContentRequest

    req = ComputeGCContentRequest(
        sequence=request.sequence,
        gc_window_size=request.gc_window_size,
        gc_split_ratio=request.gc_split_ratio,
        gc_min_threshold=request.gc_min_threshold,
        gc_max_threshold=request.gc_max_threshold,
        include_sliding_window=request.include_sliding_window,
        include_half_split=request.include_half_split,
        round_decimals=request.round_decimals,
    )
    result = compute_gc_content(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/sequence/homopolymer")
async def check_homopolymer_runs(request: CheckHomopolymerRunsRequestModel):
    """Check homopolymer runs in a DNA sequence."""
    from core.homopolymer import check_homopolymer_runs
    from schemas.canonical import CheckHomopolymerRunsRequest

    req = CheckHomopolymerRunsRequest(
        sequence=request.sequence,
        homopolymer_min_run=request.homopolymer_min_run,
        polyT_strict=request.polyT_strict,
        polyG_strict=request.polyG_strict,
        check_bases=request.check_bases,
        return_run_positions=request.return_run_positions,
    )
    result = check_homopolymer_runs(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/sequence/tm")
async def compute_melting_temp(request: ComputeMeltingTempRequestModel):
    """Compute melting temperature for a DNA sequence."""
    from core.tm import compute_melting_temp
    from schemas.canonical import ComputeMeltingTempRequest

    req = ComputeMeltingTempRequest(
        sequence=request.sequence,
        tm_method=request.tm_method,
        na_conc=request.na_conc,
        mg_conc=request.mg_conc,
        primer_conc=request.primer_conc,
        seed_region_length=request.seed_region_length,
        compute_seed_tm=request.compute_seed_tm,
        round_decimals=request.round_decimals,
    )
    result = compute_melting_temp(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/sequence/secondary-structure")
async def compute_secondary_structure(request: ComputeSecondaryStructureRequestModel):
    """Compute secondary structure / MFE for a DNA sequence."""
    from core.ss import compute_secondary_structure
    from schemas.canonical import ComputeSecondaryStructureRequest

    req = ComputeSecondaryStructureRequest(
        sequence=request.sequence,
        mfe_include_scaffold=request.mfe_include_scaffold,
        scaffold_sequence=request.scaffold_sequence,
        temperature_celsius=request.temperature_celsius,
        return_structure_string=request.return_structure_string,
        mfe_threshold=request.mfe_threshold,
    )
    result = compute_secondary_structure(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/sequence/positional-features")
async def compute_positional_features(request: ComputePositionalFeaturesRequestModel):
    """Compute positional nucleotide features for a spacer sequence."""
    from core.positional_features import compute_positional_features
    from schemas.canonical import ComputePositionalFeaturesRequest

    req = ComputePositionalFeaturesRequest(
        sequence=request.sequence,
        spacer_length=request.spacer_length,
        return_onehot=request.return_onehot,
        check_position20_bias=request.check_position20_bias,
        custom_check_positions=request.custom_check_positions,
        onehot_alphabet=request.onehot_alphabet,
    )
    result = compute_positional_features(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/sequence/dinucleotide-composition")
async def compute_dinucleotide_composition(request: ComputeDinucleotideCompositionRequestModel):
    """Compute dinucleotide composition for a spacer sequence."""
    from core.dinucleotide import compute_dinucleotide_composition
    from schemas.canonical import ComputeDinucleotideCompositionRequest

    req = ComputeDinucleotideCompositionRequest(
        sequence=request.sequence,
        spacer_length=request.spacer_length,
        window_size=request.window_size,
        return_full_matrix=request.return_full_matrix,
        normalize_counts=request.normalize_counts,
        target_dinucleotides=request.target_dinucleotides,
    )
    result = compute_dinucleotide_composition(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/sequence/seed-gc")
async def compute_seed_gc(request: ComputeSeedGCRequestModel):
    """Compute PAM-proximal seed GC content for a spacer sequence."""
    from core.seed_gc import compute_seed_gc
    from schemas.canonical import ComputeSeedGCRequest

    req = ComputeSeedGCRequest(
        sequence=request.sequence,
        seed_region_length=request.seed_region_length,
        seed_anchor=request.seed_anchor,
        seed_min_threshold=request.seed_min_threshold,
        seed_max_threshold=request.seed_max_threshold,
        compute_seed_distal_delta=request.compute_seed_distal_delta,
        round_decimals=request.round_decimals,
    )
    result = compute_seed_gc(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/offtarget/analyze-seed")
async def analyze_mismatch_seed(request: AnalyzeMismatchSeedRequestModel):
    """Analyze mismatches and bulges in the seed region of an off-target candidate."""
    from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed as _analyze
    from schemas.canonical import VeyraResult

    result = _analyze(
        spacer_sequence=request.spacer_sequence,
        candidate_sequence=request.candidate_sequence,
        bulge_type=request.bulge_type,
        bulge_size=request.bulge_size,
        bulge_position=request.bulge_position,
        aligned_guide=request.aligned_guide,
        aligned_candidate=request.aligned_candidate,
        seed_region_length=request.seed_region_length,
        pam_pattern=request.pam_pattern,
    )
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return {
        "tool": result.tool,
        "rows": [],
        "summary": result.summary,
        "errors": result.errors,
        "warnings": result.warnings,
        "metadata": result.metadata,
    }


@app.post("/sequence/cut-site")
async def compute_cut_site(request: ComputeCutSiteRequestModel):
    """Compute canonical SpCas9 cleavage-site position (deterministic coordinate/geometry)."""
    from core.cut_site import compute_cut_site
    from schemas.canonical import ComputeCutSiteRequest

    req = ComputeCutSiteRequest(
        spacer_start=request.spacer_start,
        spacer_length=request.spacer_length,
        strand=request.strand,
        pam_position=request.pam_position,
        cut_offset_from_pam=request.cut_offset_from_pam,
        return_genomic_coord=request.return_genomic_coord,
        return_relative_coord=request.return_relative_coord,
        chrom=request.chrom,
    )
    result = compute_cut_site(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.post("/score/ontarget")
async def predict_ontarget_efficiency(request: PredictOnTargetEfficiencyRequestModel):
    """Predict on-target SpCas9 efficiency (Rule Set 2 / Rule Set 3).
    
    This is fundamentally different from CFD/off-target specificity.
    It answers: "How efficiently is this intended guide expected to cut?"
    """
    from core.ontarget import predict_ontarget_efficiency
    from schemas.canonical import ComputeOnTargetEfficiencyRequest

    req = ComputeOnTargetEfficiencyRequest(
        context_sequence=request.context_sequence,
        model=request.model,
        context_upstream=request.context_upstream,
        context_downstream=request.context_downstream,
        spacer_length=request.spacer_length,
        normalize_score=request.normalize_score,
        round_decimals=request.round_decimals,
        precomputed_features=request.precomputed_features,
    )
    result = predict_ontarget_efficiency(req)
    if result.errors:
        raise HTTPException(status_code=400, detail={"errors": result.errors})
    return _result_to_response(result)


@app.get("/models")
async def list_models():
    """List all on-target models with availability and runtime status."""
    from core.model_runtime import list_model_runtimes
    from core.model_registry import get_model_registry

    registry = get_model_registry()
    runtimes = {rt["model_id"]: rt for rt in list_model_runtimes()}

    models = []
    for model_id in ["rule_set_3", "rule_set_2", "doench_2014"]:
        info = registry.get(model_id)
        rt = runtimes.get(model_id, {})
        models.append({
            "model_id": model_id,
            "display_name": info.display_name if info else "unknown",
            "availability": info.availability if info else "unknown",
            "verified": info.verified if info else False,
            "runtime_state": rt.get("state", "not_provisioned"),
            "runtime_path": rt.get("runtime_path", ""),
            "python_version": rt.get("python_version"),
            "dependency_status": rt.get("dependency_status"),
            "verification_status": rt.get("verification_status"),
            "expected_python": rt.get("expected_python"),
        })

    return {"models": models}


@app.get("/models/{model_id}")
async def get_model(model_id: str):
    """Get detailed information about a specific model."""
    from core.model_runtime import get_model_status
    from core.model_registry import get_model_info

    info = get_model_info(model_id)
    if not info:
        raise HTTPException(status_code=404, detail={"error": f"Unknown model: {model_id}"})

    rt_status = get_model_status(model_id)
    info_dict = info.to_dict()
    info_dict["runtime"] = rt_status

    return info_dict


@app.post("/models/{model_id}/setup")
async def setup_model(model_id: str, force: bool = False):
    """Provision an isolated runtime for a model.
    
    This may be expensive (creates venv, installs packages).
    Only modifies project-local model environments under data/model_envs/.
    Does NOT modify the main VEYRA environment.
    """
    from core.model_runtime import provision_model, get_model_spec

    if not get_model_spec(model_id):
        raise HTTPException(status_code=404, detail={"error": f"Unknown model: {model_id}"})

    result = provision_model(model_id, force=force)
    if result.get("runtime_status") == "verified" or result.get("action") == "no_provisioning_needed":
        return {"success": True, "result": result}
    else:
        return {"success": False, "result": result}


@app.post("/models/{model_id}/verify")
async def verify_model_endpoint(model_id: str):
    """Verify a model's runtime with health check."""
    from core.model_runtime import verify_model, get_model_spec

    if not get_model_spec(model_id):
        raise HTTPException(status_code=404, detail={"error": f"Unknown model: {model_id}"})

    result = verify_model(model_id)
    if result.get("verification_status") == "pass":
        return {"success": True, "result": result}
    else:
        return {"success": False, "result": result}


@app.get("/models/{model_id}/status")
async def model_status(model_id: str):
    """Get the runtime status of a model."""
    from core.model_runtime import get_model_status

    status = get_model_status(model_id)
    return status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
