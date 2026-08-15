"""MCP Tool: offtarget_search

Search a genome for approximate matches to a guide/spacer sequence.
Uses BWA for mismatch-tolerant alignment or Cas-OFFinder for bulge-aware search.

Tier 2 — INDEXED / APPROXIMATE

Cost: expensive / genome-scale
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
from parsers.pam import _complement, PAM_DATABASE


def offtarget_search(
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
) -> ToolResult:
    """Search a genome for approximate off-target matches to a spacer.

    Uses BWA aln with mismatch tolerance or Cas-OFFinder for bulge-aware search.

    Backend options:
    - "bwa": Mismatch-only search using BWA aln. Fast but no bulge support.
    - "cas_offinder": DNA/RNA bulge-aware search using Cas-OFFinder 3.0.0.

    When allow_bulge=True, the cas_offinder backend is used automatically.

    Args:
        spacer_sequence: The guide/spacer sequence to search for.
        genome_id: Registered genome identifier.
        pam_pattern: IUPAC PAM pattern.
        max_mismatches: Maximum mismatches allowed.
        allow_bulge: If True, use cas_offinder backend with bulge support.
        cas_variant: Cas variant name (used for PAM context in output).
        backend: "bwa" or "cas_offinder". Ignored when allow_bulge=True.
        max_dna_bulge: Maximum DNA bulge size (cas_offinder only).
        max_rna_bulge: Maximum RNA bulge size (cas_offinder only).
        search_scope: "genome" or "region" (cas_offinder only).
        chrom: Chromosome name (required when search_scope="region").
        start: Start position, 1-based (required when search_scope="region").
        end: End position, exclusive (required when search_scope="region").

    Returns:
        ToolResult with off-target candidate rows.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Route to cas_offinder if bulges requested
    if allow_bulge or backend == "cas_offinder":
        from mcp.tools.cas_offinder_search import cas_offinder_search

        if backend == "bwa" and allow_bulge:
            warnings.append("allow_bulge=True requires cas_offinder backend. Using cas_offinder.")

        return cas_offinder_search(
            spacer_sequence=spacer_sequence,
            genome_id=genome_id,
            pam_pattern=pam_pattern,
            max_mismatches=max_mismatches,
            max_dna_bulge=max_dna_bulge if allow_bulge else 0,
            max_rna_bulge=max_rna_bulge if allow_bulge else 0,
            search_scope=search_scope,
            chrom=chrom,
            start=start,
            end=end,
            cas_variant=cas_variant,
        )

    # BWA backend (mismatch-only)
    if allow_bulge:
        warnings.append("Bulge detection not supported by BWA backend. Using cas_offinder.")

    # Validate inputs
    try:
        seq = validate_dna_sequence(spacer_sequence)
    except ValueError as e:
        return ToolResult(tool="offtarget_search", errors=[str(e)])

    try:
        pam_pattern = validate_pam_pattern(pam_pattern)
    except ValueError as e:
        return ToolResult(tool="offtarget_search", errors=[str(e)])

    if max_mismatches < 0 or max_mismatches > 10:
        return ToolResult(
            tool="offtarget_search",
            errors=[f"max_mismatches must be 0-10, got {max_mismatches}"],
        )

    # Validate genome
    try:
        genome = get_genome(genome_id)
    except ValueError as e:
        return ToolResult(tool="offtarget_search", errors=[str(e)])

    if not genome.has_bwa_index:
        return ToolResult(
            tool="offtarget_search",
            errors=[
                f"No BWA index for {genome_id}. "
                "Run build_offtarget_index first."
            ],
        )

    # BWA aln finds approximate matches
    # -n: max fraction of mismatches (0.04 = ~1 mismatch in 20nt, scale up)
    # -o: max gap open (0 for no gaps)
    # -l: seed length (use full spacer as seed for short sequences)
    # -k: max seed diff
    n_param = min(max_mismatches / len(seq), 1.0)

    rows: list[PAMSiteRow] = []
    with tempfile.NamedTemporaryFile(mode="w", suffix=".fa", delete=False) as tmp:
        tmp.write(f">query\n{seq}\n")
        tmp.flush()
        tmp_path = tmp.name

    sai_path = tmp_path + ".sai"
    try:
        # Run bwa aln — outputs binary SAI to stdout
        aln_result = subprocess.run(
            [
                "bwa", "aln",
                "-n", str(n_param),
                "-o", "0",
                "-l", str(min(len(seq), 32)),
                "-k", str(max_mismatches),
                genome.fasta_path,
                tmp_path,
            ],
            capture_output=True, timeout=300,
        )

        if aln_result.returncode != 0:
            stderr = aln_result.stderr.decode("utf-8", errors="replace") if aln_result.stderr else ""
            return ToolResult(
                tool="offtarget_search",
                errors=[f"bwa aln failed: {stderr.strip()}"],
            )

        # Write binary SAI output to file
        with open(sai_path, "wb") as f:
            f.write(aln_result.stdout)

        sam_result = subprocess.run(
            ["bwa", "samse", genome.fasta_path, sai_path, tmp_path],
            capture_output=True, text=True, timeout=120,
        )

        if sam_result.returncode != 0:
            return ToolResult(
                tool="offtarget_search",
                errors=[f"bwa samse failed: {sam_result.stderr.strip()}"],
            )

        # Parse SAM output
        for line in sam_result.stdout.split("\n"):
            if line.startswith("@"):
                continue
            if not line.strip():
                continue

            fields = line.split("\t")
            if len(fields) < 11:
                continue

            flag = int(fields[1])
            chrom = fields[2]
            pos = int(fields[3])  # 1-based
            cigar = fields[5]
            read_seq = fields[9]

            # Skip unmapped, secondary, supplementary
            if flag & 0x4 or flag & 0x100 or flag & 0x800:
                continue

            strand = "-" if flag & 0x10 else "+"

            # Calculate mismatches from NM tag if available
            nm = 0
            for tag_field in fields[11:]:
                if tag_field.startswith("NM:i:"):
                    nm = int(tag_field.split(":")[2])
                    break

            if nm > max_mismatches:
                continue

            # Parse CIGAR for coordinates
            ref_len = _cigar_ref_length(cigar)

            # Extract PAM from genome if possible
            pam_seq = _extract_pam_from_genome(
                genome.fasta_path, chrom, pos, ref_len, strand, pam_pattern
            )

            # Find mismatch positions
            mismatch_pos = _find_mismatch_positions(seq, read_seq, strand)

            rows.append(PAMSiteRow(
                chrom=chrom,
                start=pos,
                end=pos + ref_len,
                strand=strand,
                protospacer=read_seq if strand == "+" else _complement(read_seq),
                pam=pam_seq,
                pam_type=_resolve_pam_name(pam_pattern),
                mismatch_count=nm,
                mismatch_positions=",".join(str(p) for p in mismatch_pos) if mismatch_pos else None,
            ))

    finally:
        # Clean up temp files
        for suffix in ["", ".sai"]:
            try:
                os.unlink(tmp_path + suffix)
            except OSError:
                pass

    # Sort by mismatch count then position
    rows.sort(key=lambda r: (r.mismatch_count or 0, r.chrom or "", r.start or 0))

    summary = {
        "total_candidates": len(rows),
        "spacer_length": len(seq),
        "max_mismatches": max_mismatches,
        "genome_id": genome_id,
        "pam_pattern": pam_pattern,
        "mismatch_distribution": {},
        "coordinates": "1-based",
        "backend": "bwa-aln",
        "note": "BWA uses quality-weighted mismatches; results are approximate candidates.",
    }

    # Mismatch distribution
    for r in rows:
        nm = r.mismatch_count or 0
        summary["mismatch_distribution"][nm] = summary["mismatch_distribution"].get(nm, 0) + 1

    return ToolResult(
        tool="offtarget_search",
        rows=rows,
        summary=summary,
        errors=errors,
        warnings=warnings,
    )


