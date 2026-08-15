#!/usr/bin/env python3
"""VEYRA – Genomic Intelligence Backend.

Command-line entry point for ingesting genomic data files
(FASTA, FASTQ, GenBank) and producing normalized VEYRA records.

Usage:
    python veyra.py --input /path/to/file.fasta
    python veyra.py --help
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Ensure the backend package root is on sys.path so that relative imports work
# regardless of how the script is invoked.
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.genomic_record import GenomicRecord
from parsers.pam import PAM_DATABASE
from services.ingestion import IngestionError, ingest_file, get_ingestion_summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veyra",
        description="VEYRA – Genomic Intelligence Backend (Ingestion Module)",
        epilog=(
            "Supported formats: FASTA (.fa/.fasta/.fna/.faa), "
            "FASTQ (.fq/.fastq), GenBank (.gb/.gbk/.gbff)."
        ),
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input genomic file.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output full record data as JSON instead of a human-readable summary.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress the summary; output only JSON if --json is set, otherwise nothing.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        default=False,
        help="Parse and validate without printing a summary (exit code indicates result).",
    )
    parser.add_argument(
        "--pam",
        action="store_true",
        default=False,
        help="Enable PAM (Protospacer Adjacent Motif) scanning for CRISPR analysis.",
    )
    parser.add_argument(
        "--pam-types",
        nargs="+",
        default=None,
        help=(
            "PAM types to scan for. Default: SpCas9 (NGG). "
            f"Available: {', '.join(PAM_DATABASE.keys())}. "
            "Can specify multiple: --pam-types SpCas9 Cas12a"
        ),
    )
    return parser


def _print_summary(summary: dict) -> None:
    """Print a human-readable summary of the ingestion result."""
    print("=" * 60)
    print("VEYRA Ingestion Summary")
    print("=" * 60)
    print(f"  Input file      : {summary['input_file']}")
    print(f"  Detected format : {summary['detected_format']}")
    print(f"  Number of records: {summary['num_records']}")
    print(f"  Total bases     : {summary['total_bases']:,}")
    print("-" * 60)
    for i, rec in enumerate(summary["records"], 1):
        status = "OK" if rec["is_valid"] else "INVALID"
        print(f"  [{i}] ID       : {rec['id']}")
        print(f"      Length     : {rec['length']:,}")
        print(f"      Description: {rec['description'][:80]}")
        print(f"      Accession  : {rec.get('accession', 'N/A')}")
        print(f"      Format     : {rec['format']}")
        print(f"      Features   : {rec['features_count']}")
        print(f"      Quality    : {'yes' if rec['has_quality'] else 'no'}")
        print(f"      Validation : {status}")
        if rec["errors"]:
            for err in rec["errors"]:
                print(f"        ERROR: {err}")
        if rec["warnings"]:
            for warn in rec["warnings"]:
                print(f"        WARN : {warn}")
        # PAM scan results
        pam = rec.get("pam_scan")
        if pam is not None:
            print(f"      PAM Sites  : {pam['total_sites']} total "
                  f"({pam['forward_sites']} fwd, {pam['reverse_sites']} rev)")
            if pam["pam_types"]:
                for ptype, count in pam["pam_types"].items():
                    print(f"        {ptype}: {count}")
        print()
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    """Main entry point.  Returns 0 on success, non-zero on error."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    filepath = args.input
    pam_scan = args.pam
    pam_names = args.pam_types

    if not os.path.isfile(filepath):
        print(f"Error: file not found – {filepath}", file=sys.stderr)
        return 1

    try:
        if args.json:
            summary = get_ingestion_summary(filepath, pam_scan=pam_scan, pam_names=pam_names)
            if not args.quiet:
                print(json.dumps(summary, indent=2))
            return 0

        if args.validate_only:
            count = 0
            for record in ingest_file(filepath, pam_scan=pam_scan, pam_names=pam_names):
                if not record.validation.is_valid:
                    return 2
                count += 1
            if count == 0:
                print("No records found.", file=sys.stderr)
                return 2
            return 0

        # Default: human-readable summary
        summary = get_ingestion_summary(filepath, pam_scan=pam_scan, pam_names=pam_names)
        if not args.quiet:
            _print_summary(summary)
        return 0

    except IngestionError as exc:
        print(f"Ingestion error: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
