"""MCP Tool: build_offtarget_index

Build or register a reusable genome-search index for off-target analysis.
Uses BWA for approximate alignment.

Tier 2 — INDEXED / APPROXIMATE

Cost: expensive / setup / cacheable
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import ToolResult
from references import get_genome
from cache import make_cache_key, cache_get, cache_set


def build_offtarget_index(
    genome_id: str,
    cas_variant: str = "SpCas9",
    force_rebuild: bool = False,
) -> ToolResult:
    """Build or retrieve a cached BWA index for off-target searching.

    This is an expensive operation. Indexes are cached by genome_id +
    cas_variant + source checksum. Reuses existing indexes when possible.

    Args:
        genome_id: Registered genome identifier.
        cas_variant: Cas variant identifier (used as part of cache key).
        force_rebuild: If True, rebuild even if cache exists.

    Returns:
        ToolResult with index metadata.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Validate genome
    try:
        genome = get_genome(genome_id)
    except ValueError as e:
        return ToolResult(tool="build_offtarget_index", errors=[str(e)])

    if not os.path.isfile(genome.fasta_path):
        return ToolResult(
            tool="build_offtarget_index",
            errors=[f"FASTA file not found: {genome.fasta_path}"],
        )

    # Check cache
    checksum = genome.fasta_checksum()
    cache_key = make_cache_key(
        "build_offtarget_index",
        genome_id=genome_id,
        cas_variant=cas_variant,
        checksum=checksum,
    )

    if not force_rebuild:
        cached = cache_get(cache_key)
        if cached is not None and cached.get("index_path"):
            # Verify index still exists on disk
            prefix = cached["index_path"]
            if os.path.isfile(prefix + ".bwt"):
                return ToolResult(
                    tool="build_offtarget_index",
                    summary={
                        "status": "cached",
                        "genome_id": genome_id,
                        "cas_variant": cas_variant,
                        "index_path": prefix,
                        "cache_key": cache_key,
                    },
                    metadata=cached.get("metadata", {}),
                )

    # Build BWA index
    fasta_path = genome.fasta_path
    warnings.append(f"Building BWA index for {fasta_path}. This may take a while for large genomes.")

    t0 = time.time()
    try:
        result = subprocess.run(
            ["bwa", "index", fasta_path],
            capture_output=True, text=True, timeout=7200,  # 2 hour timeout
        )
        if result.returncode != 0:
            return ToolResult(
                tool="build_offtarget_index",
                errors=[f"bwa index failed: {result.stderr.strip()}"],
            )
    except FileNotFoundError:
        return ToolResult(
            tool="build_offtarget_index",
            errors=["bwa not found. Install BWA and ensure it is on PATH."],
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            tool="build_offtarget_index",
            errors=["bwa index timed out (2h limit). Genome may be too large."],
        )

    elapsed = time.time() - t0

    # Also build samtools fai index if missing
    if not genome.has_fai:
        try:
            subprocess.run(
                ["samtools", "faidx", fasta_path],
                capture_output=True, text=True, timeout=600,
            )
        except Exception:
            warnings.append("samtools faidx failed; region-based queries may not work.")

    # Update genome config
    genome.bwa_index_prefix = fasta_path
    genome.fai_path = fasta_path + ".fai"

    # Cache the result
    cache_set(
        cache_key,
        tool_name="build_offtarget_index",
        params_hash=checksum,
        index_path=fasta_path,
        metadata={
            "genome_id": genome_id,
            "cas_variant": cas_variant,
            "build_time_seconds": elapsed,
            "fasta_path": fasta_path,
        },
        source_checksum=checksum,
        ttl_seconds=86400 * 30,  # 30 day TTL for indexes
    )

    return ToolResult(
        tool="build_offtarget_index",
        summary={
            "status": "built",
            "genome_id": genome_id,
            "cas_variant": cas_variant,
            "index_path": fasta_path,
            "build_time_seconds": round(elapsed, 2),
            "cache_key": cache_key,
        },
        warnings=warnings,
    )


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VEYRA build_offtarget_index tool")
    parser.add_argument("--genome", required=True, help="Genome ID")
    parser.add_argument("--cas", default="SpCas9", help="Cas variant (default: SpCas9)")
    parser.add_argument("--force", action="store_true", help="Force rebuild")
    args = parser.parse_args()

    result = build_offtarget_index(args.genome, args.cas, args.force)
    print(result.to_json(indent=2))