def _cigar_ref_length(cigar: str) -> int:
    """Calculate reference length from CIGAR string."""
    import re
    length = 0
    for match in re.finditer(r"(\d+)[M=X]", cigar):
        length += int(match.group(1))
    return length


def _extract_pam_from_genome(
    fasta_path: str, chrom: str, pos: int, ref_len: int,
    strand: str, pam_pattern: str
) -> str | None:
    """Try to extract the PAM sequence adjacent to a hit."""
    try:
        # Use samtools to get a small window around the hit
        if strand == "+":
            # PAM is 3' of protospacer for 3prime PAMs
            pam_start = pos + ref_len
            pam_end = pam_start + 3
        else:
            # PAM is 5' of protospacer on reverse strand
            pam_start = pos - 3
            pam_end = pos

        if pam_start < 1:
            return None

        result = subprocess.run(
            ["samtools", "faidx", fasta_path, f"{chrom}:{pam_start}-{pam_end}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            seq = "".join(l for l in lines if not l.startswith(">")).upper()
            if strand == "-":
                seq = _complement(seq)
            return seq if len(seq) == 3 else None
    except Exception:
        pass
    return None


def _find_mismatch_positions(ref: str, query: str, strand: str) -> list[int]:
    """Find 0-based positions where ref and query differ."""
    positions = []
    min_len = min(len(ref), len(query))
    for i in range(min_len):
        if ref[i] != query[i]:
            positions.append(i)
    return positions


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VEYRA offtarget_search tool")
    parser.add_argument("--spacer", "-s", required=True, help="Spacer sequence")
    parser.add_argument("--genome", required=True, help="Genome ID")
    parser.add_argument("--pam", default="NGG", help="PAM pattern")
    parser.add_argument("--max-mismatches", type=int, default=4)
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    result = offtarget_search(args.spacer, args.genome, args.pam, args.max_mismatches)
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
