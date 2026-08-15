"""MCP Tool: compute_dinucleotide_composition

Deterministic dinucleotide/k-mer composition feature extractor for SpCas9 spacer sequences.

Tier: cheap / deterministic
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import PAMSiteRow, ToolResult, validate_dna_sequence


def compute_dinucleotide_composition(
    sequence: str,
    spacer_length: int = 20,
    window_size: int = 2,
    return_full_matrix: bool = False,
    normalize_counts: bool = False,
    target_dinucleotides: list[str] | None = None,
) -> ToolResult:
    """Extract position-anchored k-mer/dinucleotide features from a spacer sequence.

    This tool is a feature extractor, NOT an efficacy predictor.
    It produces position-anchored dinucleotide composition for downstream
    ML/scoring systems.

    Args:
        sequence: DNA sequence to analyze (already in scoring orientation).
        spacer_length: Expected spacer length (default 20 for SpCas9).
        window_size: k-mer window size (default 2 for dinucleotides).
        return_full_matrix: Whether to include per-position anchored rows.
        normalize_counts: Whether to include normalized frequencies.
        target_dinucleotides: Optional list of specific k-mers to report.

    Returns:
        ToolResult with dinucleotide composition in summary/metadata.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if target_dinucleotides is None:
        target_dinucleotides = []

    # --- Validate sequence ---
    try:
        seq = validate_dna_sequence(sequence, allow_iupac=True)
    except ValueError as e:
        return ToolResult(tool="compute_dinucleotide_composition", errors=[str(e)])

    seq_len = len(seq)

    # --- Validate spacer_length ---
    if not isinstance(spacer_length, int) or spacer_length <= 0:
        errors.append(f"spacer_length must be a positive integer, got {spacer_length}")
        if errors:
            return ToolResult(tool="compute_dinucleotide_composition", errors=errors)

    # --- Validate window_size ---
    if not isinstance(window_size, int) or window_size < 1:
        errors.append(f"window_size must be a positive integer >= 1, got {window_size}")
    elif window_size > spacer_length:
        errors.append(
            f"window_size ({window_size}) must be <= spacer_length ({spacer_length})"
        )

    # --- Validate target_dinucleotides ---
    valid_dna = set("ACGTacgtRYSWKMBDHVNryswkmbdhvn")
    if not isinstance(target_dinucleotides, list):
        errors.append("target_dinucleotides must be a list of strings")
    else:
        for t in target_dinucleotides:
            if not isinstance(t, str):
                errors.append(f"target_dinucleotides entries must be strings, got {type(t).__name__}")
            elif len(t) != window_size:
                errors.append(
                    f"target_dinucleotide '{t}' has length {len(t)}, expected {window_size}"
                )
            else:
                invalid_chars = set(t) - valid_dna
                if invalid_chars:
                    errors.append(
                        f"target_dinucleotide '{t}' contains invalid characters: {sorted(invalid_chars)}"
                    )
        if len(target_dinucleotides) != len(set(t.upper() for t in target_dinucleotides)):
            warnings.append("target_dinucleotides contains duplicates; deduplicated automatically")

    if errors:
        return ToolResult(tool="compute_dinucleotide_composition", errors=errors)

    # --- Extract spacer ---
    if seq_len < spacer_length:
        errors.append(
            f"Sequence length ({seq_len}) is shorter than spacer_length ({spacer_length})"
        )
        return ToolResult(tool="compute_dinucleotide_composition", errors=errors)

    spacer = seq[:spacer_length]

    # --- Compute k-mer windows ---
    total_windows = spacer_length - window_size + 1
    counts: dict[str, int] = {}
    full_matrix: list[dict] = []

    for i in range(total_windows):
        kmer = spacer[i : i + window_size]
        kmer_upper = kmer.upper()

        counts[kmer_upper] = counts.get(kmer_upper, 0) + 1

        if return_full_matrix:
            full_matrix.append({
                "position_start": i + 1,  # 1-based biological position
                "position_end": i + window_size,
                "kmer": kmer_upper,
                "occurrence_index": counts[kmer_upper],
            })

    # --- Compute frequencies ---
    frequencies: dict[str, float] = {}
    if normalize_counts:
        frequencies = {k: v / total_windows for k, v in counts.items()}

    # --- Apply target filter ---
    if target_dinucleotides:
        # Deduplicate targets (case-insensitive)
        seen = set()
        unique_targets = []
        for t in target_dinucleotides:
            t_upper = t.upper()
            if t_upper not in seen:
                seen.add(t_upper)
                unique_targets.append(t_upper)

        # Filter counts/frequencies to only requested targets
        filtered_counts = {t: counts.get(t, 0) for t in unique_targets}
        filtered_frequencies = {t: frequencies.get(t, 0.0) for t in unique_targets} if normalize_counts else {}

        # Filter full matrix to only requested targets
        if return_full_matrix:
            full_matrix = [row for row in full_matrix if row["kmer"] in seen]

        counts = filtered_counts
        frequencies = filtered_frequencies
        target_reported = unique_targets
    else:
        target_reported = sorted(counts.keys())

    # --- Build result ---
    row = PAMSiteRow(
        protospacer=spacer,
        pam=None,
        pam_type=None,
    )

    summary = {
        "sequence_length": seq_len,
        "spacer_length": spacer_length,
        "window_size": window_size,
        "total_windows": total_windows,
        "counts": counts,
        "target_dinucleotides": target_reported,
        "normalize_counts": normalize_counts,
        "return_full_matrix": return_full_matrix,
    }

    if normalize_counts:
        summary["frequencies"] = frequencies

    if return_full_matrix:
        summary["full_matrix"] = full_matrix
    else:
        summary["full_matrix"] = None

    metadata = {
        "position_convention": "1-based biological positions (position 1 = 5' end, position N = PAM-proximal)",
        "window_formula": f"total_windows = spacer_length - window_size + 1 = {spacer_length} - {window_size} + 1 = {total_windows}",
        "scoring_note": (
            "Dinucleotide composition features for downstream ML/scoring systems. "
            "NOT an efficacy prediction. Does not reproduce Rule Set 2/3 or Azimuth."
        ),
    }

    return ToolResult(
        tool="compute_dinucleotide_composition",
        rows=[row],
        summary=summary,
        errors=errors,
        warnings=warnings,
        metadata=metadata,
    )


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="VEYRA compute_dinucleotide_composition tool")
    parser.add_argument("--sequence", "-s", required=True, help="DNA sequence")
    parser.add_argument("--spacer-length", type=int, default=20, help="Spacer length")
    parser.add_argument("--window-size", type=int, default=2, help="k-mer window size")
    parser.add_argument("--return-full-matrix", action="store_true", help="Include position-anchored matrix")
    parser.add_argument("--normalize-counts", action="store_true", help="Include normalized frequencies")
    parser.add_argument("--target-dinucleotides", nargs="*", default=[], help="Specific k-mers to report")
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    result = compute_dinucleotide_composition(
        sequence=args.sequence,
        spacer_length=args.spacer_length,
        window_size=args.window_size,
        return_full_matrix=args.return_full_matrix,
        normalize_counts=args.normalize_counts,
        target_dinucleotides=args.target_dinucleotides or [],
    )
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
