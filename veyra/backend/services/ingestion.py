"""VEYRA ingestion service.

Orchestrates format detection, parsing, validation, PAM scanning,
and conversion into normalized GenomicRecord instances.
"""

from __future__ import annotations

import os
from typing import Iterator

from parsers.detector import detect_format, FormatDetectionError
from parsers.fasta_parser import parse as parse_fasta
from parsers.fastq_parser import parse as parse_fastq
from parsers.genbank_parser import parse as parse_genbank
from parsers.pam import scan_pam, scan_pam_multi, PAM_DATABASE
from schemas.genomic_record import GenomicRecord, VEYRAFormat
from utils.validation import validate_record


class IngestionError(Exception):
    """Raised when ingestion fails due to format or parsing issues."""


def ingest_file(
    filepath: str,
    *,
    pam_scan: bool = False,
    pam_names: list[str] | None = None,
) -> Iterator[GenomicRecord]:
    """Detect format, parse, validate, and yield normalized GenomicRecords.

    Args:
        filepath: Path to an input genomic file.
        pam_scan: If True, run PAM detection on each record's sequence.
        pam_names: List of PAM types to scan for (default: ["SpCas9"]).
                   Only used when pam_scan is True.

    Yields:
        Validated GenomicRecord instances.

    Raises:
        FileNotFoundError: If the file does not exist.
        IngestionError: If format detection fails or parsing fails.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Input file not found: {filepath}")

    try:
        fmt = detect_format(filepath)
    except FormatDetectionError as exc:
        raise IngestionError(str(exc)) from exc

    if fmt == VEYRAFormat.UNKNOWN:
        raise IngestionError(
            f"Cannot determine format of file: {filepath}. "
            "Supported formats: FASTA, FASTQ, GenBank."
        )

    parser_map = {
        VEYRAFormat.FASTA: parse_fasta,
        VEYRAFormat.FASTQ: parse_fastq,
        VEYRAFormat.GENBANK: parse_genbank,
    }

    parser = parser_map.get(fmt)
    if parser is None:
        raise IngestionError(f"No parser available for format: {fmt.value}")

    try:
        for record in parser(filepath):
            validated = validate_record(record)

            if pam_scan and validated.sequence:
                if pam_names:
                    validated.pam_scan = scan_pam_multi(validated.sequence, pam_names)
                else:
                    validated.pam_scan = scan_pam(validated.sequence)

            yield validated
    except ValueError as exc:
        raise IngestionError(f"Parsing error for {filepath}: {exc}") from exc
    except OSError as exc:
        raise IngestionError(f"I/O error reading {filepath}: {exc}") from exc


def ingest_file_list(filepath: str, **kwargs) -> list[GenomicRecord]:
    """Ingest a file and return all records as a list (convenience wrapper)."""
    return list(ingest_file(filepath, **kwargs))


def get_ingestion_summary(
    filepath: str,
    *,
    pam_scan: bool = False,
    pam_names: list[str] | None = None,
) -> dict:
    """Ingest a file and return a concise summary dict.

    Useful for CLI output – avoids loading huge sequences into memory
    for display purposes.
    """
    records: list[GenomicRecord] = []
    total_bases = 0
    for record in ingest_file(filepath, pam_scan=pam_scan, pam_names=pam_names):
        records.append(record)
        total_bases += record.length

    if not records:
        raise IngestionError(f"No records found in {filepath}")

    fmt = records[0].provenance.input_format if records else VEYRAFormat.UNKNOWN

    return {
        "input_file": filepath,
        "detected_format": fmt.value,
        "num_records": len(records),
        "total_bases": total_bases,
        "records": [r.summary() for r in records],
    }
