"""MCP Tool: compute_gc_content

Deterministic GC-content feature extractor for DNA sequences.

Tier: cheap / deterministic
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import PAMSiteRow, ToolResult, validate_dna_sequence

# Ambiguous IUPAC bases treated as "not G or C" — they do NOT contribute to
# the GC numerator but DO count in the denominator.  This is consistent with
# the standard convention where ambiguous bases represent uncertainty about
# which specific base is present; none of the possibilities are G or C in
# the ambiguity classes that include non-GC bases.  For bases like S (G or C)
# we conservatively do NOT count them as GC because the ambiguity means we
# cannot be certain.  The calling layer can decide to pre-filter or handle
# ambiguous sequences differently if needed.

_GC_BASES = frozenset("GCgc")


def _gc_content(seq: str) -> float:
    """Compute GC content as a fraction in [0, 1].

    Ambiguous IUPAC bases are NOT counted as G or C but ARE counted in
    the denominator.
    """
    if not seq:
        return 0.0
    upper = seq.upper()
    gc = sum(1 for ch in upper if ch in _GC_BASES)
    return gc / len(upper)


def compute_gc_content(
    sequence: str,
    gc_window_size: int = 5,
    gc_split_ratio: float = 0.5,
    gc_min_threshold: float = 0.20,
    gc_max_threshold: float = 0.80,
    include_sliding_window: bool = True,
    include_half_split: bool = True,
    round_decimals: int = 3,
) -> ToolResult:
    """Compute GC content and optional derived features for a DNA sequence.

    Args:
        sequence: DNA sequence (IUPAC characters allowed).
        gc_window_size: Sliding window size in nucleotides.
        gc_split_ratio: Fraction of sequence for 5' half (0–1).
        gc_min_threshold: Minimum GC for pass filter.
        gc_max_threshold: Maximum GC for pass filter.
        include_sliding_window: Whether to compute sliding-window GC.
        include_half_split: Whether to compute 5'/3' split GC.
        round_decimals: Decimal places for rounding.

    Returns:
        ToolResult with GC content features in summary.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- Validate sequence ---
    try:
        seq = validate_dna_sequence(sequence, allow_iupac=True)
    except ValueError as e:
        return ToolResult(tool="compute_gc_content", errors=[str(e)])

    seq_len = len(seq)

    # --- Validate parameters ---
    if not isinstance(gc_window_size, int) or gc_window_size <= 0:
        errors.append(f"gc_window_size must be a positive integer, got {gc_window_size}")
    if not (0.0 <= gc_split_ratio <= 1.0):
        errors.append(f"gc_split_ratio must be in [0, 1], got {gc_split_ratio}")
    if not (0.0 <= gc_min_threshold <= 1.0):
        errors.append(f"gc_min_threshold must be in [0, 1], got {gc_min_threshold}")
    if not (0.0 <= gc_max_threshold <= 1.0):
        errors.append(f"gc_max_threshold must be in [0, 1], got {gc_max_threshold}")
    if gc_min_threshold > gc_max_threshold:
        errors.append(
            f"gc_min_threshold ({gc_min_threshold}) must be <= gc_max_threshold ({gc_max_threshold})"
        )
    if not isinstance(round_decimals, int) or round_decimals < 0:
        errors.append(f"round_decimals must be a non-negative integer, got {round_decimals}")

    if errors:
        return ToolResult(tool="compute_gc_content", errors=errors)

    # --- Overall GC ---
    gc = _gc_content(seq)
    gc_rounded = round(gc, round_decimals)

    # --- 5'/3' half split ---
    gc_5prime = None
    gc_3prime = None
    if include_half_split:
        # split_index = floor(seq_len * gc_split_ratio)
        # For ratio=0.5: even length splits evenly, odd gets floor
        split_idx = int(seq_len * gc_split_ratio)
        # Clamp to valid range [1, seq_len-1] so both halves are non-empty
        split_idx = max(1, min(split_idx, seq_len - 1))
        gc_5prime = round(_gc_content(seq[:split_idx]), round_decimals)
        gc_3prime = round(_gc_content(seq[split_idx:]), round_decimals)

    # --- Sliding window ---
    sliding_windows: list[dict] = []
    if include_sliding_window:
        if gc_window_size > seq_len:
            warnings.append(
                f"Window size ({gc_window_size}) exceeds sequence length ({seq_len}); "
                "sliding window skipped."
            )
        else:
            for i in range(seq_len - gc_window_size + 1):
                window = seq[i : i + gc_window_size]
                sliding_windows.append({
                    "start": i,           # 0-based half-open
                    "end": i + gc_window_size,
                    "gc": round(_gc_content(window), round_decimals),
                })

    # --- Threshold filter ---
    passes_basic_filter = gc_min_threshold <= gc <= gc_max_threshold

    # --- Build result row ---
    row = PAMSiteRow(
        protospacer=seq[:20] if seq_len >= 20 else seq,
        pam=None,
        pam_type=None,
    )

    summary = {
        "sequence_length": seq_len,
        "gc_content": gc_rounded,
        "gc_5prime": gc_5prime,
        "gc_3prime": gc_3prime,
        "sliding_windows": sliding_windows,
        "passes_basic_filter": passes_basic_filter,
    }

    metadata = {
        "gc_window_size": gc_window_size,
        "gc_split_ratio": gc_split_ratio,
        "gc_min_threshold": gc_min_threshold,
        "gc_max_threshold": gc_max_threshold,
        "include_sliding_window": include_sliding_window,
        "include_half_split": include_half_split,
        "round_decimals": round_decimals,
        "scoring_note": "GC content is a sequence feature, NOT a CRISPR safety/efficacy claim.",
    }

    return ToolResult(
        tool="compute_gc_content",
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

    parser = argparse.ArgumentParser(description="VEYRA compute_gc_content tool")
    parser.add_argument("--sequence", "-s", required=True, help="DNA sequence")
    parser.add_argument("--gc-window-size", type=int, default=5)
    parser.add_argument("--gc-split-ratio", type=float, default=0.5)
    parser.add_argument("--gc-min-threshold", type=float, default=0.20)
    parser.add_argument("--gc-max-threshold", type=float, default=0.80)
    parser.add_argument("--include-sliding-window", action="store_true", default=True)
    parser.add_argument("--no-sliding-window", action="store_true")
    parser.add_argument("--include-half-split", action="store_true", default=True)
    parser.add_argument("--no-half-split", action="store_true")
    parser.add_argument("--round-decimals", type=int, default=3)
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    result = compute_gc_content(
        sequence=args.sequence,
        gc_window_size=args.gc_window_size,
        gc_split_ratio=args.gc_split_ratio,
        gc_min_threshold=args.gc_min_threshold,
        gc_max_threshold=args.gc_max_threshold,
        include_sliding_window=not args.no_sliding_window,
        include_half_split=not args.no_half_split,
        round_decimals=args.round_decimals,
    )
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
