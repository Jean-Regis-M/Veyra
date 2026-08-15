"""MCP Tool: compute_seed_gc

Deterministic PAM-proximal seed GC-content feature extractor for SpCas9 guide candidates.

Tier: cheap / deterministic
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import PAMSiteRow, ToolResult, validate_dna_sequence
from mcp.tools.compute_gc_content import _gc_content

_SUPPORTED_ANCHORS = frozenset({"pam_proximal"})


def compute_seed_gc(
    sequence: str,
    seed_region_length: int = 10,
    seed_anchor: str = "pam_proximal",
    seed_min_threshold: float = 0.20,
    seed_max_threshold: float = 0.80,
    compute_seed_distal_delta: bool = False,
    round_decimals: int = 3,
) -> ToolResult:
    """Compute GC content over the PAM-proximal seed region of a spacer.

    This tool is a feature extractor, NOT a specificity predictor.
    It produces seed-region GC features for downstream VEYRA reasoning/ranking.

    Position convention (VEYRA biological 1-based):
        position 1 = 5' end of spacer
        position N = PAM-proximal nucleotide

    For seed_anchor = "pam_proximal" and seed_region_length = 10
    on a 20-nt spacer:
        seed = positions 11-20 (PAM-proximal 10 nt)
        distal = positions 1-10

    Args:
        sequence: DNA sequence (already in scoring orientation).
        seed_region_length: Length of the seed region (default 10).
        seed_anchor: Anchor point for seed extraction ("pam_proximal").
        seed_min_threshold: Minimum GC fraction for pass filter.
        seed_max_threshold: Maximum GC fraction for pass filter.
        compute_seed_distal_delta: Whether to compute distal GC and delta.
        round_decimals: Decimal places for rounding output values.

    Returns:
        ToolResult with seed GC features in summary.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- Validate sequence ---
    try:
        seq = validate_dna_sequence(sequence, allow_iupac=True)
    except ValueError as e:
        return ToolResult(tool="compute_seed_gc", errors=[str(e)])

    seq_len = len(seq)

    # --- Validate seed_region_length ---
    if not isinstance(seed_region_length, int) or seed_region_length <= 0:
        errors.append(f"seed_region_length must be a positive integer, got {seed_region_length}")
    elif seed_region_length > seq_len:
        errors.append(
            f"seed_region_length ({seed_region_length}) exceeds sequence length ({seq_len})"
        )

    # --- Validate seed_anchor ---
    if not isinstance(seed_anchor, str) or seed_anchor not in _SUPPORTED_ANCHORS:
        errors.append(
            f"seed_anchor must be one of {sorted(_SUPPORTED_ANCHORS)}, got '{seed_anchor}'"
        )

    # --- Validate thresholds ---
    if not isinstance(seed_min_threshold, (int, float)):
        errors.append(f"seed_min_threshold must be numeric, got {type(seed_min_threshold).__name__}")
    if not isinstance(seed_max_threshold, (int, float)):
        errors.append(f"seed_max_threshold must be numeric, got {type(seed_max_threshold).__name__}")
    if isinstance(seed_min_threshold, (int, float)) and isinstance(seed_max_threshold, (int, float)):
        if not (0.0 <= seed_min_threshold <= 1.0):
            errors.append(f"seed_min_threshold must be in [0, 1], got {seed_min_threshold}")
        if not (0.0 <= seed_max_threshold <= 1.0):
            errors.append(f"seed_max_threshold must be in [0, 1], got {seed_max_threshold}")
        if seed_min_threshold > seed_max_threshold:
            errors.append(
                f"seed_min_threshold ({seed_min_threshold}) must be <= seed_max_threshold ({seed_max_threshold})"
            )

    # --- Validate round_decimals ---
    if not isinstance(round_decimals, int) or round_decimals < 0:
        errors.append(f"round_decimals must be a non-negative integer, got {round_decimals}")

    if errors:
        return ToolResult(tool="compute_seed_gc", errors=errors)

    # --- Extract seed region ---
    # For pam_proximal: seed is the last seed_region_length positions
    # Biological positions: (seq_len - seed_region_length + 1) to seq_len
    seed_start = seq_len - seed_region_length + 1  # 1-based biological
    seed_end = seq_len  # 1-based biological
    # Python slice: 0-based start = seed_start - 1, end = seed_end
    seed_seq = seq[seed_start - 1 : seed_end]

    # --- Compute seed GC (full precision) ---
    seed_gc = _gc_content(seed_seq)

    # --- Threshold filter (uses full precision, not rounded) ---
    passes_seed_filter = seed_min_threshold <= seed_gc <= seed_max_threshold

    # --- Distal GC and delta ---
    distal_gc = None
    seed_distal_gc_delta = None

    if compute_seed_distal_delta:
        distal_seq = seq[: seed_start - 1]  # positions 1 to (seed_start - 1)
        if distal_seq:
            distal_gc = _gc_content(distal_seq)
            seed_distal_gc_delta = seed_gc - distal_gc
        else:
            # Distal region is empty — cannot compute delta
            warnings.append(
                "Distal region is empty (seed spans entire sequence); "
                "seed_distal_gc_delta cannot be computed."
            )
            distal_gc = None
            seed_distal_gc_delta = None

    # --- Round output values ---
    seed_gc_rounded = round(seed_gc, round_decimals)
    distal_gc_rounded = round(distal_gc, round_decimals) if distal_gc is not None else None
    delta_rounded = round(seed_distal_gc_delta, round_decimals) if seed_distal_gc_delta is not None else None

    # --- Build result ---
    row = PAMSiteRow(
        protospacer=seq[:20] if seq_len >= 20 else seq,
        pam=None,
        pam_type=None,
    )

    summary = {
        "sequence_length": seq_len,
        "seed_region_length": seed_region_length,
        "seed_anchor": seed_anchor,
        "seed_start_position": seed_start,
        "seed_end_position": seed_end,
        "seed_gc_content": seed_gc_rounded,
        "passes_seed_filter": passes_seed_filter,
        "distal_gc_content": distal_gc_rounded,
        "seed_distal_gc_delta": delta_rounded,
    }

    metadata = {
        "seed_min_threshold": seed_min_threshold,
        "seed_max_threshold": seed_max_threshold,
        "compute_seed_distal_delta": compute_seed_distal_delta,
        "round_decimals": round_decimals,
        "position_convention": "1-based biological positions (position 1 = 5' end, position N = PAM-proximal)",
        "gc_ambiguity_policy": "IUPAC ambiguous bases counted in denominator but not GC numerator (consistent with compute_gc_content)",
        "scoring_note": (
            "Seed GC feature for downstream VEYRA reasoning/ranking. "
            "NOT a specificity or efficacy prediction. "
            "Thresholds are configurable heuristics, not universal biological limits."
        ),
    }

    return ToolResult(
        tool="compute_seed_gc",
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

    parser = argparse.ArgumentParser(description="VEYRA compute_seed_gc tool")
    parser.add_argument("--sequence", "-s", required=True, help="DNA sequence")
    parser.add_argument("--seed-region-length", type=int, default=10, help="Seed region length")
    parser.add_argument("--seed-anchor", default="pam_proximal", help="Seed anchor point")
    parser.add_argument("--seed-min-threshold", type=float, default=0.20, help="Min GC threshold")
    parser.add_argument("--seed-max-threshold", type=float, default=0.80, help="Max GC threshold")
    parser.add_argument("--compute-seed-distal-delta", action="store_true",
                        help="Compute distal GC and delta")
    parser.add_argument("--round-decimals", type=int, default=3, help="Decimal places for rounding")
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    result = compute_seed_gc(
        sequence=args.sequence,
        seed_region_length=args.seed_region_length,
        seed_anchor=args.seed_anchor,
        seed_min_threshold=args.seed_min_threshold,
        seed_max_threshold=args.seed_max_threshold,
        compute_seed_distal_delta=args.compute_seed_distal_delta,
        round_decimals=args.round_decimals,
    )
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
