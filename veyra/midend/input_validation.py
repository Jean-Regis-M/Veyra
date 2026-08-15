"""MIDEND boundary validation for user-provided genomic files.

The backend's actual ingestion parsers support FASTA, FASTQ, and GenBank.
GFF/GFF3 and arbitrary plain-text DNA files are intentionally not accepted as
file uploads because no corresponding VEYRA backend parser exists.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from io import StringIO
from pathlib import PurePath
from typing import Any

from Bio import SeqIO

MAX_INPUT_BYTES = 50 * 1024 * 1024

SUPPORTED_FORMATS: dict[str, dict[str, Any]] = {
    "fasta": {
        "extensions": {".fa", ".fasta", ".fna", ".faa", ".fns", ".frn"},
        "mime_types": {"text/x-fasta", "application/x-fasta", "chemical/seq-na-fasta", "text/plain"},
        "backend_operation": "ingest_file",
    },
    "fastq": {
        "extensions": {".fq", ".fastq", ".fqr"},
        "mime_types": {"text/fastq", "application/fastq", "text/plain"},
        "backend_operation": "ingest_file",
    },
    "genbank": {
        "extensions": {".gb", ".gbk", ".gbff", ".genbank"},
        "mime_types": {"text/plain", "chemical/seq-genbank", "application/x-genbank"},
        "backend_operation": "ingest_file",
    },
}

_EXT_TO_FORMAT = {ext: fmt for fmt, spec in SUPPORTED_FORMATS.items() for ext in spec["extensions"]}
_DNA_CHARS = set("ACGTURYSWKMBDHVNacgturyswkmbdhvn-.* \\t\\r\\n")


class MIDENDInputError(ValueError):
    """Structured, safe error raised before AI/backend execution."""

    def __init__(self, error: str, message: str, field: str = "file"):
        self.error = error
        self.message = message
        self.field = field
        super().__init__(message)

    def to_dict(self) -> dict[str, str]:
        return {"error": self.error, "message": self.message, "field": self.field}


@dataclass(frozen=True)
class ValidatedInput:
    input_id: str
    filename: str
    detected_format: str
    size_bytes: int
    record_count: int
    sequence_count: int
    validation_status: str = "valid"
    backend_operation: str = "ingest_file"
    _content: bytes = field(repr=False, default=b"")

    def public(self) -> dict[str, Any]:
        return {
            "input_id": self.input_id,
            "filename": self.filename,
            "format": self.detected_format,
            "detected_format": self.detected_format,
            "size_bytes": self.size_bytes,
            "record_count": self.record_count,
            "sequence_count": self.sequence_count,
            "validation_status": self.validation_status,
            "backend_operation": self.backend_operation,
        }


def _safe_filename(filename: str) -> str:
    if not filename or "\x00" in filename:
        raise MIDENDInputError("unreadable_file", "The uploaded file has no usable filename.")
    # Multipart filenames are names, never paths. Reject both POSIX and Windows separators.
    if filename != PurePath(filename).name or "/" in filename or "\\" in filename or ".." in filename:
        raise MIDENDInputError("path_traversal", "File paths are not accepted; upload a file by filename.")
    return filename


def _content_format(text: str) -> str | None:
    nonempty = [line.strip() for line in text.splitlines() if line.strip()]
    if not nonempty:
        return None
    first = nonempty[0]
    if first.startswith(">"):
        return "fasta"
    if first.startswith("LOCUS ") or first.startswith("ID   ") or first.startswith("ACCESSION "):
        return "genbank"
    if first.startswith("@"):
        # A FASTQ candidate must contain a complete four-line record shape.
        lines = text.splitlines()
        if len(lines) >= 4 and lines[2].strip().startswith("+"):
            return "fastq"
        return None
    return None


def _validate_sequence_text(sequence: str, filename: str) -> None:
    if not sequence.strip():
        raise MIDENDInputError("empty_file", f"The uploaded file '{filename}' is empty.")
    if set(sequence) - _DNA_CHARS:
        raise MIDENDInputError("invalid_sequence_format",
                               f"The sequence data in '{filename}' contains invalid nucleotide characters.")


def _parse_records(fmt: str, text: str, filename: str) -> int:
    try:
        records = list(SeqIO.parse(StringIO(text), {"fasta": "fasta", "fastq": "fastq", "genbank": "genbank"}[fmt]))
    except Exception as exc:
        raise MIDENDInputError("malformed_file",
                               f"The uploaded file has a {fmt.upper()} extension but its contents are not valid {fmt.upper()}.") from None
    if not records:
        raise MIDENDInputError("malformed_file", f"The uploaded {fmt.upper()} file contains no records.")
    for record in records:
        if not str(record.seq).strip():
            raise MIDENDInputError("malformed_file", f"The uploaded {fmt.upper()} file contains an empty sequence record.")
        _validate_sequence_text(str(record.seq), filename)
    return len(records)


def validate_input_file(filename: str, content: bytes, content_type: str | None = None,
                        max_bytes: int = MAX_INPUT_BYTES) -> ValidatedInput:
    """Validate extension, MIME hint, content format, and biological structure."""
    filename = _safe_filename(filename)
    size = len(content)
    if size == 0:
        raise MIDENDInputError("empty_file", f"The uploaded file '{filename}' is empty.")
    if size > max_bytes:
        raise MIDENDInputError("file_too_large", f"The uploaded file exceeds the {max_bytes} byte limit.")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    ext = f".{extension}" if extension else ""
    expected = _EXT_TO_FORMAT.get(ext)
    if expected is None:
        supported = ", ".join(sorted(_EXT_TO_FORMAT))
        raise MIDENDInputError("unsupported_file_type",
                               f"Unsupported input file type '{ext or '[no extension]'}'. Supported extensions: {supported}.")
    if content_type and content_type.lower().split(";", 1)[0] not in SUPPORTED_FORMATS[expected]["mime_types"]:
        # Generic octet-stream is accepted as a transport container; format is still checked below.
        if content_type.lower().split(";", 1)[0] not in {"application/octet-stream", ""}:
            raise MIDENDInputError("unsupported_file_type", f"MIME type '{content_type}' does not match '{filename}'.")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise MIDENDInputError("malformed_file", f"The uploaded '{filename}' is not valid UTF-8 text.") from None
    actual = _content_format(text)
    if actual is None:
        raise MIDENDInputError("malformed_file",
                               f"The uploaded file has a {expected.upper()} extension but its contents are not valid {expected.upper()}.")
    if actual != expected:
        raise MIDENDInputError("mismatched_file_format",
                               f"The filename extension indicates {expected.upper()}, but the content is {actual.upper()}.")
    record_count = _parse_records(actual, text, filename)
    return ValidatedInput(new_id(), filename, actual, size, record_count, record_count,
                          backend_operation=SUPPORTED_FORMATS[actual]["backend_operation"], _content=content)


def new_id() -> str:
    return f"input_{uuid.uuid4().hex[:12]}"


class InputRegistry:
    """Process-local store for validated bytes and safe metadata."""

    def __init__(self):
        self.items: dict[str, ValidatedInput] = {}

    def add(self, item: ValidatedInput) -> ValidatedInput:
        self.items[item.input_id] = item
        return item

    def get(self, input_id: str) -> ValidatedInput:
        try:
            return self.items[input_id]
        except KeyError:
            raise MIDENDInputError("unknown_input", "The validated input was not found.", field="input_id") from None

