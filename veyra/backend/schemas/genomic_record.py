"""VEYRA normalized genomic data model.

Defines the internal representation for ingested genomic data.
All parsers produce GenomicRecord instances that downstream
VEYRA modules consume.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class VEYRAFormat(str, enum.Enum):
    """Supported and detected input formats."""

    FASTA = "fasta"
    FASTQ = "fastq"
    GENBANK = "genbank"
    UNKNOWN = "unknown"


@dataclass
class GenomicCoordinate:
    """Genomic coordinates for a feature or region."""

    start: int | None = None
    end: int | None = None
    strand: int | None = None  # 1 = forward, -1 = reverse, 0 = unknown
    scaffold: str | None = None
    assembly: str | None = None


@dataclass
class GenomicFeature:
    """A single annotated feature from a sequence record (e.g. gene, CDS)."""

    type: str = ""
    location: GenomicCoordinate | None = None
    qualifiers: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class QualityData:
    """Quality scores for FASTQ reads."""

    scores: list[int] = field(default_factory=list)
    mean_quality: float | None = None
    min_quality: int | None = None
    max_quality: int | None = None


@dataclass
class Provenance:
    """Tracks where the data came from and how it was processed."""

    source_filename: str = ""
    input_format: VEYRAFormat = VEYRAFormat.UNKNOWN
    parser_name: str = ""
    parser_version: str = ""
    database_source: str | None = None
    accession: str | None = None
    assembly_version: str | None = None


@dataclass
class ValidationResult:
    """Result of validating a parsed record."""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PAMSite:
    """A detected PAM (Protospacer Adjacent Motif) site in a sequence.

    PAM sites are short DNA motifs required for CRISPR-Cas9 binding.
    The PAM is located immediately 3' of the protospacer on the
    non-target (displaced) strand.  In this representation, positions
    refer to the forward strand of the input sequence.
    """

    position: int  # 0-based start position of the PAM on the forward strand
    pam_sequence: str  # the PAM motif (e.g. "NGG")
    pam_type: str  # canonical PAM class (e.g. "NGG", "NAG", "NNNNGATT")
    strand: int  # 1 = forward strand, -1 = reverse complement strand
    spacer_start: int | None = None  # start of the 20nt spacer (upstream of PAM)
    spacer_end: int | None = None  # end of the 20nt spacer
    spacer_sequence: str | None = None  # the 20nt protospacer sequence
    guide_rna: str | None = None  # 20nt guide RNA (reverse complement of spacer)


@dataclass
class PAMScanResult:
    """Results of a PAM scan across a genomic sequence."""

    pam_sites: list[PAMSite] = field(default_factory=list)
    total_sites: int = 0
    forward_sites: int = 0
    reverse_sites: int = 0
    pam_types_found: dict[str, int] = field(default_factory=dict)


@dataclass
class GenomicRecord:
    """Normalized internal representation of a single genomic sequence record.

    This is the core data structure produced by all VEYRA parsers.
    Downstream modules (BLAST, CRISPOR, reasoning layers) consume
    GenomicRecord instances.
    """

    id: str = ""
    sequence: str = ""
    length: int = 0
    description: str = ""
    accession: str | None = None
    annotations: dict[str, Any] = field(default_factory=dict)
    features: list[GenomicFeature] = field(default_factory=list)
    coordinate: GenomicCoordinate | None = None
    quality: QualityData | None = None
    pam_scan: PAMScanResult | None = None
    provenance: Provenance = field(default_factory=Provenance)
    validation: ValidationResult = field(default_factory=ValidationResult)

    def __post_init__(self) -> None:
        if self.length == 0 and self.sequence:
            self.length = len(self.sequence)

    def summary(self) -> dict[str, Any]:
        """Return a concise summary dict suitable for display."""
        pam_info: dict[str, Any] | None = None
        if self.pam_scan is not None:
            pam_info = {
                "total_sites": self.pam_scan.total_sites,
                "forward_sites": self.pam_scan.forward_sites,
                "reverse_sites": self.pam_scan.reverse_sites,
                "pam_types": self.pam_scan.pam_types_found,
            }
        return {
            "id": self.id,
            "length": self.length,
            "description": self.description[:120] if self.description else "",
            "accession": self.accession,
            "format": self.provenance.input_format.value,
            "features_count": len(self.features),
            "has_quality": self.quality is not None,
            "pam_scan": pam_info,
            "is_valid": self.validation.is_valid,
            "errors": self.validation.errors,
            "warnings": self.validation.warnings,
        }
