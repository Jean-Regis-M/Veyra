"""MCP Tool: pam_scan_region

Run PAM scanning against a genomic region using indexed FASTA access.
Does NOT load the entire genome into memory.

Tier 1 — FAST / EXACT (reference lookup + regex).

Cost: cheap / reference lookup
"""

from __future__ import annotations

import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import ToolResult, validate_chrom, validate_coordinates, validate_pam_pattern
from mcp.tools.pam_scan import pam_scan
from references import get_genome


def pam_scan_region(
    genome_id: str,
    chrom: str,
    start: int,
    end: int,
    pam_pattern: str = "NGG",
    protospacer_len: int = 20,
    strand: str = "both",
) -> ToolResult:
    """Scan a genomic region for PAM sites using indexed FASTA retrieval.

    Uses `samtools faidx` to extract only the requested region,
    avoiding loading the full genome into memory.

    Args:
        genome_id: Registered genome identifier (e.g. "GRCh38.p14").
        chrom: Chromosome/contig name.
        start: 1-based start position (inclusive).
        end: 1-based end position (exclusive).
        pam_pattern: IUPAC PAM motif.
        protospacer_len: Length of the protospacer.
        strand: "both", "fwd", or "rev".

    Returns:
        ToolResult with PAMSiteRow entries.
    """
    errors: list[str] = []

    # Validate genome
    try:
        genome = get_genome(genome_id)
    except ValueError as e:
        return ToolResult(tool="pam_scan_region", errors=[str(e)])

    if not genome.has_fai:
        return ToolResult(
            tool="pam_scan_region",
            errors=[
                f"No .fai index for {genome_id}. Run: samtools faidx {genome.fasta_path}"
            ],
        )

    # Validate inputs
    try:
        chrom = validate_chrom(chrom)
        start, end = validate_coordinates(start, end)
        pam_pattern = validate_pam_pattern(pam_pattern)
    except ValueError as e:
        return ToolResult(tool="pam_scan_region", errors=[str(e)])

    if strand not in ("both", "fwd", "rev"):
        return ToolResult(tool="pam_scan_region", errors=[f"Invalid strand: {strand}"])

    # Extract region using samtools faidx (1-based, inclusive coordinates for samtools)
    region = f"{chrom}:{start}-{end}"
    try:
        result = subprocess.run(
            ["samtools", "faidx", genome.fasta_path, region],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return ToolResult(
                tool="pam_scan_region",
                errors=[f"samtools faidx failed: {result.stderr.strip()}"],
            )
    except FileNotFoundError:
        return ToolResult(
            tool="pam_scan_region",
            errors=["samtools not found. Install samtools and ensure it is on PATH."],
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            tool="pam_scan_region",
            errors=["samtools faidx timed out (30s limit)."],
        )

    # Parse the FASTA output
    lines = result.stdout.strip().split("\n")
    seq_lines = [l for l in lines if not l.startswith(">")]
    sequence = "".join(seq_lines).upper()

    if not sequence:
        return ToolResult(
            tool="pam_scan_region",
            errors=[f"Empty sequence returned for region {region}"],
        )

    # Run PAM scan on the extracted sequence
    pam_result = pam_scan(sequence, pam_pattern, protospacer_len, strand, chrom=chrom)

    # Adjust coordinates to genome space
    for row in pam_result.rows:
        if row.start is not None:
            row.start = row.start - 1 + start  # convert from local 1-based to genome 1-based
        if row.end is not None:
            row.end = row.end - 1 + start

    pam_result.tool = "pam_scan_region"
    pam_result.metadata = {
        "genome_id": genome_id,
        "region": region,
        "region_length": end - start + 1,
        "retrieval_method": "samtools_faidx",
    }
    pam_result.summary["genome_id"] = genome_id
    pam_result.summary["region"] = region

    return pam_result


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VEYRA pam_scan_region tool")
    parser.add_argument("--genome", required=True, help="Genome ID (e.g. GRCh38.p14)")
    parser.add_argument("--chrom", required=True, help="Chromosome name")
    parser.add_argument("--start", type=int, required=True, help="1-based start (inclusive)")
    parser.add_argument("--end", type=int, required=True, help="1-based end (exclusive)")
    parser.add_argument("--pam", default="NGG", help="IUPAC PAM pattern")
    parser.add_argument("--spacer-len", type=int, default=20)
    parser.add_argument("--strand", default="both", choices=["both", "fwd", "rev"])
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    result = pam_scan_region(
        args.genome, args.chrom, args.start, args.end,
        args.pam, args.spacer_len, args.strand,
    )
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
