"""FASTQ parser for VEYRA.

Uses Biopython's SeqIO to parse FASTQ files.  Quality scores are
preserved in the GenomicRecord.quality field.
"""

from __future__ import annotations

import os
from typing import Iterator

from Bio import SeqIO

from schemas.genomic_record import GenomicRecord, Provenance, QualityData, VEYRAFormat

PARSER_NAME = "biopython.SeqIO.fastq"
PARSER_VERSION = "1.83"


def parse(filepath: str) -> Iterator[GenomicRecord]:
    """Yield GenomicRecord for each read in the FASTQ file.

    Args:
        filepath: Path to a FASTQ-formatted file.

    Yields:
        GenomicRecord for each read found.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is empty or cannot be parsed.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    filename = os.path.basename(filepath)
    record_count = 0

    for bio_record in SeqIO.parse(filepath, "fastq"):
        record_count += 1
        seq = str(bio_record.seq).upper()
        quals = bio_record.letter_annotations.get("phred_quality", [])

        quality: QualityData | None = None
        if quals:
            quality = QualityData(
                scores=quals,
                mean_quality=sum(quals) / len(quals) if quals else None,
                min_quality=min(quals) if quals else None,
                max_quality=max(quals) if quals else None,
            )

        accession = bio_record.id if bio_record.id else None

        record = GenomicRecord(
            id=bio_record.id or f"read_{record_count}",
            sequence=seq,
            description=bio_record.description or "",
            accession=accession,
            quality=quality,
            provenance=Provenance(
                source_filename=filename,
                input_format=VEYRAFormat.FASTQ,
                parser_name=PARSER_NAME,
                parser_version=PARSER_VERSION,
                accession=accession,
            ),
        )
        yield record

    if record_count == 0:
        raise ValueError(f"FASTQ file is empty or malformed: {filepath}")
