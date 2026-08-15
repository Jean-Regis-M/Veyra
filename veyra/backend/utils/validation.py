"""Validation utilities for VEYRA genomic records.

Provides functions to validate parsed GenomicRecord instances
before they enter the downstream pipeline.
"""

from __future__ import annotations

from schemas.genomic_record import GenomicRecord, ValidationResult

# Nucleotide alphabet (IUPAC)
_VALID_DNA = set("ACGTNRYSWKMBDHVUacgtNRYSWKMBDHVU")
_VALID_RNA = set("ACGNRYSWKMBDHVNacgnrYSWKMBDHVn")


def validate_record(record: GenomicRecord) -> GenomicRecord:
    """Validate a GenomicRecord and populate its validation field.

    Checks:
        - sequence is non-empty
        - sequence length matches the stored length field
        - sequence contains only valid nucleotide characters
        - record ID is non-empty

    Returns:
        The same GenomicRecord with validation field populated.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not record.id:
        errors.append("Record ID is empty")

    if not record.sequence:
        errors.append("Sequence is empty")
    else:
        if record.length != len(record.sequence):
            warnings.append(
                f"Length mismatch: stored={record.length}, actual={len(record.sequence)}"
            )

        invalid_chars = set(record.sequence) - _VALID_DNA - _VALID_RNA
        if invalid_chars:
            warnings.append(
                f"Non-standard nucleotide characters found: {sorted(invalid_chars)}"
            )

    if record.length < 0:
        errors.append(f"Negative sequence length: {record.length}")

    record.validation = ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
    return record


def validate_records(records: list[GenomicRecord]) -> list[GenomicRecord]:
    """Validate a batch of records."""
    return [validate_record(r) for r in records]
