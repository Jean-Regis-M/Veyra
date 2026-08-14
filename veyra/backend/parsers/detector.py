"""Input format detection for VEYRA.

Inspects file extension and file content headers to identify
FASTA, FASTQ, or GenBank format.  Extensions are used as a
first hint; content inspection confirms or overrides.
"""

from __future__ import annotations

import os
from typing import TextIO

from schemas.genomic_record import VEYRAFormat

# ---------------------------------------------------------------------------
# Extension mapping
# ---------------------------------------------------------------------------
_EXTENSION_MAP: dict[str, VEYRAFormat] = {
    ".fa": VEYRAFormat.FASTA,
    ".fasta": VEYRAFormat.FASTA,
    ".fna": VEYRAFormat.FASTA,
    ".faa": VEYRAFormat.FASTA,
    ".fns": VEYRAFormat.FASTA,
    ".frn": VEYRAFormat.FASTA,
    ".fq": VEYRAFormat.FASTQ,
    ".fastq": VEYRAFormat.FASTQ,
    ".fqr": VEYRAFormat.FASTQ,
    ".gb": VEYRAFormat.GENBANK,
    ".gbk": VEYRAFormat.GENBANK,
    ".gbff": VEYRAFormat.GENBANK,
    ".genbank": VEYRAFormat.GENBANK,
}


class FormatDetectionError(Exception):
    """Raised when the input format cannot be determined."""


def detect_by_extension(filepath: str) -> VEYRAFormat:
    """Detect format from the file extension (case-insensitive)."""
    _, ext = os.path.splitext(filepath)
    return _EXTENSION_MAP.get(ext.lower(), VEYRAFormat.UNKNOWN)


def detect_by_content(filepath: str) -> VEYRAFormat:
    """Detect format by reading the first few lines of the file.

    This is the authoritative detector; extensions are only hints.
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            return _detect_from_stream(fh)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise FormatDetectionError(f"Cannot read file for format detection: {exc}") from exc


def _detect_from_stream(fh: TextIO) -> VEYRAFormat:
    """Inspect the first non-empty lines of a text stream."""
    header_lines: list[str] = []
    for _ in range(20):
        line = fh.readline()
        if not line:
            break
        header_lines.append(line.rstrip("\n\r"))
    if not header_lines:
        return VEYRAFormat.UNKNOWN

    # GenBank starts with "LOCUS "
    for line in header_lines:
        stripped = line.strip()
        if stripped.startswith("LOCUS "):
            return VEYRAFormat.GENBANK
        if stripped.startswith("ID   "):
            return VEYRAFormat.GENBANK
        if stripped.startswith("ACCESSION "):
            return VEYRAFormat.GENBANK

    # FASTQ: first non-empty line starts with "@"
    for line in header_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("@"):
            # Quick heuristic: look for the "+ " quality separator
            # in the next few lines
            return _confirm_fastq(fh, header_lines)
        break

    # FASTA: first non-empty line starts with ">"
    for line in header_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            return VEYRAFormat.FASTA
        break

    return VEYRAFormat.UNKNOWN


def _confirm_fastq(fh: TextIO, already_read: list[str]) -> VEYRAFormat:
    """After seeing '@', confirm this is FASTQ by looking for the '+' separator."""
    # We already read the header line.  The next non-empty line should be
    # sequence, then '+', then quality.
    lines = list(already_read)
    for _ in range(5):
        line = fh.readline()
        if not line:
            break
        lines.append(line.rstrip("\n\r"))

    # Find the '@' line index, then look for '+' a few lines later
    at_idx: int | None = None
    for i, line in enumerate(lines):
        if line.strip().startswith("@"):
            at_idx = i
            break
    if at_idx is None:
        return VEYRAFormat.UNKNOWN

    # After '@' header there should be sequence, then '+', then quality
    remaining = lines[at_idx + 1 :]
    plus_found = any(l.strip().startswith("+") for l in remaining)
    if plus_found:
        return VEYRAFormat.FASTQ
    # Not confirmed – treat as FASTA with '@' in description
    return VEYRAFormat.FASTA


def detect_format(filepath: str) -> VEYRAFormat:
    """Public API: detect format using extension + content heuristics.

    Returns VEYRAFormat.UNKNOWN if the format cannot be determined.
    Raises FileNotFoundError if the file does not exist.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Input file not found: {filepath}")

    ext_fmt = detect_by_extension(filepath)
    content_fmt = detect_by_content(filepath)

    # If content detection gives UNKNOWN but extension is clear, trust extension
    if content_fmt != VEYRAFormat.UNKNOWN:
        return content_fmt
    if ext_fmt != VEYRAFormat.UNKNOWN:
        return ext_fmt

    return VEYRAFormat.UNKNOWN
