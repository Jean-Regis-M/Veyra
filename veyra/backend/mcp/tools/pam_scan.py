"""MCP Tool: pam_scan

Fast PAM/protospacer discovery within an input sequence.
Tier 1 — FAST / EXACT (regex/IUPAC matching).

Cost: cheap / deterministic
"""

from __future__ import annotations

import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import (
    PAMSiteRow,
    ToolResult,
    validate_dna_sequence,
    validate_pam_pattern,
)
from parsers.pam import _iupac_to_regex, _complement, _expand_iupac, PAM_DATABASE


def pam_scan(
    sequence: str,
    pam_pattern: str = "NGG",
    protospacer_len: int = 20,
    strand: str = "both",
    chrom: str | None = None,
) -> ToolResult:
    """Scan a raw DNA sequence for PAM sites.

    Args:
        sequence: Raw DNA string (may contain IUPAC ambiguity codes).
        pam_pattern: IUPAC PAM motif (default: NGG for SpCas9).
        protospacer_len: Length of the protospacer (default: 20).
        strand: "both", "fwd", or "rev".
        chrom: Optional chromosome/contig name for output.

    Returns:
        ToolResult with PAMSiteRow entries.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Validate inputs
    try:
        seq = validate_dna_sequence(sequence, allow_iupac=True)
    except ValueError as e:
        return ToolResult(tool="pam_scan", errors=[str(e)])

    if not seq:
        return ToolResult(
            tool="pam_scan",
            summary={"total_sites": 0, "forward_sites": 0, "reverse_sites": 0,
                     "sequence_length": 0, "pam_pattern": pam_pattern,
                     "protospacer_len": protospacer_len, "strand_filter": strand,
                     "coordinates": "1-based, half-open [start, end)"},
        )

    try:
        pam_pattern = validate_pam_pattern(pam_pattern)
    except ValueError as e:
        return ToolResult(tool="pam_scan", errors=[str(e)])

    if strand not in ("both", "fwd", "rev"):
        return ToolResult(tool="pam_scan", errors=[f"Invalid strand: {strand}. Use 'both', 'fwd', or 'rev'"])

    if protospacer_len < 1 or protospacer_len > 100:
        return ToolResult(tool="pam_scan", errors=[f"protospacer_len must be 1-100, got {protospacer_len}"])

    # Determine PAM position based on known Cas types or default to 3prime
    pam_position = "3prime"
    for _name, info in PAM_DATABASE.items():
        if info["motif"].upper() == pam_pattern.upper():
            pam_position = info["pam_position"]
            break

    seq_len = len(seq)
    rows: list[PAMSiteRow] = []

    fwd_regex = _iupac_to_regex(pam_pattern)
    rev_motif = _complement(pam_pattern)
    rev_regex = _iupac_to_regex(rev_motif)

    # Forward strand
    if strand in ("both", "fwd"):
        for m in re.finditer(fwd_regex, seq):
            pos = m.start()  # 0-based
            pam_seq = m.group()
            spacer: str | None = None

            if pam_position == "3prime":
                s_start = pos - protospacer_len
                if s_start >= 0:
                    spacer = seq[s_start:pos]
            else:
                s_start = pos + len(pam_seq)
                if s_start + protospacer_len <= seq_len:
                    spacer = seq[s_start:s_start + protospacer_len]

            rows.append(PAMSiteRow(
                chrom=chrom,
                start=pos + 1,  # convert to 1-based
                end=pos + 1 + len(pam_seq),
                strand="+",
                protospacer=spacer,
                pam=pam_seq,
                pam_type=f"custom:{pam_pattern}" if pam_pattern not in [v["motif"] for v in PAM_DATABASE.values()] else _resolve_pam_name(pam_pattern),
            ))

    # Reverse strand
    if strand in ("both", "rev"):
        for m in re.finditer(rev_regex, seq):
            pos = m.start()  # 0-based
            pam_seq_rc = _complement(m.group())  # canonical PAM on reverse strand
            spacer: str | None = None

            if pam_position == "3prime":
                s_end = pos
                s_start = pos - protospacer_len
                if s_start >= 0:
                    spacer = seq[s_start:s_end]
            else:
                s_start = pos + len(m.group())
                if s_start + protospacer_len <= seq_len:
                    spacer = seq[s_start:s_start + protospacer_len]

            rows.append(PAMSiteRow(
                chrom=chrom,
                start=pos + 1,
                end=pos + 1 + len(m.group()),
                strand="-",
                protospacer=spacer,
                pam=pam_seq_rc,
                pam_type=f"custom:{pam_pattern}" if pam_pattern not in [v["motif"] for v in PAM_DATABASE.values()] else _resolve_pam_name(pam_pattern),
            ))

    # Sort by position
    rows.sort(key=lambda r: (r.start or 0, r.strand or ""))

    summary = {
        "total_sites": len(rows),
        "forward_sites": sum(1 for r in rows if r.strand == "+"),
        "reverse_sites": sum(1 for r in rows if r.strand == "-"),
        "sequence_length": seq_len,
        "pam_pattern": pam_pattern,
        "protospacer_len": protospacer_len,
        "strand_filter": strand,
        "coordinates": "1-based, half-open [start, end)",
    }

    return ToolResult(
        tool="pam_scan",
        rows=rows,
        summary=summary,
        errors=errors,
        warnings=warnings,
    )


def _resolve_pam_name(motif: str) -> str:
    """Resolve a PAM motif to its canonical name if possible."""
    for name, info in PAM_DATABASE.items():
        if info["motif"].upper() == motif.upper():
            return name
    return f"custom:{motif}"


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="VEYRA pam_scan tool")
    parser.add_argument("--sequence", "-s", required=True, help="DNA sequence to scan")
    parser.add_argument("--pam", default="NGG", help="IUPAC PAM pattern (default: NGG)")
    parser.add_argument("--spacer-len", type=int, default=20, help="Protospacer length (default: 20)")
    parser.add_argument("--strand", default="both", choices=["both", "fwd", "rev"])
    parser.add_argument("--chrom", default=None, help="Chromosome name")
    parser.add_argument("--tsv", action="store_true", help="Output as TSV instead of JSON")
    args = parser.parse_args()

    result = pam_scan(args.sequence, args.pam, args.spacer_len, args.strand, args.chrom)
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
