"""VEYRA ingestion service.

Orchestrates format detection, parsing, validation, and conversion
into normalized GenomicRecord instances.  This is the main entry point
for the ingestion pipeline.
"""

from __future__ import annotations

import os
from typing import Iterator

from parsers.detector import detect_format, FormatDetectionError
from parsers.fasta_parser import parse as parse_fasta
from parsers.fastq_parser import parse as parse_fastq
from parsers.genbank_parser import parse as parse_genbank
from schemas.genomic_record import GenomicRecord, VEYRAFormat
from utils.validation import validate_record


class IngestionError(Exception):
    """Raised when ingestion fails due to format or parsing issues."""


def ingest_file(filepath: str) -> Iterator[GenomicRecord]:
    """Detect format, parse, validate, and yield normalized GenomicRecords.

    Args:
        filepath: Path to an input genomic file.

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
            yield validated
    except ValueError as exc:
        raise IngestionError(f"Parsing error for {filepath}: {exc}") from exc
    except OSError as exc:
        raise IngestionError(f"I/O error reading {filepath}: {exc}") from exc


def ingest_file_list(filepath: str) -> list[GenomicRecord]:
    """Ingest a file and return all records as a list (convenience wrapper)."""
    return list(ingest_file(filepath))


def get_ingestion_summary(filepath: str) -> dict:
    """Ingest a file and return a concise summary dict.

    Useful for CLI output – avoids loading huge sequences into memory
    for display purposes.
    """
    records: list[GenomicRecord] = []
    total_bases = 0
    for record in ingest_file(filepath):
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
