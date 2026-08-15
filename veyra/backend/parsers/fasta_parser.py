"""FASTA parser for VEYRA.

Uses Biopython's SimpleFastaParser to read FASTA files and produce
VEYRA GenomicRecord instances.
"""

from __future__ import annotations

import os
from typing import Iterator

from Bio.SeqIO.FastaIO import SimpleFastaParser

from schemas.genomic_record import GenomicRecord, Provenance, VEYRAFormat

PARSER_NAME = "biopython.SimpleFastaParser"
PARSER_VERSION = "1.83"


def parse(filepath: str) -> Iterator[GenomicRecord]:
    """Yield GenomicRecord for each sequence in the FASTA file.

    Args:
        filepath: Path to a FASTA-formatted file.

    Yields:
        GenomicRecord for each record found.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is empty or malformed.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    filename = os.path.basename(filepath)
    record_count = 0

    with open(filepath, "r", encoding="utf-8") as fh:
        for title, sequence in SimpleFastaParser(fh):
            record_count += 1
            seq = sequence.strip().upper()
            if not seq:
                continue

            # Parse the FASTA header: first word is ID, rest is description
            parts = title.split(None, 1)
            record_id = parts[0] if parts else f"seq_{record_count}"
            description = title if len(parts) > 1 else ""

            # Attempt to extract accession from the ID
            accession = _extract_accession(record_id)

            record = GenomicRecord(
                id=record_id,
                sequence=seq,
                description=description,
                accession=accession,
                provenance=Provenance(
                    source_filename=filename,
                    input_format=VEYRAFormat.FASTA,
                    parser_name=PARSER_NAME,
                    parser_version=PARSER_VERSION,
                    accession=accession,
                ),
            )
            yield record

    if record_count == 0:
        raise ValueError(f"FASTA file is empty or malformed: {filepath}")


def _extract_accession(record_id: str) -> str | None:
    """Try to pull a meaningful accession from the record ID."""
    # Common patterns: gi|12345|ref|NM_001234.1|, XM_001234.5, NM_001234.1
    if "|" in record_id:
        parts = record_id.split("|")
        for part in parts:
            if any(part.startswith(p) for p in ("NM_", "XM_", "NR_", "NC_", "NG_", "NP_", "WP_")):
                return part
        return parts[-1] if len(parts) > 1 else record_id
    return record_id
