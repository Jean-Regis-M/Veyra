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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
