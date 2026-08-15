"""MCP Tool: predict_ontarget_efficiency

Predict on-target SpCas9 efficiency using Rule Set models.

This is fundamentally different from CFD/off-target specificity.
It answers: "How efficiently is this intended guide expected to cut?"

    Available models:
- rule_set_3: Doench 2021 (LightGBM via rs3)
- rule_set_2: Doench 2016 / Fusi / Azimuth (AdaBoost)
- doench_2014: Doench 2014 linear regression (pure Python)
- auto: Select highest-priority verified model (with auto-provisioning)

Tier 1 — CHEAP / DETERMINISTIC
Cost: cheap / deterministic
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.schemas import ToolResult, validate_dna_sequence
from core.ontarget import predict_ontarget_efficiency
from schemas.canonical import ComputeOnTargetEfficiencyRequest


def predict_ontarget_efficiency_tool(
    context_sequence: str,
    model: str = "auto",
    context_upstream: int = 4,
    context_downstream: int = 3,
    spacer_length: int = 20,
    normalize_score: bool = False,
    round_decimals: int = 3,
) -> ToolResult:
    """Predict on-target SpCas9 efficiency.

    This is fundamentally different from CFD/off-target specificity.
    It answers: "How efficiently is this intended guide expected to cut?"

    Available models:
    - auto: Select highest-priority verified model (with auto-provisioning)
    - rule_set_3: Doench 2021 (LightGBM via rs3)
    - rule_set_2: Doench 2016 / Fusi / Azimuth (AdaBoost)
    - doench_2014: Doench 2014 linear regression (pure Python)

    Args:
        context_sequence: Full context sequence (upstream + spacer + PAM + downstream).
        model: "auto", "rule_set_2", "rule_set_3", "doench_2014", or "both".
        context_upstream: Number of nucleotides upstream of spacer.
        context_downstream: Number of nucleotides downstream of PAM.
        spacer_length: Length of the spacer/protospacer.
        normalize_score: Whether to normalize score to [0,1].
        round_decimals: Decimal places for rounding output values.

    Returns:
        ToolResult with on-target efficiency scores.
    """
    # Validate context sequence
    try:
        validate_dna_sequence(context_sequence)
    except ValueError as e:
        return ToolResult(
            tool="predict_ontarget_efficiency",
            errors=[f"Invalid context_sequence: {e}"],
        )

    request = ComputeOnTargetEfficiencyRequest(
        context_sequence=context_sequence,
        model=model,
        context_upstream=context_upstream,
        context_downstream=context_downstream,
        spacer_length=spacer_length,
        normalize_score=normalize_score,
        round_decimals=round_decimals,
    )
    result = predict_ontarget_efficiency(request)

    return ToolResult(
        tool="predict_ontarget_efficiency",
        rows=[],
        summary=result.summary,
        errors=result.errors,
        warnings=result.warnings,
        metadata=result.metadata,
    )


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VEYRA predict_ontarget_efficiency tool")
    parser.add_argument("--context-sequence", "-s", required=True, help="Context sequence")
    parser.add_argument("--model", default="auto", choices=["auto", "rule_set_2", "rule_set_3", "doench_2014", "both"])
    parser.add_argument("--context-upstream", type=int, default=4, help="Upstream context length")
    parser.add_argument("--context-downstream", type=int, default=3, help="Downstream context length")
    parser.add_argument("--spacer-length", type=int, default=20, help="Spacer length")
    parser.add_argument("--normalize-score", action="store_true", help="Normalize score to [0,1]")
    parser.add_argument("--round-decimals", type=int, default=3, help="Decimal places for rounding")
    parser.add_argument("--tsv", action="store_true")
    args = parser.parse_args()

    result = predict_ontarget_efficiency_tool(
        context_sequence=args.context_sequence,
        model=args.model,
        context_upstream=args.context_upstream,
        context_downstream=args.context_downstream,
        spacer_length=args.spacer_length,
        normalize_score=args.normalize_score,
        round_decimals=args.round_decimals,
    )
    if args.tsv:
        print(result.to_tsv())
    else:
        print(result.to_json(indent=2))