"""Portability regression tests for midend service."""

import os
from pathlib import Path
import pytest

from veyra.midend.ai.tool_catalog import compute_contract_hash, build_tool_catalog, get_tool_catalog
from veyra.midend.tests.test_genome_scope import ECOLI_FASTA_PATH


def test_tool_catalog_contract_hash_computes_without_laptop_paths():
    """Verify compute_contract_hash resolves midend.md portably."""
    h = compute_contract_hash()
    assert isinstance(h, str)
    assert len(h) == 16


def test_tool_catalog_builds_all_tools():
    """Verify tool catalog builds cleanly and contains all native tools."""
    catalog = build_tool_catalog(force_rebuild=True)
    assert len(catalog.tools) >= 15
    assert "pam_scan" in catalog.tools
    assert "compute_gc_content" in catalog.tools
    assert "offtarget_search" in catalog.tools


def test_ecoli_fixture_path_resolves_to_existing_file():
    """Verify test fixture resolution for E. coli genome."""
    assert ECOLI_FASTA_PATH.is_file(), f"E. coli FASTA file not found at: {ECOLI_FASTA_PATH}"
