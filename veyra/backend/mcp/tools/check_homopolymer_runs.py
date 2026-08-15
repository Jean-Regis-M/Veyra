"""MCP Tool: check_homopolymer_runs

Deterministic homopolymer-run detector for DNA sequences.

Tier: cheap / deterministic

This tool flags homopolymer runs (poly-T, poly-G, etc.) as sequence-level
heuristics.  poly-T flags relate to Pol III transcription termination risk;
poly-G flags relate to potential G-quadruplex formation risk.  Neither is
direct experimental evidence.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import PAMSiteRow, ToolResult, validate_dna_sequence

# Valid bases for homopolymer scanning (standard DNA only — no IUPAC ambiguity
# codes participate in contiguous-run detection because ambiguous bases represent
# uncertainty about which base is present).
_VALID_CHECK_BASES = frozenset("ACGTacgt")


def _find_runs(seq: str, check_bases: str, min_run: int) -> list[dict]:
    """Find contiguous runs of identical bases in seq.

    Uses 0-based half-open [start, end) coordinate convention
    consistent with the GC sliding-window tool.

    Args:
        seq: Uppercased DNA sequence.
        check_bases: Uppercase string of bases to scan for.
        min_run: Minimum run length to report.

    Returns:
        List of dicts with base, start, end, length.
    """
    runs = []
    if not seq or min_run < 2:
        return runs

    check_set = frozenset(check_bases.upper())
    current_base = seq[0]
    current_start = 0

    for i in range(1, len(seq)):
        if seq[i] != current_base:
            # End of run
            length = i - current_start
            if length >= min_run and current_base in check_set:
                runs.append({
                    "base": current_base,
                    "start": current_start,
                    "end": i,
                    "length": length,
                })
            current_base = seq[i]
            current_start = i

    # Handle final run
    length = len(seq) - current_start
    if length >= min_run and current_base in check_set:
        runs.append({
            "base": current_base,
            "start": current_start,
            "end": len(seq),
            "length": length,
        })

    return runs


def check_homopolymer_runs(
    sequence: str,
    homopolymer_min_run: int = 4,
    polyT_strict: bool = True,
    polyG_strict: bool = False,
    check_bases: str = "ACGT",
    return_run_positions: bool = False,
) -> ToolResult:
    """Detect homopolymer runs in a DNA sequence.

    Args:
        sequence: DNA sequence (IUPAC characters allowed).
        homopolymer_min_run: Minimum run length to flag (>= 2).
        polyT_strict: If True, poly-T runs cause passes_filter=False.
        polyG_strict: If True, poly-G runs cause passes_filter=False.
        check_bases: Bases to scan for runs (subset of ACGT).
        return_run_positions: If True, include run position details.

    Returns:
        ToolResult with homopolymer analysis in summary.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- Validate sequence ---
    try:
        seq = validate_dna_sequence(sequence, allow_iupac=True)
    except ValueError as e:
        return ToolResult(tool="check_homopolymer_runs", errors=[str(e)])

    seq_len = len(seq)

    # --- Validate parameters ---
    if not isinstance(homopolymer_min_run, int) or homopolymer_min_run < 2:
        errors.append(f"homopolymer_min_run must be an integer >= 2, got {homopolymer_min_run}")

    if not check_bases or not isinstance(check_bases, str):
        errors.append("check_bases must be a non-empty string")
    else:
        check_upper = check_bases.upper()
        invalid_bases = set(check_upper) - _VALID_CHECK_BASES
        if invalid_bases:
            errors.append(f"Invalid bases in check_bases: {sorted(invalid_bases)}")
        check_bases = check_upper

    if errors:
        return ToolResult(tool="check_homopolymer_runs", errors=errors)

    # --- Find all qualifying runs ---
    runs = _find_runs(seq, check_bases, homopolymer_min_run)

    # --- Compute flags ---
    polyT_flag = any(r["base"] == "T" for r in runs)
    polyG_flag = any(r["base"] == "G" for r in runs)

    # Max run across all requested bases
    homopolymer_max_run = max((r["length"] for r in runs), default=0)

    # --- Pass/fail logic ---
    # Strict mode: qualifying runs of that base cause failure
    # Non-strict: runs are flagged but do not cause failure
    fails = False
    if polyT_strict and polyT_flag:
        fails = True
    if polyG_strict and polyG_flag:
        fails = True

    passes_filter = not fails

    # --- Build result ---
    row = PAMSiteRow(
        protospacer=seq[:20] if seq_len >= 20 else seq,
    )

    summary = {
        "sequence_length": seq_len,
        "polyT_flag": polyT_flag,
        "polyG_flag": polyG_flag,
        "homopolymer_max_run": homopolymer_max_run,
        "passes_filter": passes_filter,
        "runs": runs if return_run_positions else [],
    }

    metadata = {
        "homopolymer_min_run": homopolymer_min_run,
        "polyT_strict": polyT_strict,
        "polyG_strict": polyG_strict,
        "check_bases": check_bases,
        "return_run_positions": return_run_positions,
        "scoring_note": (
            "Homopolymer flags are sequence-level heuristics, NOT experimental "
            "evidence of transcription termination or G-quadruplex formation."
        ),
    }

    return ToolResult(
        tool="check_homopolymer_runs",
        rows=[row],
        summary=summary,
        errors=errors,
        warnings=warnings,
        metadata=metadata,
    )


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VEYRA check_homopolymer_runs tool")
    parser.add_argument("--sequence", "-s", required=True, help="DNA sequence")
    parser.add_argument("--homopolymer-min-run", type=int, default=4, help="Min run length to flag")
    parser.add_argument("--polyT-strict", type=str, default="true", choices=["true", "false"])
    parser.add_argument("--polyG-strict", type=str, default="false", choices=["true", "false"])
    parser.add_argument("--check-bases", default="ACGT", help="Bases to scan")
    parser.add_argument("--return-run-positions", type=str, default="false", choices=["true", "false"])
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    result = check_homopolymer_runs(
        sequence=args.sequence,
        homopolymer_min_run=args.homopolymer_min_run,
        polyT_strict=args.polyT_strict == "true",
        polyG_strict=args.polyG_strict == "true",
        check_bases=args.check_bases,
        return_run_positions=args.return_run_positions == "true",
    )
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
