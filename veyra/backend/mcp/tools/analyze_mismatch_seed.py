"""MCP Tool: analyze_mismatch_seed

Analyze mismatches and bulges in the seed region of a CRISPR off-target candidate.

Tier 1 — SEED ANALYSIS

Cost: cheap / deterministic
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import PAMSiteRow, ToolResult, validate_dna_sequence


def analyze_mismatch_seed(
    spacer_sequence: str,
    candidate_sequence: str,
    bulge_type: str = "X",
    bulge_size: int = 0,
    bulge_position: int | None = None,
    aligned_guide: str | None = None,
    aligned_candidate: str | None = None,
    seed_region_length: int = 10,
    pam_pattern: str = "NGG",
) -> ToolResult:
    """Analyze mismatches and bulges in the seed region of an off-target candidate.

    Performs alignment-aware seed analysis for both ordinary mismatches and
    bulged alignments. Handles positional correspondence after indels.

    VEYRA position convention:
    - Position 1 = 5' end of spacer
    - Position N = PAM-proximal nucleotide

    For SpCas9 with seed_region_length=10:
    - Seed region: positions 11-20 (PAM-proximal 10 nt)
    - Distal region: positions 1-10

    Args:
        spacer_sequence: The wild-type guide/spacer sequence (20nt).
        candidate_sequence: The candidate off-target sequence.
        bulge_type: "X" (no bulge), "DNA", or "RNA".
        bulge_size: Size of the bulge (0 for no bulge).
        bulge_position: Position of the bulge in the alignment (0-based).
        aligned_guide: Aligned guide sequence with gaps (from Cas-OFFinder).
        aligned_candidate: Aligned candidate sequence with gaps (from Cas-OFFinder).
        seed_region_length: Length of the seed region (default 10).
        pam_pattern: PAM pattern for context.

    Returns:
        ToolResult with seed analysis summary.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Validate inputs
    try:
        spacer = validate_dna_sequence(spacer_sequence)
    except ValueError as e:
        return ToolResult(tool="analyze_mismatch_seed", errors=[str(e)])

    try:
        candidate = validate_dna_sequence(candidate_sequence)
    except ValueError as e:
        return ToolResult(tool="analyze_mismatch_seed", errors=[str(e)])

    if bulge_type not in ("X", "DNA", "RNA"):
        return ToolResult(
            tool="analyze_mismatch_seed",
            errors=[f"bulge_type must be 'X', 'DNA', or 'RNA', got '{bulge_type}'"],
        )

    if bulge_size < 0:
        return ToolResult(
            tool="analyze_mismatch_seed",
            errors=[f"bulge_size must be >= 0, got {bulge_size}"],
        )

    if seed_region_length < 1 or seed_region_length > len(spacer):
        return ToolResult(
            tool="analyze_mismatch_seed",
            errors=[f"seed_region_length must be 1-{len(spacer)}, got {seed_region_length}"],
        )

    spacer_len = len(spacer)

    # For equal-length comparisons (no bulge)
    if bulge_type == "X" or bulge_size == 0:
        # Simple positional comparison
        min_len = min(len(spacer), len(candidate))
        mismatch_positions = []
        for i in range(min_len):
            if spacer[i] != candidate[i]:
                mismatch_positions.append(i)

        # Seed region: positions [spacer_len - seed_region_length, spacer_len) in 0-based
        seed_start = spacer_len - seed_region_length
        seed_mismatches = [p for p in mismatch_positions if p >= seed_start]
        distal_mismatches = [p for p in mismatch_positions if p < seed_start]

        summary = {
            "spacer_length": spacer_len,
            "candidate_length": len(candidate),
            "seed_region_length": seed_region_length,
            "seed_start_position": seed_start + 1,  # 1-based
            "seed_end_position": spacer_len,  # 1-based
            "bulge_type": "X",
            "bulge_size": 0,
            "bulge_in_seed": False,
            "total_mismatches": len(mismatch_positions),
            "seed_mismatch_count": len(seed_mismatches),
            "distal_mismatch_count": len(distal_mismatches),
            "has_seed_mismatch": len(seed_mismatches) > 0,
            "mismatch_positions_0based": mismatch_positions,
            "seed_mismatch_positions_0based": seed_mismatches,
            "distal_mismatch_positions_0based": distal_mismatches,
        }

    else:
        # Alignment-aware analysis for bulged candidates
        if not aligned_guide or not aligned_candidate:
            # Fall back to simple comparison if alignment not provided
            warnings.append("Alignment not provided for bulged candidate. Using simplified analysis.")

            # For bulges, candidate may be different length
            min_len = min(len(spacer), len(candidate))
            mismatch_positions = []
            for i in range(min_len):
                if spacer[i] != candidate[i]:
                    mismatch_positions.append(i)

            seed_start = spacer_len - seed_region_length
            seed_mismatches = [p for p in mismatch_positions if p >= seed_start]
            distal_mismatches = [p for p in mismatch_positions if p < seed_start]

            summary = {
                "spacer_length": spacer_len,
                "candidate_length": len(candidate),
                "seed_region_length": seed_region_length,
                "seed_start_position": seed_start + 1,
                "seed_end_position": spacer_len,
                "bulge_type": bulge_type,
                "bulge_size": bulge_size,
                "bulge_in_seed": False,
                "total_mismatches": len(mismatch_positions),
                "seed_mismatch_count": len(seed_mismatches),
                "distal_mismatch_count": len(distal_mismatches),
                "has_seed_mismatch": len(seed_mismatches) > 0,
                "mismatch_positions_0based": mismatch_positions,
                "seed_mismatch_positions_0based": seed_mismatches,
                "distal_mismatch_positions_0based": distal_mismatches,
                "warning": "Analysis simplified due to missing alignment",
            }
        else:
            # Parse the alignment to map positions correctly
            guide_pos = 0
            candidate_pos = 0
            events = []  # list of (event_type, guide_pos_0based, candidate_pos_0based, guide_base, candidate_base)

            seed_start = spacer_len - seed_region_length
            bulge_in_seed = False
            seed_mismatch_count = 0
            distal_mismatch_count = 0
            mismatch_positions = []
            seed_mismatch_positions = []
            distal_mismatch_positions = []

            for i in range(len(aligned_guide)):
                g_base = aligned_guide[i]
                c_base = aligned_candidate[i]

                if g_base == "-":
                    # RNA bulge: extra base in candidate
                    events.append(("RNA_BULGE", None, candidate_pos, "-", c_base))
                    candidate_pos += 1
                elif c_base == "-":
                    # DNA bulge: extra base in guide
                    events.append(("DNA_BULGE", guide_pos, None, g_base, "-"))
                    if guide_pos >= seed_start:
                        bulge_in_seed = True
                    guide_pos += 1
                else:
                    # Both have bases - check for mismatch
                    if g_base.upper() != c_base.upper():
                        # Mismatch (lowercase in candidate = mismatch)
                        events.append(("MISMATCH", guide_pos, candidate_pos, g_base, c_base.upper()))
                        mismatch_positions.append(guide_pos)
                        if guide_pos >= seed_start:
                            seed_mismatch_count += 1
                            seed_mismatch_positions.append(guide_pos)
                        else:
                            distal_mismatch_count += 1
                            distal_mismatch_positions.append(guide_pos)
                    guide_pos += 1
                    candidate_pos += 1

            # Check if bulge position is in seed
            if bulge_position is not None:
                # bulge_position is in alignment coordinates
                # Need to convert to guide coordinates
                align_pos = 0
                guide_pos_at_bulge = None
                for i in range(len(aligned_guide)):
                    if i == bulge_position:
                        guide_pos_at_bulge = guide_pos
                        break
                    if aligned_guide[i] != "-":
                        guide_pos += 1
                    if aligned_candidate[i] != "-":
                        pass  # candidate_pos tracking not needed here

                if guide_pos_at_bulge is not None and guide_pos_at_bulge >= seed_start:
                    bulge_in_seed = True

            summary = {
                "spacer_length": spacer_len,
                "candidate_length": len(candidate),
                "seed_region_length": seed_region_length,
                "seed_start_position": seed_start + 1,
                "seed_end_position": spacer_len,
                "bulge_type": bulge_type,
                "bulge_size": bulge_size,
                "bulge_in_seed": bulge_in_seed,
                "total_mismatches": len(mismatch_positions),
                "seed_mismatch_count": seed_mismatch_count,
                "distal_mismatch_count": distal_mismatch_count,
                "has_seed_mismatch": seed_mismatch_count > 0,
                "mismatch_positions_0based": mismatch_positions,
                "seed_mismatch_positions_0based": seed_mismatch_positions,
                "distal_mismatch_positions_0based": distal_mismatch_positions,
                "events": events,
                "aligned_guide": aligned_guide,
                "aligned_candidate": aligned_candidate,
            }

    return ToolResult(
        tool="analyze_mismatch_seed",
        rows=[],
        summary=summary,
        errors=errors,
        warnings=warnings,
        metadata={
            "position_convention": "1-based biological positions",
            "position_1": "5' end of spacer",
            "position_n": "PAM-proximal nucleotide",
            "seed_definition": f"PAM-proximal {seed_region_length} nt",
        },
    )


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VEYRA analyze_mismatch_seed tool")
    parser.add_argument("--spacer", "-s", required=True, help="Wild-type spacer sequence")
    parser.add_argument("--candidate", "-c", required=True, help="Candidate sequence")
    parser.add_argument("--bulge-type", default="X", choices=["X", "DNA", "RNA"])
    parser.add_argument("--bulge-size", type=int, default=0)
    parser.add_argument("--bulge-position", type=int, default=None)
    parser.add_argument("--aligned-guide", help="Aligned guide sequence")
    parser.add_argument("--aligned-candidate", help="Aligned candidate sequence")
    parser.add_argument("--seed-length", type=int, default=10)
    parser.add_argument("--pam", default="NGG")
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    result = analyze_mismatch_seed(
        spacer_sequence=args.spacer,
        candidate_sequence=args.candidate,
        bulge_type=args.bulge_type,
        bulge_size=args.bulge_size,
        bulge_position=args.bulge_position,
        aligned_guide=args.aligned_guide,
        aligned_candidate=args.aligned_candidate,
        seed_region_length=args.seed_length,
        pam_pattern=args.pam,
    )
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
