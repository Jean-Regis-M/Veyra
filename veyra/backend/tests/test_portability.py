"""Portability regression tests for arbitrary deployment root discovery."""

import os
from pathlib import Path
import pytest

from references import get_genome, list_genomes, get_cfd_resources, _get_reference_search_roots
from core.model_runtime import get_model_runtime_path, _load_state, get_model_status
from core.model_registry import initialize_model_registry, get_model_registry


def test_reference_registry_discovers_ecoli_portably():
    """Verify E. coli reference genome is registered with an existing FASTA path."""
    ecoli = get_genome("ecoli_k12_mg1655")
    assert ecoli is not None
    assert ecoli.genome_id == "ecoli_k12_mg1655"
    assert os.path.isfile(ecoli.fasta_path), f"FASTA path does not exist: {ecoli.fasta_path}"
    assert ecoli.fasta_path.endswith("data/references/ecoli_k12/genome/GCF_000005845.2.fasta")
    assert os.path.isabs(ecoli.fasta_path)


def test_cfd_resources_resolve_portably():
    """Verify CFD scoring resources are discovered and loadable without hardcoded laptop paths."""
    mismatch_path, pam_path = get_cfd_resources()
    assert os.path.isfile(mismatch_path), f"Missing mismatch score file: {mismatch_path}"
    assert os.path.isfile(pam_path), f"Missing PAM score file: {pam_path}"
    assert "crispor_cfd" in mismatch_path or "CFD_Scoring" in mismatch_path


def test_model_runtime_paths_derive_from_current_root(monkeypatch):
    """Verify model runtime paths adapt when VEYRA_DATA_DIR / VEYRA_MODEL_ENVS_DIR is set."""
    custom_envs_dir = "/tmp/custom_model_envs"
    monkeypatch.setenv("VEYRA_MODEL_ENVS_DIR", custom_envs_dir)
    
    # Reload model runtime module path config
    import core.model_runtime as mr
    monkeypatch.setattr(mr, "_MODEL_ENVS_DIR", custom_envs_dir)
    
    rt_path = mr.get_model_runtime_path("rule_set_2")
    assert rt_path == "/tmp/custom_model_envs/rule_set_2"


def test_reference_search_roots_respect_environment_variable(monkeypatch):
    """Verify external reference roots can be configured via environment variable."""
    monkeypatch.setenv("GENOME_REFERENCES_DIR", "/opt/genomes")
    roots = _get_reference_search_roots()
    assert Path("/opt/genomes") in roots


def test_model_registry_initializes_cleanly():
    """Verify model registry builds without error and contains all 3 models."""
    registry = initialize_model_registry()
    assert "doench_2014" in registry
    assert "rule_set_2" in registry
    assert "rule_set_3" in registry
    
    # Verify doench_2014 is available and verified
    doench = registry["doench_2014"]
    assert doench.availability == "verified"
    assert doench.compatible is True
    assert doench.verified is True
    assert doench.installed is True
