"""VEYRA MCP Server

Provides a registry of all MCP tools and exposes them via
a local CLI interface for development and debugging.

Launch with: python -m mcp.server
"""

from __future__ import annotations

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.tools.pam_scan import pam_scan
from mcp.tools.pam_scan_region import pam_scan_region
from mcp.tools.build_offtarget_index import build_offtarget_index
from mcp.tools.offtarget_search import offtarget_search
from mcp.tools.score_offtargets import score_offtargets
from mcp.tools.rank_candidates import rank_candidates
from mcp.tools.compute_gc_content import compute_gc_content
from mcp.tools.check_homopolymer_runs import check_homopolymer_runs
from mcp.tools.compute_melting_temp import compute_melting_temp
from mcp.tools.compute_secondary_structure import compute_secondary_structure
from mcp.tools.compute_positional_features import compute_positional_features
from mcp.tools.compute_dinucleotide_composition import compute_dinucleotide_composition
from mcp.tools.compute_seed_gc import compute_seed_gc
from mcp.tools.cas_offinder_search import cas_offinder_search
from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed
from mcp.tools.compute_cut_site import compute_cut_site
from mcp.tools.predict_ontarget_efficiency import predict_ontarget_efficiency_tool
from mcp.schemas import PAMSiteRow

# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, dict] = {
    "pam_scan": {
        "function": pam_scan,
        "description": "Fast PAM/protospacer discovery within an input sequence (regex/IUPAC)",
        "cost": "cheap / deterministic",
        "tier": 1,
    },
    "pam_scan_region": {
        "function": pam_scan_region,
        "description": "PAM scanning against a genomic region via indexed FASTA access",
        "cost": "cheap / reference lookup",
        "tier": 1,
    },
    "build_offtarget_index": {
        "function": build_offtarget_index,
        "description": "Build or register a reusable genome-search index (BWA). EXPENSIVE.",
        "cost": "expensive / setup / cacheable",
        "tier": 2,
    },
    "offtarget_search": {
        "function": offtarget_search,
        "description": "Search genome for approximate matches to a guide/spacer (BWA aln)",
        "cost": "expensive / genome-scale",
        "tier": 2,
    },
    "score_offtargets": {
        "function": score_offtargets,
        "description": "Calculate CFD-style specificity scores for off-target candidates",
        "cost": "moderate",
        "tier": 2,
    },
    "rank_candidates": {
        "function": rank_candidates,
        "description": "Aggregate off-target evidence and rank candidate guides",
        "cost": "moderate",
        "tier": 2,
    },
    "compute_gc_content": {
        "function": compute_gc_content,
        "description": "Compute GC content and optional sliding-window / 5'-3' split features for a DNA sequence",
        "cost": "cheap / deterministic",
        "tier": 1,
    },
    "check_homopolymer_runs": {
        "function": check_homopolymer_runs,
        "description": "Detect homopolymer runs (poly-T, poly-G, etc.) in a DNA sequence for SpCas9 guide filtering",
        "cost": "cheap / deterministic",
        "tier": 1,
    },
    "compute_melting_temp": {
        "function": compute_melting_temp,
        "description": "Compute estimated duplex melting temperature using nearest-neighbor, Wallace, or GC-percent methods",
        "cost": "moderate / deterministic",
        "tier": 1,
    },
    "compute_secondary_structure": {
        "function": compute_secondary_structure,
        "description": "Compute minimum free energy (MFE) and optional dot-bracket structure for a DNA sequence (requires ViennaRNA)",
        "cost": "moderate / deterministic / optional dependency",
        "tier": 1,
    },
    "compute_positional_features": {
        "function": compute_positional_features,
        "description": "Deterministic positional nucleotide-feature extractor for SpCas9 spacer sequences (1-based biological positions, one-hot encoding, position-20 bias)",
        "cost": "cheap / deterministic",
        "tier": 1,
    },
    "compute_dinucleotide_composition": {
        "function": compute_dinucleotide_composition,
        "description": "Deterministic dinucleotide/k-mer composition feature extractor for SpCas9 spacer sequences (position-anchored, configurable window size, target filtering)",
        "cost": "cheap / deterministic",
        "tier": 1,
    },
    "compute_seed_gc": {
        "function": compute_seed_gc,
        "description": "Deterministic PAM-proximal seed GC-content feature extractor for SpCas9 guide candidates (configurable seed length, thresholds, optional distal delta)",
        "cost": "cheap / deterministic",
        "tier": 1,
    },
    "cas_offinder_search": {
        "function": cas_offinder_search,
        "description": "Genome-wide off-target search with DNA/RNA bulge support using Cas-OFFinder 3.0.0 (CPU via POCL)",
        "cost": "expensive / genome-scale / bulge-aware",
        "tier": 2,
    },
    "analyze_mismatch_seed": {
        "function": analyze_mismatch_seed,
        "description": "Alignment-aware seed region mismatch/bulge analysis for off-target candidates",
        "cost": "cheap / deterministic",
        "tier": 1,
    },
    "compute_cut_site": {
        "function": compute_cut_site,
        "description": "Deterministic canonical SpCas9 cleavage-site position anchor (coordinate-only, strand-aware, not a cleavage-efficiency predictor)",
        "cost": "cheap / deterministic",
        "tier": 1,
    },
    "predict_ontarget_efficiency": {
        "function": predict_ontarget_efficiency_tool,
        "description": "Predict on-target SpCas9 efficiency (Rule Set 2 / Rule Set 3). Distinguishes from off-target specificity (CFD).",
        "cost": "cheap / deterministic",
        "tier": 1,
    },
}


