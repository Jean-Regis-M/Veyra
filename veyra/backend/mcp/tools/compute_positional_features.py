"""MCP Tool: compute_positional_features

Deterministic positional nucleotide-feature extractor for SpCas9 spacer sequences.

Tier: cheap / deterministic
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import PAMSiteRow, ToolResult, validate_dna_sequence


_DEFAULT_ALPHABET = "ACGT"


def _build_onehot(base: str, alphabet: str) -> dict[str, int]:
    """Build a one-hot encoding dict for a single base."""
    upper = base.upper()
    return {a: (1 if a == upper else 0) for a in alphabet}


def _is_ambiguous(base: str, alphabet: str) -> bool:
    """Return True if the base is not in the canonical alphabet."""
    return base.upper() not in alphabet


def compute_positional_features(
    sequence: str,
    spacer_length: int = 20,
    return_onehot: bool = True,
    check_position20_bias: bool = True,
    custom_check_positions: list[int] | None = None,
    onehot_alphabet: str = _DEFAULT_ALPHABET,
) -> ToolResult:
    """Extract positional nucleotide features from a spacer sequence.

    This tool is a feature extractor, NOT an efficacy predictor.
    It produces positional identity, one-hot encoding, and optional
    SpCas9 position-20 heuristic checks for downstream ML/scoring systems.

    Args:
        sequence: DNA sequence to analyze (already in scoring orientation).
        spacer_length: Expected spacer length (default 20 for SpCas9).
        return_onehot: Whether to include per-position one-hot encoding.
        check_position20_bias: Whether to check position-20 PAM-proximal bias.
        custom_check_positions: Optional list of 1-based positions to extract.
        onehot_alphabet: Alphabet for one-hot encoding (default "ACGT").

    Returns:
        ToolResult with positional features in summary/metadata.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if custom_check_positions is None:
        custom_check_positions = []

    # --- Validate sequence ---
    try:
        seq = validate_dna_sequence(sequence, allow_iupac=True)
    except ValueError as e:
        return ToolResult(tool="compute_positional_features", errors=[str(e)])

    seq_len = len(seq)

    # --- Validate spacer_length ---
    if not isinstance(spacer_length, int) or spacer_length <= 0:
        errors.append(f"spacer_length must be a positive integer, got {spacer_length}")
        if errors:
            return ToolResult(tool="compute_positional_features", errors=errors)

    # --- Validate onehot_alphabet ---
    if not onehot_alphabet or not isinstance(onehot_alphabet, str):
        errors.append("onehot_alphabet must be a non-empty string")
    else:
        if len(set(onehot_alphabet)) != len(onehot_alphabet):
            errors.append("onehot_alphabet contains duplicate characters")
        if not all(c.isalpha() for c in onehot_alphabet):
            errors.append("onehot_alphabet must contain only alphabetic characters")

    # --- Validate custom positions ---
    if not isinstance(custom_check_positions, list):
        errors.append("custom_check_positions must be a list of integers")
    else:
        for pos in custom_check_positions:
            if not isinstance(pos, int):
                errors.append(f"custom_check_positions entries must be integers, got {type(pos).__name__}: {pos}")
            elif pos < 1:
                errors.append(f"custom_check_positions must use 1-based positions >= 1, got {pos}")
            elif pos > spacer_length:
                errors.append(
                    f"custom_check_position {pos} exceeds spacer_length ({spacer_length})"
                )

    if errors:
        return ToolResult(tool="compute_positional_features", errors=errors)

    # --- Extract spacer for scoring ---
    # If sequence is longer than spacer_length, use the first spacer_length
    # bases (5' end). This matches upstream PAM/candidate logic which
    # provides the spacer in the correct orientation.
    if seq_len < spacer_length:
        errors.append(
            f"Sequence length ({seq_len}) is shorter than spacer_length ({spacer_length})"
        )
        return ToolResult(tool="compute_positional_features", errors=errors)

    spacer = seq[:spacer_length]

    # --- Build per-position features ---
    positions: list[dict] = []
    onehot_list: list[dict] = []

    for i, base in enumerate(spacer):
        bio_pos = i + 1  # 1-based biological position
        is_ambig = _is_ambiguous(base, onehot_alphabet)

        pos_data: dict = {
            "position": bio_pos,
            "base": base,
        }
        positions.append(pos_data)

        if return_onehot:
            oh: dict = {"position": bio_pos, "base": base, "encoding": {}}
            if is_ambig:
                oh["encoding"] = {a: 0 for a in onehot_alphabet}
                oh["encoded"] = False
            else:
                oh["encoding"] = _build_onehot(base, onehot_alphabet)
                oh["encoded"] = True
            onehot_list.append(oh)

    # --- Position-20 bias check ---
    position20_base: str | None = None
    position20_bias_flag: str = "neutral"

    if check_position20_bias and spacer_length >= 20:
        # Position 20 = PAM-proximal nucleotide (biological 1-based)
        position20_base = spacer[19]

        # Heuristic: G = favored, T = disfavored, A/C = neutral
        if position20_base == "G":
            position20_bias_flag = "favored"
        elif position20_base == "T":
            position20_bias_flag = "disfavored"
        else:
            position20_bias_flag = "neutral"

    # --- Custom position checks ---
    custom_positions: list[dict] = []
    if custom_check_positions:
        for pos in sorted(custom_check_positions):
            base_at_pos = spacer[pos - 1]
            custom_positions.append({
                "position": pos,
                "base": base_at_pos,
            })

    # --- Build result ---
    row = PAMSiteRow(
        protospacer=spacer,
        pam=None,
        pam_type=None,
    )

    summary = {
        "sequence_length": seq_len,
        "spacer_length": spacer_length,
        "spacer": spacer,
        "position20_base": position20_base,
        "position20_bias_flag": position20_bias_flag,
        "custom_positions": custom_positions,
    }

    if return_onehot:
        summary["onehot"] = onehot_list

    metadata = {
        "onehot_alphabet": onehot_alphabet,
        "check_position20_bias": check_position20_bias,
        "custom_check_positions": custom_check_positions,
        "position_convention": "1-based biological positions (position 1 = 5' end, position N = PAM-proximal)",
        "scoring_note": (
            "Positional features for downstream ML/scoring systems. "
            "NOT an efficacy prediction. Position-20 heuristic is a categorical "
            "feature, not a numerical penalty."
        ),
    }

    return ToolResult(
        tool="compute_positional_features",
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

    parser = argparse.ArgumentParser(description="VEYRA compute_positional_features tool")
    parser.add_argument("--sequence", "-s", required=True, help="DNA sequence")
    parser.add_argument("--spacer-length", type=int, default=20, help="Spacer length")
    parser.add_argument("--return-onehot", action="store_true", default=True)
    parser.add_argument("--no-onehot", action="store_true", help="Disable one-hot output")
    parser.add_argument("--check-position20-bias", action="store_true", default=True)
    parser.add_argument("--no-position20-bias", action="store_true", help="Disable position-20 check")
    parser.add_argument("--custom-check-positions", nargs="*", type=int, default=[])
    parser.add_argument("--onehot-alphabet", default="ACGT", help="One-hot alphabet")
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    result = compute_positional_features(
        sequence=args.sequence,
        spacer_length=args.spacer_length,
        return_onehot=not args.no_onehot,
        check_position20_bias=not args.no_position20_bias,
        custom_check_positions=args.custom_check_positions or [],
        onehot_alphabet=args.onehot_alphabet,
    )
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
