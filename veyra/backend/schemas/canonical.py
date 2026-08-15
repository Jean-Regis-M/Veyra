"""Canonical schemas for VEYRA unified interface.

Shared request/response models used by CLI, HTTP API, MCP, and Python API.
All interfaces convert to/from these canonical types.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass, field
from typing import Any


# ============================================================================
# Request schemas
# ============================================================================

@dataclass
class IngestRequest:
    """Request for file ingestion."""
    input_path: str
    pam_scan: bool = False
    pam_names: list[str] | None = None
    output_format: str = "json"


@dataclass
class PamScanRequest:
    """Request for PAM scanning on raw sequence."""
    sequence: str
    pam_pattern: str = "NGG"
    protospacer_len: int = 20
    strand: str = "both"
    chrom: str | None = None


@dataclass
class PamScanRegionRequest:
    """Request for PAM scanning on a genomic region."""
    genome_id: str
    chrom: str
    start: int
    end: int
    pam_pattern: str = "NGG"
    protospacer_len: int = 20
    strand: str = "both"


@dataclass
class BuildIndexRequest:
    """Request for building a BWA index."""
    genome_id: str
    cas_variant: str = "SpCas9"
    force_rebuild: bool = False


@dataclass
class OfftargetSearchRequest:
    """Request for off-target search."""
    spacer_sequence: str
    genome_id: str
    pam_pattern: str = "NGG"
    max_mismatches: int = 4
    allow_bulge: bool = False
    cas_variant: str = "SpCas9"


@dataclass
class ScoreOfftargetsRequest:
    """Request for CFD scoring of off-target candidates."""
    spacer_sequence: str
    candidates: list[dict[str, Any]] = field(default_factory=list)
    pam_pattern: str = "NGG"


@dataclass
class RankCandidatesRequest:
    """Request for ranking candidate guides."""
    guides: list[dict[str, Any]] = field(default_factory=list)
    off_targets: list[dict[str, Any]] | None = None
    on_target_scores: dict[str, float] | None = None
    sort_by: str = "composite"


@dataclass
class GenomeListRequest:
    """Request for listing genomes."""
    pass


@dataclass
class GenomeInfoRequest:
    """Request for genome info."""
    genome_id: str


@dataclass
class CacheStatusRequest:
    """Request for cache status."""
    tool_name: str | None = None


@dataclass
class CacheClearRequest:
    """Request for clearing cache."""
    tool_name: str | None = None


# ============================================================================
# Result schemas
# ============================================================================

@dataclass
class ResultRow:
    """A single result row — uniform across all tools."""
    chrom: str | None = None
    start: int | None = None
    end: int | None = None
    strand: str | None = None
    protospacer: str | None = None
    pam: str | None = None
    pam_type: str | None = None
    mismatch_count: int | None = None
    mismatch_positions: str | None = None
    cfd_score: float | None = None
    rs2_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VeyraResult:
    """Standard result wrapper for all VEYRA operations."""
    tool: str
    rows: list[ResultRow] = field(default_factory=list)
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
        writer = csv.DictWriter(
            buf, fieldnames=fieldnames, delimiter="\t",
            extrasaction="ignore", restval=""
        )
        writer.writeheader()
        for row in self.rows:
            d = row.to_dict()
            writer.writerow({k: ("" if v is None else v) for k, v in d.items()})
        return buf.getvalue()

    def to_text(self) -> str:
        """Human-readable text output."""
        lines = [f"Tool: {self.tool}"]
        if self.summary:
            lines.append("Summary:")
            for k, v in self.summary.items():
                lines.append(f"  {k}: {v}")
        if self.errors:
            lines.append("Errors:")
            for e in self.errors:
                lines.append(f"  - {e}")
        if self.warnings:
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  - {w}")
        if self.rows:
            lines.append(f"Results ({len(self.rows)} rows):")
            for row in self.rows[:10]:
                d = row.to_dict()
                parts = [f"{k}={v}" for k, v in d.items() if v is not None]
                lines.append(f"  {', '.join(parts)}")
            if len(self.rows) > 10:
                lines.append(f"  ... and {len(self.rows) - 10} more rows")
        return "\n".join(lines)


# ============================================================================
# Error model
# ============================================================================

@dataclass
class VeyraError:
    """Structured error response."""
    error: str
    code: str = "UNKNOWN"
    details: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)


# ============================================================================
# Genome info
# ============================================================================

@dataclass
class GenomeInfo:
    """Information about a registered genome."""
    genome_id: str
    display_name: str
    fasta_path: str
    has_fai: bool = False
    has_bwa_index: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================================
# Cache status
# ============================================================================

@dataclass
class CacheStatus:
    """Cache status information."""
    total_entries: int = 0
    by_tool: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
