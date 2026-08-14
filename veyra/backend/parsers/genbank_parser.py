"""GenBank parser for VEYRA.

Uses Biopython's SeqIO to parse GenBank files.  Preserves features,
annotations, coordinates, and source metadata.
"""

from __future__ import annotations

import os
from typing import Iterator

from Bio import SeqIO
from Bio.SeqFeature import SimpleLocation

from schemas.genomic_record import (
    GenomicCoordinate,
    GenomicFeature,
    GenomicRecord,
    Provenance,
    VEYRAFormat,
)

PARSER_NAME = "biopython.SeqIO.genbank"
PARSER_VERSION = "1.83"


def parse(filepath: str) -> Iterator[GenomicRecord]:
    """Yield GenomicRecord for each entry in the GenBank file.

    Args:
        filepath: Path to a GenBank-formatted file (.gb, .gbk, .gbff).

    Yields:
        GenomicRecord for each record found.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is empty or cannot be parsed.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    filename = os.path.basename(filepath)
    record_count = 0

    for bio_record in SeqIO.parse(filepath, "genbank"):
        record_count += 1
        seq = str(bio_record.seq).upper()

        # Extract source annotation metadata
        source_feature = None
        for feat in bio_record.features:
            if feat.type == "source":
                source_feature = feat
                break

        accession = bio_record.id
        assembly_version: str | None = None
        database_source: str | None = None

        if source_feature is not None:
            quals = source_feature.qualifiers
            if "db_xref" in quals:
                database_source = "; ".join(quals["db_xref"])
            # Try to find assembly info
            if "note" in quals:
                for note in quals["note"]:
                    if "assembly" in note.lower():
                        assembly_version = note
                        break

        # Convert Biopython features to VEYRA features
        features: list[GenomicFeature] = []
        for feat in bio_record.features:
            coord = _convert_location(feat.location)
            features.append(
                GenomicFeature(
                    type=feat.type,
                    location=coord,
                    qualifiers={k: list(v) for k, v in feat.qualifiers.items()},
                )
            )

        # Build coordinate from source feature
        coordinate: GenomicCoordinate | None = None
        if source_feature is not None and source_feature.location is not None:
            coordinate = _convert_location(source_feature.location)
            if coordinate:
                coordinate.assembly = assembly_version

        # Build annotations dict from record annotations
        annotations: dict[str, str | list[str]] = {}
        for key, value in bio_record.annotations.items():
            if isinstance(value, list):
                annotations[key] = value
            else:
                annotations[key] = str(value)

        record = GenomicRecord(
            id=bio_record.id,
            sequence=seq,
            description=bio_record.description or "",
            accession=accession,
            annotations=annotations,
            features=features,
            coordinate=coordinate,
            provenance=Provenance(
                source_filename=filename,
                input_format=VEYRAFormat.GENBANK,
                parser_name=PARSER_NAME,
                parser_version=PARSER_VERSION,
                accession=accession,
                database_source=database_source,
                assembly_version=assembly_version,
            ),
        )
        yield record

    if record_count == 0:
        raise ValueError(f"GenBank file is empty or cannot be parsed: {filepath}")


def _convert_location(location: SimpleLocation | None) -> GenomicCoordinate | None:
    """Convert a Biopython SeqFeature location to a GenomicCoordinate."""
    if location is None:
        return None
    return GenomicCoordinate(
        start=int(location.start),
        end=int(location.end),
        strand=location.strand if location.strand is not None else 0,
        scaffold=location.ref if location.ref else None,
    )
