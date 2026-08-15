"""MCP Tool: compute_melting_temp

Deterministic melting-temperature estimator for DNA sequences.

Tier: moderate / deterministic

Uses Biopython's MeltingTemp module for established nearest-neighbor,
Wallace, and GC-percent methods.  Tm is an estimated physicochemical
property; it is NOT itself a validated prediction of Cas9 cleavage
efficiency or specificity.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import PAMSiteRow, ToolResult, validate_dna_sequence

# Biopython MeltingTemp — established implementations
from Bio.SeqUtils.MeltingTemp import Tm_NN, Tm_Wallace, Tm_GC
from Bio.Seq import Seq

_VALID_METHODS = frozenset({"nearest_neighbor", "wallace", "gc_percent"})


def compute_melting_temp(
    sequence: str,
    tm_method: str = "nearest_neighbor",
    na_conc: float = 50.0,
    mg_conc: float = 0.0,
    primer_conc: float = 250.0,
    seed_region_length: int = 10,
    compute_seed_tm: bool = False,
    round_decimals: int = 2,
) -> ToolResult:
    """Compute estimated melting temperature for a DNA sequence.

    Uses Biopython's MeltingTemp module for all calculations.

    Args:
        sequence: DNA sequence (standard ACGT).
        tm_method: "nearest_neighbor", "wallace", or "gc_percent".
        na_conc: Na+ concentration in mM (default 50).
        mg_conc: Mg2+ concentration in mM (default 0).
        primer_conc: Primer concentration in nM (default 250).
        seed_region_length: Length of seed region for seed Tm (default 10).
        compute_seed_tm: Whether to compute Tm for the 3' seed region.
        round_decimals: Decimal places for rounding (default 2).

    Returns:
        ToolResult with melting temperature in summary.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- Validate sequence ---
    try:
        seq = validate_dna_sequence(sequence, allow_iupac=False)
    except ValueError as e:
        return ToolResult(tool="compute_melting_temp", errors=[str(e)])

    seq_len = len(seq)

    # --- Validate parameters ---
    if tm_method not in _VALID_METHODS:
        errors.append(f"tm_method must be one of {sorted(_VALID_METHODS)}, got '{tm_method}'")
    if not isinstance(na_conc, (int, float)) or na_conc < 0:
        errors.append(f"na_conc must be a non-negative number, got {na_conc}")
    if not isinstance(mg_conc, (int, float)) or mg_conc < 0:
        errors.append(f"mg_conc must be a non-negative number, got {mg_conc}")
    if not isinstance(primer_conc, (int, float)) or primer_conc <= 0:
        errors.append(f"primer_conc must be a positive number, got {primer_conc}")
    if not isinstance(round_decimals, int) or round_decimals < 0:
        errors.append(f"round_decimals must be a non-negative integer, got {round_decimals}")

    if compute_seed_tm:
        if not isinstance(seed_region_length, int) or seed_region_length <= 0:
            errors.append(f"seed_region_length must be a positive integer, got {seed_region_length}")
        elif seed_region_length > seq_len:
            errors.append(
                f"seed_region_length ({seed_region_length}) exceeds sequence length ({seq_len})"
            )

    if errors:
        return ToolResult(tool="compute_melting_temp", errors=errors)

    # --- Compute Tm ---
    bio_seq = Seq(seq)

    if tm_method == "nearest_neighbor":
        # Tm_NN uses: Na, Mg, dNTPs, dnac1 (primer conc), saltcorr=5 (SantaLucia 1998)
        # K, Tris set to 0; dNTPs set to 0 (not provided by caller)
        tm_celsius = Tm_NN(
            bio_seq,
            Na=na_conc,
            Mg=mg_conc,
            dnac1=primer_conc / 2.0,  # Tm_NN expects concentration per strand
            dnac2=primer_conc / 2.0,
            saltcorr=5,
        )
    elif tm_method == "wallace":
        # Wallace rule: Tm = 2*(A+T) + 4*(G+C), no salt/conc dependence
        if na_conc != 50.0 or mg_conc != 0.0 or primer_conc != 250.0:
            warnings.append(
                "Wallace method does not use na_conc, mg_conc, or primer_conc; "
                "these parameters were ignored."
            )
        tm_celsius = Tm_Wallace(bio_seq)
    elif tm_method == "gc_percent":
        # Tm_GC: salt-dependent GC-based approximation
        tm_celsius = Tm_GC(
            bio_seq,
            Na=na_conc,
            Mg=mg_conc,
            saltcorr=0,
        )

    tm_celsius = round(tm_celsius, round_decimals)

    # --- Seed Tm ---
    seed_tm_celsius = None
    if compute_seed_tm:
        # 3' end of the provided sequence (seed region for SpCas9)
        seed_seq = bio_seq[-seed_region_length:]
        if tm_method == "nearest_neighbor":
            seed_tm_celsius = round(
                Tm_NN(
                    seed_seq,
                    Na=na_conc,
                    Mg=mg_conc,
                    dnac1=primer_conc / 2.0,
                    dnac2=primer_conc / 2.0,
                    saltcorr=5,
                ),
                round_decimals,
            )
        elif tm_method == "wallace":
            seed_tm_celsius = round(Tm_Wallace(seed_seq), round_decimals)
        elif tm_method == "gc_percent":
            seed_tm_celsius = round(
                Tm_GC(seed_seq, Na=na_conc, Mg=mg_conc, saltcorr=0),
                round_decimals,
            )

    # --- Build result ---
    row = PAMSiteRow(
        protospacer=seq[:20] if seq_len >= 20 else seq,
    )

    summary = {
        "sequence_length": seq_len,
        "tm_celsius": tm_celsius,
        "seed_tm_celsius": seed_tm_celsius,
    }

    metadata = {
        "tm_method": tm_method,
        "na_conc": na_conc,
        "mg_conc": mg_conc,
        "primer_conc": primer_conc,
        "seed_region_length": seed_region_length if compute_seed_tm else None,
        "compute_seed_tm": compute_seed_tm,
        "round_decimals": round_decimals,
        "scoring_note": (
            "Melting temperature is an estimated physicochemical property; "
            "it is NOT a validated prediction of Cas9 cleavage."
        ),
    }

    return ToolResult(
        tool="compute_melting_temp",
        rows=[row],
        summary=summary,
        errors=errors,
        warnings=warnings,
        metadata=metadata,
    )


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VEYRA compute_melting_temp tool")
    parser.add_argument("--sequence", "-s", required=True, help="DNA sequence")
    parser.add_argument("--tm-method", default="nearest_neighbor",
                        choices=["nearest_neighbor", "wallace", "gc_percent"])
    parser.add_argument("--na-conc", type=float, default=50.0, help="Na+ concentration (mM)")
    parser.add_argument("--mg-conc", type=float, default=0.0, help="Mg2+ concentration (mM)")
    parser.add_argument("--primer-conc", type=float, default=250.0, help="Primer concentration (nM)")
    parser.add_argument("--seed-region-length", type=int, default=10, help="Seed region length")
    parser.add_argument("--compute-seed-tm", action="store_true", help="Compute seed region Tm")
    parser.add_argument("--round-decimals", type=int, default=2, help="Decimal places")
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    result = compute_melting_temp(
        sequence=args.sequence,
        tm_method=args.tm_method,
        na_conc=args.na_conc,
        mg_conc=args.mg_conc,
        primer_conc=args.primer_conc,
        seed_region_length=args.seed_region_length,
        compute_seed_tm=args.compute_seed_tm,
        round_decimals=args.round_decimals,
    )
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
