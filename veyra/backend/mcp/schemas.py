"""Shared schemas for MCP tool inputs and outputs.

Coordinate convention: ALL coordinates are 1-based, half-open [start, end)
consistent with samtools/BLAST convention.  start is inclusive, end is exclusive.

All fields use None/null when not applicable to a particular tool.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PAMSiteRow:
    """A single PAM site result row — uniform across all tools."""

    chrom: str | None = None
    start: int | None = None  # 1-based
    end: int | None = None  # exclusive
    strand: str | None = None  # "+" or "-"
    protospacer: str | None = None
    pam: str | None = None
    pam_type: str | None = None
    mismatch_count: int | None = None
    mismatch_positions: str | None = None  # comma-separated 0-based positions
    cfd_score: float | None = None
    rs2_score: float | None = None
    bulge_type: str | None = None  # "X", "DNA", or "RNA"
    bulge_size: int | None = None
    bulge_position: int | None = None
    aligned_guide: str | None = None  # aligned guide with gaps
    aligned_candidate: str | None = None  # aligned candidate with gaps
    cfd_status: str | None = None  # "unsupported_bulge" for bulged candidates

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolResult:
    """Standard wrapper for MCP tool results."""

    tool: str
    rows: list[PAMSiteRow] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(
            {
                "tool": self.tool,
                "rows": [r.to_dict() for r in self.rows],
                "summary": self.summary,
                "errors": self.errors,
                "warnings": self.warnings,
                "metadata": self.metadata,
            },
            indent=indent,
            default=str,
        )

    def to_tsv(self) -> str:
        if not self.rows:
            return ""
        fieldnames = list(self.rows[0].to_dict().keys())
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, delimiter="\t",
                                extrasaction="ignore", restval="")
        writer.writeheader()
        for row in self.rows:
            d = row.to_dict()
            # Replace None with empty string for TSV
            writer.writerow({k: ("" if v is None else v) for k, v in d.items()})
        return buf.getvalue()


# --- Validation helpers ---

_DNA_VALID = set("ACGTacgt")
_IUPAC_VALID = set("ACGTacgtRYSWKMBDHVNryswkmbdhvn")


def validate_dna_sequence(seq: str, allow_iupac: bool = False) -> str:
    """Validate and normalize a DNA sequence string.

    Returns the uppercased sequence.
    Raises ValueError on invalid input.
    """
    if not seq or not seq.strip():
        raise ValueError("Sequence is empty")
    seq = seq.strip().upper()
    valid = _IUPAC_VALID if allow_iupac else _DNA_VALID
    invalid = set(seq) - valid
    if invalid:
        raise ValueError(f"Invalid nucleotide characters: {sorted(invalid)}")
    return seq


def validate_chrom(chrom: str) -> str:
    """Validate and normalize a chromosome name."""
    if not chrom or not chrom.strip():
        raise ValueError("Chromosome name is empty")
    return chrom.strip()


def validate_coordinates(start: int, end: int, seq_len: int | None = None) -> tuple[int, int]:
    """Validate genomic coordinates (1-based, half-open).

    Returns validated (start, end).
    """
    if start < 1:
        raise ValueError(f"Start position must be >= 1, got {start}")
    if end < start:
        raise ValueError(f"End position ({end}) must be >= start ({start})")
    if seq_len is not None and end > seq_len + 1:
        raise ValueError(f"End position ({end}) exceeds sequence length ({seq_len})")
    return start, end


def validate_pam_pattern(pattern: str) -> str:
    """Validate an IUPAC PAM pattern."""
    pattern = pattern.strip().upper()
    if not pattern:
        raise ValueError("PAM pattern is empty")
    invalid = set(pattern) - _IUPAC_VALID
    if invalid:
        raise ValueError(f"Invalid IUPAC characters in PAM pattern: {sorted(invalid)}")
    return pattern
