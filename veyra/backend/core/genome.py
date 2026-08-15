"""Core genome management service.

Provides genome listing and info through a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import GenomeInfo, VeyraResult, ResultRow
from references import list_genomes as _list_genomes, get_genome as _get_genome


def list_genomes() -> VeyraResult:
    """List all registered genomes.

    Returns:
        VeyraResult with genome information.
    """
    genomes = _list_genomes()
    rows = []
    for g in genomes:
        rows.append(ResultRow(
            chrom=g.genome_id,
            start=None,
            end=None,
            strand=None,
            protospacer=g.display_name,
            pam=None,
            pam_type=None,
            mismatch_count=None,
            mismatch_positions=None,
            cfd_score=None,
            rs2_score=None,
        ))

    return VeyraResult(
        tool="list_genomes",
        rows=rows,
        summary={
            "total_genomes": len(genomes),
            "genome_ids": [g.genome_id for g in genomes],
        },
        errors=[],
        warnings=[],
        metadata={},
    )


def genome_info(genome_id: str) -> VeyraResult:
    """Get detailed information about a genome.

    Args:
        genome_id: The genome identifier.

    Returns:
        VeyraResult with genome details.
    """
    try:
        genome = _get_genome(genome_id)
        info = GenomeInfo(
            genome_id=genome.genome_id,
            display_name=genome.display_name,
            fasta_path=genome.fasta_path,
            has_fai=genome.has_fai,
            has_bwa_index=genome.has_bwa_index,
            metadata=genome.metadata,
        )

        return VeyraResult(
            tool="genome_info",
            rows=[ResultRow(
                chrom=info.genome_id,
                start=None,
                end=None,
                strand=None,
                protospacer=info.display_name,
                pam=info.fasta_path,
                pam_type=None,
                mismatch_count=None,
                mismatch_positions=None,
                cfd_score=None,
                rs2_score=None,
            )],
            summary=info.to_dict(),
            errors=[],
            warnings=[],
            metadata={"has_fai": info.has_fai, "has_bwa_index": info.has_bwa_index},
        )
    except ValueError as e:
        return VeyraResult(
            tool="genome_info",
            errors=[str(e)],
        )