def list_tools() -> None:
    """Print available tools."""
    print("=" * 70)
    print("VEYRA MCP Tools")
    print("=" * 70)
    for name, info in TOOL_REGISTRY.items():
        print(f"\n  {name}")
        print(f"    Cost: {info['cost']}")
        print(f"    Tier: {info['tier']}")
        print(f"    {info['description']}")
    print()


def invoke_tool(tool_name: str, args: dict) -> None:
    """Invoke a tool and print the result."""
    if tool_name not in TOOL_REGISTRY:
        print(json.dumps({"error": f"Unknown tool: {tool_name}"}))
        sys.exit(1)

    func = TOOL_REGISTRY[tool_name]["function"]
    try:
        result = func(**args)
        print(result.to_json(indent=2))
    except TypeError as e:
        print(json.dumps({"error": f"Invalid arguments: {e}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Tool execution failed: {e}"}))
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="veyra-mcp",
        description="VEYRA MCP Server — genomic/CRISPR analysis tools",
    )
    sub = parser.add_subparsers(dest="command")

    # list
    sub.add_parser("list", help="List available tools")

    # invoke <tool> --args-json '{...}'
    invoke_p = sub.add_parser("invoke", help="Invoke a tool")
    invoke_p.add_argument("tool", help="Tool name")
    invoke_p.add_argument("--args-json", required=True, help="JSON arguments for the tool")
    invoke_p.add_argument("--tsv", action="store_true", help="Output as TSV")

    # Quick shortcuts
    pam_p = sub.add_parser("pam-scan", help="Quick PAM scan")
    pam_p.add_argument("--sequence", "-s", required=True)
    pam_p.add_argument("--pam", default="NGG")
    pam_p.add_argument("--spacer-len", type=int, default=20)
    pam_p.add_argument("--strand", default="both", choices=["both", "fwd", "rev"])

    pam_region_p = sub.add_parser("pam-scan-region", help="PAM scan a genomic region")
    pam_region_p.add_argument("--genome", required=True)
    pam_region_p.add_argument("--chrom", required=True)
    pam_region_p.add_argument("--start", type=int, required=True)
    pam_region_p.add_argument("--end", type=int, required=True)
    pam_region_p.add_argument("--pam", default="NGG")

    build_p = sub.add_parser("build-index", help="Build off-target index")
    build_p.add_argument("--genome", required=True)
    build_p.add_argument("--cas", default="SpCas9")
    build_p.add_argument("--force", action="store_true")

    ot_p = sub.add_parser("offtarget-search", help="Off-target search")
    ot_p.add_argument("--spacer", "-s", required=True)
    ot_p.add_argument("--genome", required=True)
    ot_p.add_argument("--pam", default="NGG")
    ot_p.add_argument("--max-mismatches", type=int, default=4)

    args = parser.parse_args()

    if args.command == "list":
        list_tools()
    elif args.command == "invoke":
        tool_args = json.loads(args.args_json)
        invoke_tool(args.tool, tool_args)
    elif args.command == "pam-scan":
        result = pam_scan(args.sequence, args.pam, args.spacer_len, args.strand)
        print(result.to_json(indent=2))
    elif args.command == "pam-scan-region":
        result = pam_scan_region(args.genome, args.chrom, args.start, args.end, args.pam)
        print(result.to_json(indent=2))
    elif args.command == "build-index":
        result = build_offtarget_index(args.genome, args.cas, args.force)
        print(result.to_json(indent=2))
    elif args.command == "offtarget-search":
        result = offtarget_search(args.spacer, args.genome, args.pam, args.max_mismatches)
        print(result.to_json(indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
