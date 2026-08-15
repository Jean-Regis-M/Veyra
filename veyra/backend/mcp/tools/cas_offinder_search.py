"""MCP Tool: cas_offinder_search

Search a genome for off-target matches using Cas-OFFinder with DNA/RNA bulge support.

Tier 2 — INDEXED / BULGE-AWARE

Cost: expensive / genome-scale

Uses Cas-OFFinder 3.0.0 with OpenCL (CPU via POCL).
Supports mismatch + DNA/RNA bulge search.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import PAMSiteRow, ToolResult, validate_dna_sequence, validate_pam_pattern
from mcp.tools.pam_scan import _resolve_pam_name
from references import get_genome


# Cas-OFFinder executable path
_CAS_OFFINDER_BIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "tools", "cas-offinder", "build", "cas-offinder"
)
_POCL_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "cache", "pocl",
)
os.makedirs(_POCL_CACHE_DIR, exist_ok=True)


def _get_pam_length(pam_pattern: str) -> int:
    """Get the length of a PAM pattern."""
    return len(pam_pattern)


def _validate_spacer_for_cas_offinder(spacer_sequence: str, pam_pattern: str) -> tuple[str, int, int, int]:
    """Validate spacer and compute pattern/query lengths.

    Returns:
        (validated_sequence, spacer_length, pam_length, total_pattern_length)
    """
    seq = validate_dna_sequence(spacer_sequence)
    pam_len = _get_pam_length(pam_pattern)
    total_len = len(seq) + pam_len

    return seq, len(seq), pam_len, total_len


def cas_offinder_search(
    spacer_sequence: str,
    genome_id: str,
    pam_pattern: str = "NGG",
    max_mismatches: int = 4,
    max_dna_bulge: int = 1,
    max_rna_bulge: int = 1,
    search_scope: str = "genome",
    chrom: str | None = None,
    start: int | None = None,
    end: int | None = None,
    cas_variant: str = "SpCas9",
    strand_search: str = "both",
    max_results: int = 1000,
) -> ToolResult:
    """Search a genome for off-target matches using Cas-OFFinder.

    Uses Cas-OFFinder 3.0.0 with OpenCL for DNA/RNA bulge-aware search.

    Args:
        spacer_sequence: The guide/spacer sequence to search for.
        genome_id: Registered genome identifier.
        pam_pattern: IUPAC PAM pattern (e.g., "NGG" for SpCas9).
        max_mismatches: Maximum mismatches allowed.
        max_dna_bulge: Maximum DNA bulge size (0 = no DNA bulges).
        max_rna_bulge: Maximum RNA bulge size (0 = no RNA bulges).
        search_scope: "genome" for whole genome, "region" for specific region.
        chrom: Chromosome name (required when search_scope="region").
        start: Start position, 1-based (required when search_scope="region").
        end: End position, exclusive (required when search_scope="region").
        cas_variant: Cas variant name (used for PAM context in output).

    Returns:
        ToolResult with off-target candidates including bulge information.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if strand_search not in ("both", "fwd", "rev"):
        return ToolResult(tool="cas_offinder_search", errors=[
            f"strand_search must be 'both', 'fwd', or 'rev', got '{strand_search}'"
        ])
    if max_results < 1:
        return ToolResult(tool="cas_offinder_search", errors=[
            f"max_results must be >= 1, got {max_results}"
        ])

    # Check Cas-OFFinder executable
    if not os.path.isfile(_CAS_OFFINDER_BIN):
        return ToolResult(
            tool="cas_offinder_search",
            errors=[f"Cas-OFFinder executable not found at {_CAS_OFFINDER_BIN}. Build from source first."],
            summary={"backend": "cas_offinder", "search_scope": search_scope},
            metadata={"cas_offinder_version": "3.0.0", "executable": _CAS_OFFINDER_BIN},
        )

    # Validate inputs
    try:
        seq, spacer_len, pam_len, total_len = _validate_spacer_for_cas_offinder(spacer_sequence, pam_pattern)
    except ValueError as e:
        return ToolResult(tool="cas_offinder_search", errors=[str(e)])

    try:
        pam_pattern = validate_pam_pattern(pam_pattern)
    except ValueError as e:
        return ToolResult(tool="cas_offinder_search", errors=[str(e)])

    # Validate bulge parameters
    if max_dna_bulge < 0 or max_dna_bulge > 5:
        return ToolResult(
            tool="cas_offinder_search",
            errors=[f"max_dna_bulge must be 0-5, got {max_dna_bulge}"],
        )
    if max_rna_bulge < 0 or max_rna_bulge > 5:
        return ToolResult(
            tool="cas_offinder_search",
            errors=[f"max_rna_bulge must be 0-5, got {max_rna_bulge}"],
        )
    if max_mismatches < 0 or max_mismatches > 10:
        return ToolResult(
            tool="cas_offinder_search",
            errors=[f"max_mismatches must be 0-10, got {max_mismatches}"],
        )

    # Validate genome
    try:
        genome = get_genome(genome_id)
    except ValueError as e:
        return ToolResult(tool="cas_offinder_search", errors=[str(e)])

    # Validate search scope
    if search_scope not in ("genome", "region"):
        return ToolResult(
            tool="cas_offinder_search",
            errors=[f"search_scope must be 'genome' or 'region', got '{search_scope}'"],
        )

    if search_scope == "region":
        if not chrom:
            return ToolResult(
                tool="cas_offinder_search",
                errors=["chrom is required when search_scope='region'"],
            )
        if start is None or end is None:
            return ToolResult(
                tool="cas_offinder_search",
                errors=["start and end are required when search_scope='region'"],
            )
        if start < 1:
            return ToolResult(
                tool="cas_offinder_search",
                errors=[f"start must be >= 1, got {start}"],
            )
        if end <= start:
            return ToolResult(
                tool="cas_offinder_search",
                errors=[f"end ({end}) must be > start ({start})"],
            )

    # Create Cas-OFFinder input file
    # Pattern format: spacer_length N's + PAM pattern = total_len characters
    pattern = "N" * spacer_len + pam_pattern

    # Query must be same length as pattern (spacer + PAM)
    query_with_pam = seq + pam_pattern

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "input.txt")
        output_file = os.path.join(tmpdir, "output.txt")

        # Write input file
        with open(input_file, "w") as f:
            # Line 1: genome directory
            f.write(os.path.dirname(genome.fasta_path) + "\n")

            # Line 2: pattern + DNA bulge + RNA bulge
            f.write(f"{pattern} {max_dna_bulge} {max_rna_bulge}\n")

            # Line 3+: query sequence with PAM + mismatch threshold
            f.write(f"{query_with_pam} {max_mismatches}\n")

        # Run Cas-OFFinder
        try:
            # Keep POCL's compiled-kernel cache inside VEYRA. A stale or
            # unwritable user cache can otherwise make OpenCL compilation
            # fail before Cas-OFFinder starts searching.
            engine_env = os.environ.copy()
            engine_env.setdefault("POCL_CACHE_DIR", _POCL_CACHE_DIR)
            result = subprocess.run(
                [_CAS_OFFINDER_BIN, input_file, "C", output_file],
                capture_output=True,
                text=True,
                timeout=600,
                env=engine_env,
            )
        except FileNotFoundError:
            return ToolResult(
                tool="cas_offinder_search",
                errors=[f"Cas-OFFinder executable not found: {_CAS_OFFINDER_BIN}"],
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                tool="cas_offinder_search",
                errors=["Cas-OFFinder search timed out (600s limit)"],
            )

        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            return ToolResult(
                tool="cas_offinder_search",
                errors=[f"Cas-OFFinder failed: {stderr}"],
                summary={"backend": "cas_offinder", "search_scope": search_scope, "coordinates": "1-based"},
                metadata={"cas_offinder_version": "3.0.0", "cas_offinder_source": "https://github.com/snugel/cas-offinder", "execution_device": "cpu", "executable": _CAS_OFFINDER_BIN},
            )

        # Parse output
        rows: list[PAMSiteRow] = []
        if os.path.exists(output_file):
            with open(output_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    fields = line.split("\t")
                    if len(fields) < 9:
                        continue

                    # Parse fields
                    query_id = fields[0]
                    bulge_type = fields[1]  # "X", "DNA", or "RNA"
                    crRNA = fields[2]  # aligned guide with gaps
                    dna_seq = fields[3]  # aligned genomic with gaps and lowercase mismatches
                    chrom_name = fields[4]
                    location = int(fields[5])  # 0-based
                    direction = fields[6]
                    mismatch_count = int(fields[7])
                    bulge_size = int(fields[8])

                    # Extract chromosome name (remove description if present)
                    chrom_clean = chrom_name.split()[0] if " " in chrom_name else chrom_name

                    # Convert 0-based location to 1-based for VEYRA convention
                    start_1based = location + 1

                    # Calculate end position based on alignment length
                    alignment_len = len(dna_seq.replace("-", ""))
                    end_pos = start_1based + alignment_len

                    # Extract protospacer (remove gaps, uppercase for mismatches)
                    protospacer = dna_seq.replace("-", "").upper()

                    # Extract PAM from aligned sequence if possible
                    pam_seq = None
                    if len(protospacer) >= spacer_len:
                        pam_seq = protospacer[spacer_len:spacer_len + pam_len] if len(protospacer) > spacer_len else None

                    # Find mismatch positions (lowercase in dna_seq = mismatch)
                    mismatch_positions = []
                    guide_pos = 0
                    for i, c in enumerate(dna_seq):
                        if c == "-":
                            continue
                        if c.islower():
                            mismatch_positions.append(guide_pos)
                        guide_pos += 1

                    # For bulged candidates, set cfd_status
                    cfd_status = None
                    if bulge_type != "X":
                        cfd_status = "unsupported_bulge"

                    rows.append(PAMSiteRow(
                        chrom=chrom_clean,
                        start=start_1based,
                        end=end_pos,
                        strand=direction,
                        protospacer=protospacer,
                        pam=pam_seq,
                        pam_type=_resolve_pam_name(pam_pattern),
                        mismatch_count=mismatch_count,
                        mismatch_positions=",".join(str(p) for p in mismatch_positions) if mismatch_positions else None,
                        bulge_type=bulge_type,
                        bulge_size=bulge_size,
                        aligned_guide=crRNA,
                        aligned_candidate=dna_seq,
                        cfd_status=cfd_status,
                    ))

    # Filter by region if requested
    if search_scope == "region" and chrom and start is not None and end is not None:
        filtered = []
        for r in rows:
            if r.chrom == chrom and r.start is not None and r.start >= start and r.start < end:
                filtered.append(r)
        rows = filtered
    if strand_search == "fwd":
        rows = [r for r in rows if r.strand in ("+", "F")]
    elif strand_search == "rev":
        rows = [r for r in rows if r.strand in ("-", "R")]
    bulge_order = {"X": 0, "DNA": 1, "RNA": 2}
    rows.sort(key=lambda r: (
        bulge_order.get(r.bulge_type or "X", 3),
        r.mismatch_count or 0,
        r.chrom or "",
        r.start or 0,
    ))

    results_truncated = len(rows) > max_results
    if results_truncated:
        rows = rows[:max_results]

    # Compute summary
    bulge_distribution = {}
    for r in rows:
        bt = r.bulge_type or "X"
        bulge_distribution[bt] = bulge_distribution.get(bt, 0) + 1

    summary = {
        "total_candidates": len(rows),
        "spacer_length": spacer_len,
        "pam_pattern": pam_pattern,
        "max_mismatches": max_mismatches,
        "max_dna_bulge": max_dna_bulge,
        "max_rna_bulge": max_rna_bulge,
        "genome_id": genome_id,
        "search_scope": search_scope,
        "bulge_distribution": bulge_distribution,
        "coordinates": "1-based",
        "backend": "cas_offinder",
        "execution_device": "cpu",
        "opencl_runtime": "pocl",
        "strand_search": strand_search,
        "max_results": max_results,
        "results_truncated": results_truncated,
    }

    if search_scope == "region":
        summary["chrom"] = chrom
        summary["start"] = start
        summary["end"] = end

    return ToolResult(
        tool="cas_offinder_search",
        rows=rows,
        summary=summary,
        errors=errors,
        warnings=warnings,
        metadata={
            "cas_offinder_version": "3.0.0",
            "cas_offinder_source": "https://github.com/snugel/cas-offinder",
            "license": "BSD 3-Clause",
            "execution_device": "cpu",
            "opencl_runtime": "pocl",
            "executable": _CAS_OFFINDER_BIN,
        },
    )


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VEYRA cas_offinder_search tool")
    parser.add_argument("--spacer", "-s", required=True, help="Spacer sequence")
    parser.add_argument("--genome", required=True, help="Genome ID")
    parser.add_argument("--pam", default="NGG", help="PAM pattern")
    parser.add_argument("--max-mismatches", type=int, default=4)
    parser.add_argument("--max-dna-bulge", type=int, default=1)
    parser.add_argument("--max-rna-bulge", type=int, default=1)
    parser.add_argument("--scope", default="genome", choices=["genome", "region"])
    parser.add_argument("--chrom", help="Chromosome (for region scope)")
    parser.add_argument("--start", type=int, help="Start position (for region scope)")
    parser.add_argument("--end", type=int, help="End position (for region scope)")
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    result = cas_offinder_search(
        spacer_sequence=args.spacer,
        genome_id=args.genome,
        pam_pattern=args.pam,
        max_mismatches=args.max_mismatches,
        max_dna_bulge=args.max_dna_bulge,
        max_rna_bulge=args.max_rna_bulge,
        search_scope=args.scope,
        chrom=args.chrom,
        start=args.start,
        end=args.end,
    )
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
