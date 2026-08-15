"""MIDEND boundary validation for user-provided genomic and calibration files.

Supports two independent input classes:
1. analysis_input: FASTA, FASTQ, and GenBank files for normal genomic analysis workflows.
2. calibration_input: CSV and TSV files for optional experimental calibration datasets.
"""

from __future__ import annotations

import csv
import re
import uuid
from dataclasses import dataclass, field
from io import StringIO
from pathlib import PurePath
from typing import Any

from Bio import SeqIO

MAX_INPUT_BYTES = 50 * 1024 * 1024

ANALYSIS_FORMATS: dict[str, dict[str, Any]] = {
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

CALIBRATION_FORMATS: dict[str, dict[str, Any]] = {
    "csv": {
        "extensions": {".csv"},
        "mime_types": {"text/csv", "application/csv", "text/plain", "application/vnd.ms-excel"},
        "backend_operation": "calibration",
    },
    "tsv": {
        "extensions": {".tsv", ".tab"},
        "mime_types": {"text/tab-separated-values", "text/tsv", "text/plain"},
        "backend_operation": "calibration",
    },
}

SUPPORTED_FORMATS: dict[str, dict[str, Any]] = {**ANALYSIS_FORMATS, **CALIBRATION_FORMATS}

_ANALYSIS_EXT_TO_FORMAT = {ext: fmt for fmt, spec in ANALYSIS_FORMATS.items() for ext in spec["extensions"]}
_CALIBRATION_EXT_TO_FORMAT = {ext: fmt for fmt, spec in CALIBRATION_FORMATS.items() for ext in spec["extensions"]}
_EXT_TO_FORMAT = {**_ANALYSIS_EXT_TO_FORMAT, **_CALIBRATION_EXT_TO_FORMAT}
_DNA_CHARS = set("ACGTURYSWKMBDHVNacgturyswkmbdhvn-.* \t\r\n")


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
    sequence_count: int = 0
    input_class: str = "analysis_input"
    validation_status: str = "valid"
    backend_operation: str = "ingest_file"
    columns: list[str] | None = None
    column_count: int | None = None
    row_count: int | None = None
    calibration_status: str | None = None
    _content: bytes = field(repr=False, default=b"")

    def public(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "input_id": self.input_id,
            "filename": self.filename,
            "format": self.detected_format,
            "detected_format": self.detected_format,
            "input_class": self.input_class,
            "size_bytes": self.size_bytes,
            "record_count": self.record_count,
            "sequence_count": self.sequence_count,
            "validation_status": self.validation_status,
            "backend_operation": self.backend_operation,
        }
        if self.input_class == "calibration_input":
            result["columns"] = self.columns or []
            result["column_count"] = self.column_count or 0
            result["row_count"] = self.row_count or self.record_count
            result["sample_count"] = self.row_count or self.record_count
            result["calibration_status"] = self.calibration_status or "uncalibrated"
        return result


def _safe_filename(filename: str) -> str:
    if not filename or "\x00" in filename:
        raise MIDENDInputError("unreadable_file", "The uploaded file has no usable filename.")
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
    except Exception:
        raise MIDENDInputError("malformed_file",
                               f"The uploaded file has a {fmt.upper()} extension but its contents are not valid {fmt.upper()}.") from None
    if not records:
        raise MIDENDInputError("malformed_file", f"The uploaded {fmt.upper()} file contains no records.")
    for record in records:
        if not str(record.seq).strip():
            raise MIDENDInputError("malformed_file", f"The uploaded {fmt.upper()} file contains an empty sequence record.")
        _validate_sequence_text(str(record.seq), filename)
    return len(records)


def validate_calibration_file(filename: str, content: bytes, content_type: str | None = None,
                              max_bytes: int = MAX_INPUT_BYTES) -> ValidatedInput:
    """Validate CSV/TSV calibration tabular dataset structure and header."""
    filename = _safe_filename(filename)
    size = len(content)
    if size == 0:
        raise MIDENDInputError("empty_file", f"The uploaded calibration file '{filename}' is empty.", field="file")
    if size > max_bytes:
        raise MIDENDInputError("file_too_large", f"The uploaded file exceeds the {max_bytes} byte limit.", field="file")

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    ext = f".{extension}" if extension else ""
    expected = _CALIBRATION_EXT_TO_FORMAT.get(ext)
    if expected is None:
        raise MIDENDInputError("unsupported_calibration_format",
                               f"Unsupported calibration format '{ext or '[no extension]'}'. Supported formats: .csv, .tsv.",
                               field="file")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise MIDENDInputError("malformed_file", f"The uploaded '{filename}' is not valid UTF-8 text.", field="file") from None

    if not text.strip():
        raise MIDENDInputError("empty_file", f"The uploaded calibration file '{filename}' is empty.", field="file")

    delimiter = "," if expected == "csv" else "\t"
    try:
        reader = csv.reader(StringIO(text), delimiter=delimiter)
        raw_rows = [row for row in reader]
    except Exception:
        raise MIDENDInputError("malformed_file", f"Failed to parse tabular structure in '{filename}'.", field="file") from None

    # Filter non-empty rows
    rows = [row for row in raw_rows if any(cell.strip() for cell in row)]
    if not rows:
        raise MIDENDInputError("empty_dataset", f"The uploaded calibration dataset '{filename}' is empty.", field="file")

    header = [c.strip() for c in rows[0]]
    if not header or all(c == "" for c in header):
        raise MIDENDInputError("missing_header", f"The calibration file '{filename}' has no detectable header row.", field="file")

    # Check for obvious delimiter mismatch
    if expected == "csv" and len(header) == 1 and "\t" in rows[0][0]:
        raise MIDENDInputError("mismatched_file_format",
                               f"The file '{filename}' has a .csv extension but contains tab-separated data.", field="file")
    if expected == "tsv" and len(header) == 1 and "," in rows[0][0]:
        raise MIDENDInputError("mismatched_file_format",
                               f"The file '{filename}' has a .tsv extension but contains comma-separated data.", field="file")

    data_rows = rows[1:]
    if not data_rows:
        raise MIDENDInputError("empty_dataset",
                               f"The uploaded calibration dataset '{filename}' contains a header but no data rows.",
                               field="file")

    header_len = len(header)
    for idx, row in enumerate(data_rows, start=2):
        if len(row) != header_len:
            raise MIDENDInputError("inconsistent_columns",
                                   f"Row {idx} has {len(row)} columns, expected {header_len}.",
                                   field="file")

    return ValidatedInput(
        input_id=new_id("calib"),
        filename=filename,
        detected_format=expected,
        size_bytes=size,
        record_count=len(data_rows),
        sequence_count=0,
        input_class="calibration_input",
        validation_status="valid",
        backend_operation="calibration",
        columns=header,
        column_count=header_len,
        row_count=len(data_rows),
        calibration_status="uncalibrated",
        _content=content,
    )


def validate_input_file(filename: str, content: bytes, content_type: str | None = None,
                        max_bytes: int = MAX_INPUT_BYTES,
                        expected_class: str | None = None) -> ValidatedInput:
    """Validate extension, MIME hint, content format, and biological or calibration structure."""
    filename = _safe_filename(filename)
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    ext = f".{extension}" if extension else ""

    if expected_class == "calibration_input" or (expected_class is None and ext in _CALIBRATION_EXT_TO_FORMAT):
        return validate_calibration_file(filename, content, content_type, max_bytes)

    size = len(content)
    if size == 0:
        raise MIDENDInputError("empty_file", f"The uploaded file '{filename}' is empty.")
    if size > max_bytes:
        raise MIDENDInputError("file_too_large", f"The uploaded file exceeds the {max_bytes} byte limit.")

    expected = _ANALYSIS_EXT_TO_FORMAT.get(ext)
    if expected is None:
        if expected_class == "calibration_input":
            raise MIDENDInputError("unsupported_calibration_format",
                                   f"Unsupported calibration format '{ext or '[no extension]'}'. Supported formats: .csv, .tsv.")
        supported = ", ".join(sorted(_ANALYSIS_EXT_TO_FORMAT))
        raise MIDENDInputError("unsupported_file_type",
                               f"Unsupported input file type '{ext or '[no extension]'}'. Supported extensions: {supported}.")

    if content_type and content_type.lower().split(";", 1)[0] not in ANALYSIS_FORMATS[expected]["mime_types"]:
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
    return ValidatedInput(
        input_id=new_id("input"),
        filename=filename,
        detected_format=actual,
        size_bytes=size,
        record_count=record_count,
        sequence_count=record_count,
        input_class="analysis_input",
        validation_status="valid",
        backend_operation=ANALYSIS_FORMATS[actual]["backend_operation"],
        _content=content,
    )


def new_id(prefix: str = "input") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


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

    def get_analysis_input(self, input_id: str) -> ValidatedInput:
        item = self.get(input_id)
        if item.input_class != "analysis_input":
            raise MIDENDInputError("invalid_input_class",
                                   f"Input '{input_id}' is a {item.input_class}, expected an analysis_input.",
                                   field="input_id")
        return item

    def get_calibration_input(self, input_id: str) -> ValidatedInput:
        try:
            item = self.items[input_id]
        except KeyError:
            raise MIDENDInputError("unknown_calibration_input",
                                   f"The calibration input '{input_id}' was not found.",
                                   field="calibration_input_id") from None
        if item.input_class != "calibration_input":
            raise MIDENDInputError("invalid_input_class",
                                   f"Input '{input_id}' is a {item.input_class}, expected a calibration_input.",
                                   field="calibration_input_id")
        return item

    def list_analysis_inputs(self) -> list[ValidatedInput]:
        return [item for item in self.items.values() if item.input_class == "analysis_input"]

    def list_calibration_inputs(self) -> list[ValidatedInput]:
        return [item for item in self.items.values() if item.input_class == "calibration_input"]


