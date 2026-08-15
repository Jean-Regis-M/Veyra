"""Core ingestion service.

Wraps the existing ingestion pipeline into a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import IngestRequest, VeyraResult, ResultRow
from services.ingestion import ingest_file, get_ingestion_summary


def ingest(request: IngestRequest) -> VeyraResult:
    """Ingest a genomic file.

    Args:
        request: IngestRequest with input_path, pam_scan, pam_names.

    Returns:
        VeyraResult with ingestion summary.
    """
    try:
        summary = get_ingestion_summary(
            request.input_path,
            pam_scan=request.pam_scan,
            pam_names=request.pam_names,
        )

        rows = []
        for rec in summary.get("records", []):
            pam_info = rec.get("pam_scan")
            rows.append(ResultRow(
                chrom=rec.get("id"),
                start=None,
                end=None,
                strand=None,
                protospacer=None,
                pam=None,
                pam_type=None,
                mismatch_count=pam_info.get("total_sites") if pam_info else None,
                mismatch_positions=None,
                cfd_score=None,
                rs2_score=None,
            ))

        return VeyraResult(
            tool="ingest",
            rows=rows,
            summary={
                "input_file": summary.get("input_file"),
                "detected_format": summary.get("detected_format"),
                "num_records": summary.get("num_records"),
                "total_bases": summary.get("total_bases"),
            },
            errors=[],
            warnings=[],
            metadata={},
        )
    except Exception as e:
        return VeyraResult(
            tool="ingest",
            errors=[str(e)],
        )
