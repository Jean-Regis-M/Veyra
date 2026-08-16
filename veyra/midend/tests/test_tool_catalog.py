"""Tests for in-memory cached tool catalog derived from authoritative contract."""

import pytest
from veyra.midend.ai.tool_catalog import build_tool_catalog, get_tool_catalog, ToolCatalog, compute_contract_hash
from veyra.midend.ai.tool_definitions import NATIVE_TOOLS_DEFINITIONS, AUTHORITATIVE_DEFAULTS


def test_tool_catalog_build_and_caching():
    catalog = build_tool_catalog(force_rebuild=True)
    assert isinstance(catalog, ToolCatalog)
    assert catalog.version == "1.0.0"
    assert len(catalog.contract_hash) == 16

    # Verify cached retrieval returns the exact same object
    cached = get_tool_catalog()
    assert cached is catalog
    assert cached.contract_hash == catalog.contract_hash


def test_tool_catalog_all_tools_represented():
    catalog = get_tool_catalog()
    tool_names = set(catalog.tools.keys())
    expected_tools = {defn["function"]["name"] for defn in NATIVE_TOOLS_DEFINITIONS}

    assert tool_names == expected_tools
    assert len(tool_names) >= 17


def test_tool_catalog_schema_validity():
    catalog = get_tool_catalog()
    for name, entry in catalog.tools.items():
        assert entry.name == name
        assert entry.description
        assert entry.category in {"pam_discovery", "geometry", "sequence_qc", "thermodynamics", "features", "offtarget", "scoring", "ranking", "skill", "general"}
        assert entry.cost_tier in {"cheap", "moderate", "expensive"}
        assert isinstance(entry.mutating, bool)
        assert isinstance(entry.prerequisites, list)
        assert isinstance(entry.schema, dict)
        assert entry.schema.get("type") == "function"
        func = entry.schema.get("function", {})
        assert func.get("name") == name
        assert "parameters" in func
        assert func["parameters"].get("type") == "object"


def test_tool_catalog_defaults_and_units():
    catalog = get_tool_catalog()
    pam_tool = catalog.get_tool("pam_scan")
    assert pam_tool is not None
    assert pam_tool.defaults.get("pam_pattern") == "NGG"
    assert pam_tool.defaults.get("protospacer_len") == 20
    assert pam_tool.defaults.get("strand") == "both"

    gc_tool = catalog.get_tool("compute_gc_content")
    assert gc_tool is not None
    assert gc_tool.defaults.get("gc_window_size") == 5


def test_tool_catalog_category_filtering():
    catalog = get_tool_catalog()
    qc_tools = catalog.get_tools_by_category("sequence_qc")
    qc_names = {t.name for t in qc_tools}
    assert "compute_gc_content" in qc_names
    assert "check_homopolymer_runs" in qc_names
    assert "compute_seed_gc" in qc_names


def test_tool_catalog_selective_schemas():
    catalog = get_tool_catalog()
    subset = catalog.get_native_schemas(["pam_scan", "compute_gc_content"])
    assert len(subset) == 2
    names = {s["function"]["name"] for s in subset}
    assert names == {"pam_scan", "compute_gc_content"}


def test_compact_tool_directory_generation():
    from veyra.midend.ai.tool_catalog import generate_compact_tool_directory, get_compact_directory_entries
    catalog = get_tool_catalog()
    entries = get_compact_directory_entries(catalog)
    
    # 1. Tool count matches catalog
    assert len(entries) == len(catalog.tools)
    
    # 2. Names are unique
    names = [e["name"] for e in entries]
    assert len(names) == len(set(names))
    
    # 3. Descriptions/purposes are non-empty
    for e in entries:
        assert e["name"]
        assert e["purpose"]
        assert e["category"]
        assert e["cost_tier"]
        assert e["schema_id"]
    
    # 4. Directory string is concise and contains all tool names
    directory_text = generate_compact_tool_directory(catalog)
    assert "AVAILABLE VEYRA CAPABILITY DIRECTORY:" in directory_text
    for name in names:
        assert name in directory_text


def test_skill_and_task_aware_tool_selection():
    from veyra.midend.ai.tool_catalog import select_active_tool_names, get_active_tool_schemas

    # 1. Calibration skill or input class
    calib_tools = select_active_tool_names(active_skill="model_calibration")
    assert "model_calibration" in calib_tools
    assert "offtarget_toxicity_risk" in calib_tools
    assert "pam_scan" not in calib_tools  # Narrowed set!

    calib_input_tools = select_active_tool_names(input_class="calibration_input")
    assert "model_calibration" in calib_input_tools

    # 2. Gene cutting skill or analysis input
    spcas9_tools = select_active_tool_names(active_skill="spcas9_gene_cutting")
    assert "spcas9_gene_cutting" in spcas9_tools
    assert "pam_scan" in spcas9_tools
    assert "compute_gc_content" in spcas9_tools
    assert "model_calibration" not in spcas9_tools

    # 3. Toxicity / off-target task intent
    tox_tools = select_active_tool_names(user_task="Calculate off-target toxicity risk score")
    assert "offtarget_toxicity_risk" in tox_tools
    assert "score_offtargets" in tox_tools

    # 4. Explicit tool schemas
    schemas = get_active_tool_schemas(active_skill="model_calibration")
    assert len(schemas) == len(calib_tools)
    schema_names = {s["function"]["name"] for s in schemas}
    assert schema_names == set(calib_tools)


def test_parameter_meta_default_and_override_validation():
    from veyra.midend.ai.tool_definitions import analyze_parameters_meta

    # 1. Default parameter call
    meta_default = analyze_parameters_meta("pam_scan", {"pam_pattern": "NGG", "protospacer_len": 20})
    pam_pattern_info = meta_default.get("pam_pattern", {})
    assert pam_pattern_info["status"] == "default"
    assert pam_pattern_info["value"] == "NGG"
    assert pam_pattern_info["default"] == "NGG"

    # 2. Parameter override
    meta_override = analyze_parameters_meta("pam_scan", {"pam_pattern": "NAG", "protospacer_len": 21, "strand": "fwd"})
    pam_override = meta_override.get("pam_pattern", {})
    assert pam_override["status"] == "overridden"
    assert pam_override["value"] == "NAG"
    assert pam_override["default"] == "NGG"

    strand_override = meta_override.get("strand", {})
    assert strand_override["status"] == "overridden"
    assert strand_override["value"] == "fwd"
    assert strand_override["default"] == "both"

    # 3. Supplied custom parameter (no default in contract)
    meta_custom = analyze_parameters_meta("pam_scan", {"sequence": "ACGTACGT"})
    seq_info = meta_custom.get("sequence", {})
    assert seq_info["status"] == "supplied"
    assert seq_info["value"] == "ACGTACGT"



