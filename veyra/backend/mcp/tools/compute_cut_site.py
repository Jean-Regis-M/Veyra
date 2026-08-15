"""MCP Tool: compute_cut_site

Deterministic coordinate/geometry tool for canonical SpCas9 cleavage-site
placement. This is NOT a cleavage-efficiency predictor.

Tier 1 — DETERMINISTIC / CHEAP

Cost: cheap / deterministic
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import PAMSiteRow, ToolResult


# ---------------------------------------------------------------------------
# Supported PAM configurations
# ---------------------------------------------------------------------------

_PAM_CONFIGS = {
    "SpCas9": {
        "pam_position": "3prime",
        "pam_length": 3,
        "default_cut_offset": -3,
        "default_spacer_length": 20,
    },
}


def compute_cut_site(
    spacer_start: int,
    spacer_length: int = 20,
    strand: str = "+",
    pam_position: str = "3prime",
    cut_offset_from_pam: int = -3,
    return_genomic_coord: bool = True,
    return_relative_coord: bool = True,
    chrom: str = "",
) -> ToolResult:
    """Compute the canonical SpCas9 cleavage-site position.

    This is a deterministic coordinate/geometry tool. It reports a predicted
    canonical SpCas9 cleavage anchor — NOT cleavage efficiency, NOT repair
    outcome, NOT experimental certainty.

    For canonical SpCas9:
        - protospacer = 20 nt
        - PAM = 3' of the protospacer in the guide orientation
        - canonical blunt cut anchor = ~3 bp upstream of PAM
        - relative cut is between spacer positions 17 and 18 (1-based, 5'→3')

    Coordinate convention: 0-based half-open for genomic coordinates.
    Biological positions: 1-based for relative cut site.

    Args:
        spacer_start: 0-based start coordinate of the protospacer on the
            reference strand.
        spacer_length: Length of the protospacer (default 20).
        strand: "+" or "-" indicating which strand the guide targets.
        pam_position: PAM orientation. Currently only "3prime" supported.
        cut_offset_from_pam: Offset from PAM start to cleavage boundary.
            Default -3 means 3 bp upstream of PAM (toward spacer).
        return_genomic_coord: Whether to compute absolute genomic coordinate.
        return_relative_coord: Whether to compute spacer-relative cut position.
        chrom: Chromosome label. Required when return_genomic_coord=True.

    Returns:
        ToolResult with cut_site_genomic, cut_site_relative, and metadata.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- Validate inputs ---
    if not isinstance(spacer_start, int) or spacer_start < 0:
        errors.append(f"spacer_start must be a non-negative integer, got {spacer_start!r}")
        return ToolResult(tool="compute_cut_site", errors=errors)

    if not isinstance(spacer_length, int) or spacer_length <= 0:
        errors.append(f"spacer_length must be a positive integer, got {spacer_length!r}")
        return ToolResult(tool="compute_cut_site", errors=errors)

    if strand not in ("+", "-"):
        errors.append(f"strand must be '+' or '-', got {strand!r}")
        return ToolResult(tool="compute_cut_site", errors=errors)

    if pam_position != "3prime":
        errors.append(f"pam_position must be '3prime' (only SpCas9 supported), got {pam_position!r}")
        return ToolResult(tool="compute_cut_site", errors=errors)

    if not isinstance(cut_offset_from_pam, int):
        errors.append(f"cut_offset_from_pam must be an integer, got {cut_offset_from_pam!r}")
        return ToolResult(tool="compute_cut_site", errors=errors)

    if not isinstance(return_genomic_coord, bool):
        errors.append(f"return_genomic_coord must be a boolean, got {return_genomic_coord!r}")
        return ToolResult(tool="compute_cut_site", errors=errors)

    if not isinstance(return_relative_coord, bool):
        errors.append(f"return_relative_coord must be a boolean, got {return_relative_coord!r}")
        return ToolResult(tool="compute_cut_site", errors=errors)

    if return_genomic_coord and not chrom:
        errors.append("chrom is required when return_genomic_coord=True")
        return ToolResult(tool="compute_cut_site", errors=errors)

    # --- Check for non-standard offset ---
    is_custom_offset = cut_offset_from_pam != _PAM_CONFIGS["SpCas9"]["default_cut_offset"]
    if is_custom_offset:
        warnings.append(
            f"Custom cut_offset_from_pam={cut_offset_from_pam} (canonical SpCas9 default is -3)"
        )

    # --- Compute spacer geometry (0-based half-open) ---
    spacer_end = spacer_start + spacer_length

    # PAM is 3' of the protospacer in the guide orientation.
    # For "+" strand: spacer [start, end), PAM at [end, end+pam_length)
    # For "-" strand: spacer [start, end), PAM at [start-pam_length, start)
    pam_length = _PAM_CONFIGS["SpCas9"]["pam_length"]

    if strand == "+":
        pam_start = spacer_end          # 0-based start of PAM
        pam_end = spacer_end + pam_length
    else:
        pam_start = spacer_start - pam_length
        pam_end = spacer_start

    # --- Compute relative cut position ---
    # The canonical SpCas9 cut occurs between positions 17 and 18 (1-based)
    # of the 20-nt protospacer. In 0-based terms, this is boundary 17.
    # More generally: cut_boundary = spacer_length + cut_offset_from_pam
    # For default: 20 + (-3) = 17 (0-based boundary between pos 17 and 18)
    relative_cut_boundary = spacer_length + cut_offset_from_pam

    cut_site_relative = None
    if return_relative_coord:
        cut_site_relative = relative_cut_boundary

    # --- Compute genomic cut coordinate ---
    cut_site_genomic = None
    if return_genomic_coord:
        if strand == "+":
            # For "+" strand, the cut boundary in genomic coords:
            # spacer_start (0-based) + relative_cut_boundary
            cut_site_genomic = spacer_start + relative_cut_boundary
        else:
            # For "-" strand, the spacer is on the reverse strand.
            # The PAM is upstream (lower coordinates).
            # The cut boundary maps to:
            # spacer_end (0-based exclusive) - relative_cut_boundary
            # In 0-based terms: spacer_end - relative_cut_boundary
            # = (spacer_start + spacer_length) - (spacer_length + cut_offset_from_pam)
            # = spacer_start - cut_offset_from_pam
            cut_site_genomic = spacer_end - relative_cut_boundary

    # --- Build result ---
    # The cut site is a boundary, not a nucleotide.
    # In 0-based half-open: cut_site_genomic is the boundary position.
    # In 1-based biological: cut_site_relative is between positions N and N+1.

    rows = [PAMSiteRow(
        chrom=chrom if return_genomic_coord else None,
        start=cut_site_genomic,
        end=cut_site_genomic + 1 if cut_site_genomic is not None else None,
        strand=strand,
        protospacer=None,
        pam=None,
        pam_type="SpCas9",
        mismatch_count=0,
        mismatch_positions=None,
        cfd_score=None,
        rs2_score=None,
        bulge_type="X",
        bulge_size=0,
        bulge_position=None,
        aligned_guide=None,
        aligned_candidate=None,
        cfd_status=None,
    )]

    # Compute spacer_end for metadata
    spacer_end_val = spacer_start + spacer_length

    summary = {
        "cut_site_genomic": cut_site_genomic,
        "cut_site_relative": cut_site_relative,
        "cut_site_relative_boundary": f"{relative_cut_boundary}|{relative_cut_boundary + 1}",
        "strand": strand,
        "spacer_start": spacer_start,
        "spacer_end": spacer_end_val,
        "chrom": chrom if return_genomic_coord else None,
        "spacer_length": spacer_length,
        "pam_position": pam_position,
        "cut_offset_from_pam": cut_offset_from_pam,
        "coordinate_system": "0-based half-open (genomic), 1-based biological (relative)",
        "relative_coordinate_semantics": (
            f"Boundary between spacer positions {relative_cut_boundary} and "
            f"{relative_cut_boundary + 1} (1-based, 5'→3' across protospacer)"
        ),
        "nuclease": "SpCas9",
        "offset_source": "custom" if is_custom_offset else "canonical",
    }

    return ToolResult(
        tool="compute_cut_site",
        rows=rows,
        summary=summary,
        errors=errors,
        warnings=warnings,
        metadata={
            "nuclease": "SpCas9",
            "pam_type": "3prime",
            "pam_length": pam_length,
            "coordinate_system": "0-based half-open (genomic), 1-based biological (relative)",
            "note": (
                "Predicted canonical SpCas9 cleavage anchor. "
                "NOT a cleavage-efficiency predictor."
            ),
        },
    )


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VEYRA compute_cut_site tool")
    parser.add_argument("--spacer-start", type=int, required=True, help="0-based spacer start coordinate")
    parser.add_argument("--spacer-length", type=int, default=20, help="Spacer length (default: 20)")
    parser.add_argument("--strand", default="+", choices=["+", "-"], help="Strand (default: +)")
    parser.add_argument("--pam-position", default="3prime", help="PAM position (default: 3prime)")
    parser.add_argument("--cut-offset-from-pam", type=int, default=-3, help="Cut offset from PAM (default: -3)")
    parser.add_argument("--return-genomic-coord", action="store_true", default=True, help="Return genomic coordinate")
    parser.add_argument("--no-genomic-coord", dest="return_genomic_coord", action="store_false", help="Omit genomic coordinate")
    parser.add_argument("--return-relative-coord", action="store_true", default=True, help="Return relative coordinate")
    parser.add_argument("--no-relative-coord", dest="return_relative_coord", action="store_false", help="Omit relative coordinate")
    parser.add_argument("--chrom", default="", help="Chromosome (required for genomic coordinate)")
    parser.add_argument("--tsv", action="store_true", help="Output as TSV")
    args = parser.parse_args()

    result = compute_cut_site(
        spacer_start=args.spacer_start,
        spacer_length=args.spacer_length,
        strand=args.strand,
        pam_position=args.pam_position,
        cut_offset_from_pam=args.cut_offset_from_pam,
        return_genomic_coord=args.return_genomic_coord,
        return_relative_coord=args.return_relative_coord,
        chrom=args.chrom,
    )
    if args.tsv:
        print(result.to_tsv())
    else:
        import json
        print(json.dumps({"tool": result.tool, "summary": result.summary, "errors": result.errors, "warnings": result.warnings}, indent=2))
