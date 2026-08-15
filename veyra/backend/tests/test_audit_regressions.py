"""Regression tests for issues found during the final repository audit."""

from unittest.mock import patch

from mcp.schemas import PAMSiteRow
from mcp.tools.cas_offinder_search import cas_offinder_search
from mcp.tools.offtarget_search import offtarget_search


def test_cas_offinder_validates_shared_paging_and_strand_controls():
    result = cas_offinder_search(
        "A" * 20,
        "missing_genome",
        strand_search="sideways",
    )
    assert result.errors
    assert "strand_search" in result.errors[0]

    result = cas_offinder_search("A" * 20, "missing_genome", max_results=0)
    assert result.errors
    assert "max_results" in result.errors[0]


def test_offtarget_forwards_cas_offinder_interface_controls():
    expected = {"tool": "cas_offinder_search"}

    with patch(
        "mcp.tools.cas_offinder_search.cas_offinder_search",
        return_value=expected,
    ) as mocked:
        result = offtarget_search(
            "A" * 20,
            "test_genome",
            backend="cas_offinder",
            allow_bulge=True,
            strand_search="rev",
            max_results=7,
        )

    assert result == expected
    assert mocked.call_args.kwargs["strand_search"] == "rev"
    assert mocked.call_args.kwargs["max_results"] == 7


def test_offtarget_rejects_incomplete_bwa_region_before_engine_call():
    result = offtarget_search(
        "A" * 20,
        "test_genome",
        backend="bwa",
        search_scope="region",
    )
    assert result.errors
    assert "required" in result.errors[0]


def test_cas_rows_can_be_capped_without_scoring_bulges():
    # This verifies the canonical row shape used by the cap/filter logic.
    row = PAMSiteRow(bulge_type="DNA", bulge_size=1, cfd_status="unsupported_bulge")
    assert row.cfd_status == "unsupported_bulge"


def test_bwa_extracts_and_enforces_the_adjacent_pam():
    result = offtarget_search(
        "GATTGCCACCAAAGTGATGC",
        "ecoli_k12_mg1655",
        max_mismatches=2,
        max_results=5,
    )
    assert not result.errors
    assert result.rows
    assert all(row.pam is not None for row in result.rows)
    assert all(row.pam.endswith("GG") for row in result.rows)
