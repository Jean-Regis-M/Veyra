"""MCP Tool: compute_secondary_structure

Deterministic secondary-structure / MFE estimator for DNA sequences.

Tier: moderate / deterministic

Requires ViennaRNA Python bindings (optional dependency).  When unavailable,
the tool returns a structured dependency error rather than fabricated values.

MFE describes predicted thermodynamic stability under the selected model;
it is NOT a validated prediction of Cas9 cleavage, guide efficacy, or
RNP assembly success.
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import PAMSiteRow, ToolResult, validate_dna_sequence

# --- Optional ViennaRNA import ---
_RNA_AVAILABLE = False
_RNA_VERSION: str | None = None
try:
    import RNA as _viennarna
    _RNA_AVAILABLE = True
    _RNA_VERSION = getattr(_viennarna, "__version__", "unknown")
except ImportError:
    _viennarna = None  # type: ignore[assignment]


def _fold_rna(seq: str, temperature: float) -> tuple[str, float]:
    """Fold an RNA sequence using ViennaRNA and return (structure, mfe).

    The sequence is converted from DNA (T→U) before folding because
    ViennaRNA operates on RNA.  The thermodynamic parameters for DNA/RNA
    hybrids differ; ViennaRNA's default parameters are for RNA folding.
    This is documented as a limitation.
    """
    rna_seq = seq.replace("T", "U").replace("t", "u")
    fc = _viennarna.fold_compound(rna_seq)
    structure, mfe = fc.mfe()
    return structure, mfe


def compute_secondary_structure(
    sequence: str,
    mfe_include_scaffold: bool = False,
    scaffold_sequence: str = "",
    temperature_celsius: float = 37.0,
    return_structure_string: bool = False,
    mfe_threshold: float = -5.0,
) -> ToolResult:
    """Compute secondary structure / MFE for a DNA sequence.

    Args:
        sequence: DNA sequence (standard ACGT).
        mfe_include_scaffold: If True, fold sequence + scaffold together.
        scaffold_sequence: Scaffold RNA sequence (required when mfe_include_scaffold=True).
        temperature_celsius: Folding temperature in °C (default 37.0).
        return_structure_string: If True, include dot-bracket structure.
        mfe_threshold: MFE threshold for pass/fail filter (default -5.0 kcal/mol).

    Returns:
        ToolResult with MFE and optional structure in summary.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- Dependency check ---
    if not _RNA_AVAILABLE:
        return ToolResult(
            tool="compute_secondary_structure",
            errors=[
                "ViennaRNA Python bindings not installed. "
                "Secondary-structure computation is unavailable. "
                "Install with: pip install ViennaRNA (into the project venv)."
            ],
            metadata={
                "folding_engine": "ViennaRNA",
                "folding_engine_version": None,
                "dependency_available": False,
                "scoring_note": (
                    "MFE describes predicted thermodynamic stability; "
                    "it is NOT a validated prediction of Cas9 cleavage."
                ),
            },
        )

    # --- Validate sequence ---
    try:
        seq = validate_dna_sequence(sequence, allow_iupac=False)
    except ValueError as e:
        return ToolResult(tool="compute_secondary_structure", errors=[str(e)])

    seq_len = len(seq)

    # --- Validate parameters ---
    if not isinstance(temperature_celsius, (int, float)):
        errors.append(f"temperature_celsius must be a number, got {temperature_celsius}")
    elif math.isnan(temperature_celsius) or math.isinf(temperature_celsius):
        errors.append("temperature_celsius must not be NaN or infinite")
    elif not (0.0 <= temperature_celsius <= 100.0):
        # ViennaRNA supports 0–100°C
        errors.append(
            f"temperature_celsius must be in [0, 100], got {temperature_celsius}"
        )

    if not isinstance(mfe_threshold, (int, float)):
        errors.append(f"mfe_threshold must be a number, got {mfe_threshold}")
    elif math.isnan(mfe_threshold) or math.isinf(mfe_threshold):
        errors.append("mfe_threshold must not be NaN or infinite")

    if mfe_include_scaffold and not scaffold_sequence:
        errors.append(
            "scaffold_sequence is required when mfe_include_scaffold=true"
        )

    if errors:
        return ToolResult(tool="compute_secondary_structure", errors=errors)

    # --- Build folding sequence ---
    scaffold_len = 0
    if mfe_include_scaffold:
        scaffold_len = len(scaffold_sequence)
        fold_seq = seq + scaffold_sequence
    else:
        fold_seq = seq

    # --- Set temperature ---
    _viennarna.init_rand(0)  # Deterministic seed
    _viennarna.cvar.temperature = int(temperature_celsius)

    # --- Fold ---
    try:
        structure, mfe = _fold_rna(fold_seq, temperature_celsius)
    except Exception as e:
        return ToolResult(
            tool="compute_secondary_structure",
            errors=[f"Folding failed: {e}"],
        )

    # --- MFE threshold ---
    passes_mfe_filter = mfe <= mfe_threshold

    # --- Structure string ---
    structure_out = structure if return_structure_string else None

    # --- Build result ---
    row = PAMSiteRow(
        protospacer=seq[:20] if seq_len >= 20 else seq,
    )

    summary = {
        "sequence_length": seq_len,
        "mfe_kcal_mol": mfe,
        "passes_mfe_filter": passes_mfe_filter,
        "structure_string": structure_out,
    }

    metadata = {
        "folded_length": len(fold_seq),
        "mfe_include_scaffold": mfe_include_scaffold,
        "temperature_celsius": temperature_celsius,
        "scaffold_length": scaffold_len if mfe_include_scaffold else None,
        "mfe_threshold": mfe_threshold,
        "folding_engine": "ViennaRNA",
        "folding_engine_version": _RNA_VERSION,
        "dependency_available": True,
        "scoring_note": (
            "MFE describes predicted thermodynamic stability; "
            "it is NOT a validated prediction of Cas9 cleavage. "
            "DNA sequences are converted to RNA (T→U) for folding; "
            "thermodynamic parameters are for RNA, not DNA."
        ),
    }

    return ToolResult(
        tool="compute_secondary_structure",
        rows=[row],
        summary=summary,
        errors=errors,
        warnings=warnings,
        metadata=metadata,
    )


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VEYRA compute_secondary_structure tool")
    parser.add_argument("--sequence", "-s", required=True, help="DNA sequence")
    parser.add_argument("--mfe-include-scaffold", action="store_true",
                        help="Fold sequence + scaffold together")
    parser.add_argument("--scaffold-sequence", default="", help="Scaffold RNA sequence")
    parser.add_argument("--temperature-celsius", type=float, default=37.0,
                        help="Folding temperature (°C)")
    parser.add_argument("--return-structure-string", action="store_true",
                        help="Include dot-bracket structure")
    parser.add_argument("--mfe-threshold", type=float, default=-5.0,
                        help="MFE threshold (kcal/mol)")
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    result = compute_secondary_structure(
        sequence=args.sequence,
        mfe_include_scaffold=args.mfe_include_scaffold,
        scaffold_sequence=args.scaffold_sequence,
        temperature_celsius=args.temperature_celsius,
        return_structure_string=args.return_structure_string,
        mfe_threshold=args.mfe_threshold,
    )
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))
