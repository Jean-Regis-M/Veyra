#!/usr/bin/env python3
"""VEYRA Unified CLI.

Provides access to all VEYRA functionality through a single command-line interface.

Usage:
    python -m veyra --help
    python -m veyra ingest --input file.fasta
    python -m veyra pam scan --sequence ATCG...
    python -m veyra pam scan-region --genome-id GRCh38.p14 --chrom chr1 --start 1 --end 1000
    python -m veyra index build --genome-id GRCh38.p14
    python -m veyra offtarget search --spacer ACTG... --genome-id GRCh38.p14
    python -m veyra offtarget score --spacer ACTG... --candidates-json candidates.json
    python -m veyra rank --guides-json guides.json
    python -m veyra genome list
    python -m veyra genome info --genome-id GRCh38.p14
    python -m veyra cache status
    python -m veyra tools list
    python -m veyra tools describe pam_scan
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import VeyraResult


def _output_result(result: VeyraResult, args) -> int:
    """Output a result based on format flags."""
    if result.errors:
        for e in result.errors:
            print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.output_format == "json":
        output = result.to_json(indent=2)
    elif args.output_format == "tsv":
        output = result.to_tsv()
    else:
        output = result.to_text()

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Output written to: {args.output}", file=sys.stderr)
    else:
        print(output)

    return 0


def _add_output_args(parser):
    """Add common output arguments to a subparser."""
    parser.add_argument(
        "--output-format", "-f",
        choices=["json", "tsv", "text"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (default: stdout)",
    )


def _cmd_ingest(args):
    """Handle ingest command."""
    from core.ingestion import ingest
    from schemas.canonical import IngestRequest

    request = IngestRequest(
        input_path=args.input,
        pam_scan=args.pam,
        pam_names=args.pam_types,
    )
    result = ingest(request)
    return _output_result(result, args)


def _cmd_pam_scan(args):
    """Handle pam scan command."""
    from core.pam import pam_scan
    from schemas.canonical import PamScanRequest

    # Read sequence from file or stdin
    if args.input == "-":
        sequence = sys.stdin.read().strip()
    elif args.input and os.path.isfile(args.input):
        with open(args.input) as f:
            sequence = f.read().strip()
    else:
        sequence = args.sequence

    if not sequence:
        print("Error: no sequence provided", file=sys.stderr)
        return 1

    request = PamScanRequest(
        sequence=sequence,
        pam_pattern=args.pam_pattern,
        protospacer_len=args.protospacer_len,
        strand=args.strand,
        chrom=args.chrom,
    )
    result = pam_scan(request)
    return _output_result(result, args)


def _cmd_pam_scan_region(args):
    """Handle pam scan-region command."""
    from core.pam import pam_scan_region
    from schemas.canonical import PamScanRegionRequest

    request = PamScanRegionRequest(
        genome_id=args.genome_id,
        chrom=args.chrom,
        start=args.start,
        end=args.end,
        pam_pattern=args.pam_pattern,
        protospacer_len=args.protospacer_len,
        strand=args.strand,
    )
    result = pam_scan_region(request)
    return _output_result(result, args)


def _cmd_index_build(args):
    """Handle index build command."""
    from core.offtarget import build_index
    from schemas.canonical import BuildIndexRequest

    request = BuildIndexRequest(
        genome_id=args.genome_id,
        cas_variant=args.cas_variant,
        force_rebuild=args.force,
    )
    result = build_index(request)
    return _output_result(result, args)


def _cmd_offtarget_search(args):
    """Handle offtarget search command."""
    from core.offtarget import offtarget_search
    from schemas.canonical import OfftargetSearchRequest

    request = OfftargetSearchRequest(
        spacer_sequence=args.spacer,
        genome_id=args.genome_id,
        pam_pattern=args.pam_pattern,
        max_mismatches=args.max_mismatches,
        allow_bulge=args.allow_bulge,
        cas_variant=args.cas_variant,
    )
    result = offtarget_search(request)
    return _output_result(result, args)


def _cmd_offtarget_score(args):
    """Handle offtarget score command."""
    from core.offtarget import score_offtargets
    from schemas.canonical import ScoreOfftargetsRequest

    # Load candidates from file or stdin
    if args.candidates_json == "-":
        candidates = json.load(sys.stdin)
    elif os.path.isfile(args.candidates_json):
        with open(args.candidates_json) as f:
            candidates = json.load(f)
    else:
        print(f"Error: candidates file not found: {args.candidates_json}", file=sys.stderr)
        return 1

    request = ScoreOfftargetsRequest(
        spacer_sequence=args.spacer,
        candidates=candidates,
        pam_pattern=args.pam_pattern,
    )
    result = score_offtargets(request)
    return _output_result(result, args)


def _cmd_rank(args):
    """Handle rank command."""
    from core.ranking import rank_candidates
    from schemas.canonical import RankCandidatesRequest

    # Load guides from file or stdin
    if args.guides_json == "-":
        guides = json.load(sys.stdin)
    elif os.path.isfile(args.guides_json):
        with open(args.guides_json) as f:
            guides = json.load(f)
    else:
        print(f"Error: guides file not found: {args.guides_json}", file=sys.stderr)
        return 1

    off_targets = None
    if args.offtargets_json:
        if os.path.isfile(args.offtargets_json):
            with open(args.offtargets_json) as f:
                off_targets = json.load(f)

    on_target_scores = None
    if args.on_target_json:
        if os.path.isfile(args.on_target_json):
            with open(args.on_target_json) as f:
                on_target_scores = json.load(f)

    request = RankCandidatesRequest(
        guides=guides,
        off_targets=off_targets,
        on_target_scores=on_target_scores,
        sort_by=args.sort_by,
    )
    result = rank_candidates(request)
    return _output_result(result, args)


def _cmd_genome_list(args):
    """Handle genome list command."""
    from core.genome import list_genomes

    result = list_genomes()
    return _output_result(result, args)


def _cmd_genome_info(args):
    """Handle genome info command."""
    from core.genome import genome_info

    result = genome_info(args.genome_id)
    return _output_result(result, args)


def _cmd_cache_status(args):
    """Handle cache status command."""
    from core.cache import cache_status

    result = cache_status(tool_name=args.tool_name)
    return _output_result(result, args)


def _cmd_cache_clear(args):
    """Handle cache clear command."""
    from core.cache import cache_clear

    if not args.confirm:
        print("Warning: This will clear cache entries.", file=sys.stderr)
        print("Use --confirm to proceed.", file=sys.stderr)
        return 1

    result = cache_clear(tool_name=args.tool_name)
    return _output_result(result, args)


def _cmd_tools_list(args):
    """Handle tools list command."""
    from mcp.server import TOOL_REGISTRY

    tools = []
    for name, info in TOOL_REGISTRY.items():
        tools.append({
            "name": name,
            "tier": info.get("tier"),
            "cost": info.get("cost"),
        })

    result = VeyraResult(
        tool="tools_list",
        summary={"total_tools": len(tools), "tools": tools},
    )
    return _output_result(result, args)


def _cmd_tools_describe(args):
    """Handle tools describe command."""
    from mcp.server import TOOL_REGISTRY

    tool_name = args.tool_name
    if tool_name not in TOOL_REGISTRY:
        print(f"Error: unknown tool: {tool_name}", file=sys.stderr)
        print(f"Available tools: {', '.join(TOOL_REGISTRY.keys())}", file=sys.stderr)
        return 1

    info = TOOL_REGISTRY[tool_name]
    result = VeyraResult(
        tool="tools_describe",
        summary={
            "name": tool_name,
            "tier": info.get("tier"),
            "cost": info.get("cost"),
        },
    )
    return _output_result(result, args)


def _cmd_sequence_gc(args):
    """Handle sequence gc command."""
    from core.gc import compute_gc_content
    from schemas.canonical import ComputeGCContentRequest

    # Read sequence from file, stdin, or argument
    if args.input == "-":
        sequence = sys.stdin.read().strip()
    elif args.input and os.path.isfile(args.input):
        with open(args.input) as f:
            sequence = f.read().strip()
    else:
        sequence = args.sequence

    if not sequence:
        print("Error: no sequence provided", file=sys.stderr)
        return 1

    request = ComputeGCContentRequest(
        sequence=sequence,
        gc_window_size=args.gc_window_size,
        gc_split_ratio=args.gc_split_ratio,
        gc_min_threshold=args.gc_min_threshold,
        gc_max_threshold=args.gc_max_threshold,
        include_sliding_window=not args.no_sliding_window,
        include_half_split=not args.no_half_split,
        round_decimals=args.round_decimals,
    )
    result = compute_gc_content(request)
    return _output_result(result, args)


def _build_parser():
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="veyra",
        description="VEYRA – Genomic Intelligence Backend",
        epilog="Use 'veyra <command> --help' for help on a specific command.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- ingest ---
    ingest_parser = subparsers.add_parser("ingest", help="Ingest genomic files")
    ingest_parser.add_argument("--input", "-i", required=True, help="Input file path")
    ingest_parser.add_argument("--pam", action="store_true", help="Enable PAM scanning")
    ingest_parser.add_argument("--pam-types", nargs="+", default=None, help="PAM types to scan")
    _add_output_args(ingest_parser)
    ingest_parser.set_defaults(func=_cmd_ingest)

    # --- pam ---
    pam_parser = subparsers.add_parser("pam", help="PAM scanning commands")
    pam_sub = pam_parser.add_subparsers(dest="pam_command", help="PAM commands")

    # pam scan
    pam_scan_parser = pam_sub.add_parser("scan", help="Scan sequence for PAM sites")
    pam_scan_parser.add_argument("--sequence", "-s", help="DNA sequence")
    pam_scan_parser.add_argument("--input", "-i", help="Input file (FASTA) or - for stdin")
    pam_scan_parser.add_argument("--pam-pattern", default="NGG", help="PAM pattern (default: NGG)")
    pam_scan_parser.add_argument("--protospacer-len", type=int, default=20, help="Protospacer length")
    pam_scan_parser.add_argument("--strand", default="both", choices=["both", "fwd", "rev"])
    pam_scan_parser.add_argument("--chrom", default=None, help="Chromosome name")
    _add_output_args(pam_scan_parser)
    pam_scan_parser.set_defaults(func=_cmd_pam_scan)

    # pam scan-region
    pam_region_parser = pam_sub.add_parser("scan-region", help="Scan genomic region")
    pam_region_parser.add_argument("--genome-id", required=True, help="Genome ID")
    pam_region_parser.add_argument("--chrom", required=True, help="Chromosome")
    pam_region_parser.add_argument("--start", type=int, required=True, help="Start (1-based)")
    pam_region_parser.add_argument("--end", type=int, required=True, help="End (exclusive)")
    pam_region_parser.add_argument("--pam-pattern", default="NGG", help="PAM pattern")
    pam_region_parser.add_argument("--protospacer-len", type=int, default=20)
    pam_region_parser.add_argument("--strand", default="both", choices=["both", "fwd", "rev"])
    _add_output_args(pam_region_parser)
    pam_region_parser.set_defaults(func=_cmd_pam_scan_region)

    # --- index ---
    index_parser = subparsers.add_parser("index", help="Index management")
    index_sub = index_parser.add_subparsers(dest="index_command", help="Index commands")

    index_build_parser = index_sub.add_parser("build", help="Build BWA index")
    index_build_parser.add_argument("--genome-id", required=True, help="Genome ID")
    index_build_parser.add_argument("--cas-variant", default="SpCas9", help="Cas variant")
    index_build_parser.add_argument("--force", action="store_true", help="Force rebuild")
    _add_output_args(index_build_parser)
    index_build_parser.set_defaults(func=_cmd_index_build)

    # --- offtarget ---
    offtarget_parser = subparsers.add_parser("offtarget", help="Off-target analysis")
    offtarget_sub = offtarget_parser.add_subparsers(dest="offtarget_command", help="Off-target commands")

    # offtarget search
    search_parser = offtarget_sub.add_parser("search", help="Search for off-targets")
    search_parser.add_argument("--spacer", "-s", required=True, help="Spacer sequence")
    search_parser.add_argument("--genome-id", required=True, help="Genome ID")
    search_parser.add_argument("--pam-pattern", default="NGG", help="PAM pattern")
    search_parser.add_argument("--max-mismatches", type=int, default=4, help="Max mismatches")
    search_parser.add_argument("--allow-bulge", action="store_true", help="Allow bulges")
    search_parser.add_argument("--cas-variant", default="SpCas9", help="Cas variant")
    _add_output_args(search_parser)
    search_parser.set_defaults(func=_cmd_offtarget_search)

    # offtarget score
    score_parser = offtarget_sub.add_parser("score", help="Score off-targets with CFD")
    score_parser.add_argument("--spacer", "-s", required=True, help="WT spacer sequence")
    score_parser.add_argument("--candidates-json", required=True, help="Candidates JSON file or -")
    score_parser.add_argument("--pam-pattern", default="NGG", help="PAM pattern")
    _add_output_args(score_parser)
    score_parser.set_defaults(func=_cmd_offtarget_score)

    # --- rank ---
    rank_parser = subparsers.add_parser("rank", help="Rank candidate guides")
    rank_parser.add_argument("--guides-json", required=True, help="Guides JSON file or -")
    rank_parser.add_argument("--offtargets-json", default=None, help="Off-targets JSON file")
    rank_parser.add_argument("--on-target-json", default=None, help="On-target scores JSON")
    rank_parser.add_argument("--sort-by", default="composite",
                            choices=["composite", "cfd_max", "offtarget_count", "on_target"])
    _add_output_args(rank_parser)
    rank_parser.set_defaults(func=_cmd_rank)

    # --- genome ---
    genome_parser = subparsers.add_parser("genome", help="Genome management")
    genome_sub = genome_parser.add_subparsers(dest="genome_command", help="Genome commands")

    genome_list_parser = genome_sub.add_parser("list", help="List registered genomes")
    _add_output_args(genome_list_parser)
    genome_list_parser.set_defaults(func=_cmd_genome_list)

    genome_info_parser = genome_sub.add_parser("info", help="Get genome information")
    genome_info_parser.add_argument("--genome-id", required=True, help="Genome ID")
    _add_output_args(genome_info_parser)
    genome_info_parser.set_defaults(func=_cmd_genome_info)

    # --- cache ---
    cache_parser = subparsers.add_parser("cache", help="Cache management")
    cache_sub = cache_parser.add_subparsers(dest="cache_command", help="Cache commands")

    cache_status_parser = cache_sub.add_parser("status", help="Show cache status")
    cache_status_parser.add_argument("--tool-name", default=None, help="Filter by tool")
    _add_output_args(cache_status_parser)
    cache_status_parser.set_defaults(func=_cmd_cache_status)

    cache_clear_parser = cache_sub.add_parser("clear", help="Clear cache")
    cache_clear_parser.add_argument("--tool-name", default=None, help="Clear specific tool cache")
    cache_clear_parser.add_argument("--confirm", action="store_true", help="Confirm clearing")
    _add_output_args(cache_clear_parser)
    cache_clear_parser.set_defaults(func=_cmd_cache_clear)

    # --- tools ---
    tools_parser = subparsers.add_parser("tools", help="Tool information")
    tools_sub = tools_parser.add_subparsers(dest="tools_command", help="Tool commands")

    tools_list_parser = tools_sub.add_parser("list", help="List available tools")
    _add_output_args(tools_list_parser)
    tools_list_parser.set_defaults(func=_cmd_tools_list)

    tools_describe_parser = tools_sub.add_parser("describe", help="Describe a tool")
    tools_describe_parser.add_argument("tool_name", help="Tool name")
    _add_output_args(tools_describe_parser)
    tools_describe_parser.set_defaults(func=_cmd_tools_describe)

    # --- sequence ---
    seq_parser = subparsers.add_parser("sequence", help="Sequence analysis commands")
    seq_sub = seq_parser.add_subparsers(dest="sequence_command", help="Sequence commands")

    seq_gc_parser = seq_sub.add_parser("gc", help="Compute GC content")
    seq_gc_parser.add_argument("--sequence", "-s", help="DNA sequence")
    seq_gc_parser.add_argument("--input", "-i", help="Input file (FASTA) or - for stdin")
    seq_gc_parser.add_argument("--gc-window-size", type=int, default=5, help="Sliding window size")
    seq_gc_parser.add_argument("--gc-split-ratio", type=float, default=0.5, help="5'/3' split ratio")
    seq_gc_parser.add_argument("--gc-min-threshold", type=float, default=0.20, help="Min GC threshold")
    seq_gc_parser.add_argument("--gc-max-threshold", type=float, default=0.80, help="Max GC threshold")
    seq_gc_parser.add_argument("--no-sliding-window", action="store_true", help="Disable sliding window")
    seq_gc_parser.add_argument("--no-half-split", action="store_true", help="Disable 5'/3' split")
    seq_gc_parser.add_argument("--round-decimals", type=int, default=3, help="Decimal places")
    _add_output_args(seq_gc_parser)
    seq_gc_parser.set_defaults(func=_cmd_sequence_gc)

    return parser


def main(argv=None):
    """Main entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # Handle pam/index/offtarget/genome/cache/tools subcommands
    if args.command == "pam":
        if not hasattr(args, "pam_command") or not args.pam_command:
            print("Error: specify a subcommand (scan, scan-region)", file=sys.stderr)
            return 1
    elif args.command == "index":
        if not hasattr(args, "index_command") or not args.index_command:
            print("Error: specify a subcommand (build)", file=sys.stderr)
            return 1
    elif args.command == "offtarget":
        if not hasattr(args, "offtarget_command") or not args.offtarget_command:
            print("Error: specify a subcommand (search, score)", file=sys.stderr)
            return 1
    elif args.command == "genome":
        if not hasattr(args, "genome_command") or not args.genome_command:
            print("Error: specify a subcommand (list, info)", file=sys.stderr)
            return 1
    elif args.command == "cache":
        if not hasattr(args, "cache_command") or not args.cache_command:
            print("Error: specify a subcommand (status, clear)", file=sys.stderr)
            return 1
    elif args.command == "tools":
        if not hasattr(args, "tools_command") or not args.tools_command:
            print("Error: specify a subcommand (list, describe)", file=sys.stderr)
            return 1
    elif args.command == "sequence":
        if not hasattr(args, "sequence_command") or not args.sequence_command:
            print("Error: specify a subcommand (gc)", file=sys.stderr)
            return 1

    if hasattr(args, "func"):
        return args.func(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
