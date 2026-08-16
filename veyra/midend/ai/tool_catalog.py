"""Authoritative in-memory cached tool catalog for VEYRA MIDEND.

Derives tool definitions, defaults, cost tiers, and prerequisites from the
authoritative contract and live tool schemas.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from dataclasses import asdict, dataclass, field
from typing import Any

from .tool_definitions import (
    AUTHORITATIVE_DEFAULTS,
    NATIVE_TOOLS_DEFINITIONS,
    PARAMETER_UNITS,
    analyze_parameters_meta,
)

TOOL_METADATA_EXTENSIONS: dict[str, dict[str, Any]] = {
    "pam_scan": {
        "category": "pam_discovery",
        "cost_tier": "cheap",
        "mutating": False,
        "prerequisites": ["sequence"],
        "one_line": "Scan target DNA sequence for SpCas9 NGG/NAG PAM sites and extract protospacers",
    },
    "pam_scan_region": {
        "category": "pam_discovery",
        "cost_tier": "cheap",
        "mutating": False,
        "prerequisites": ["genomic_region"],
        "one_line": "Scan coordinates within a reference genome for PAM target sites",
    },
    "compute_cut_site": {
        "category": "geometry",
        "cost_tier": "cheap",
        "mutating": False,
        "prerequisites": ["spacer_start", "strand"],
        "one_line": "Compute exact SpCas9 blunt cut site coordinates (between position 17 and 18, 3bp upstream of PAM)",
    },
    "compute_gc_content": {
        "category": "sequence_qc",
        "cost_tier": "cheap",
        "mutating": False,
        "prerequisites": ["sequence"],
        "one_line": "Calculate total GC%, sliding-window GC profile, and half-split (5' vs 3') ratios",
    },
    "check_homopolymer_runs": {
        "category": "sequence_qc",
        "cost_tier": "cheap",
        "mutating": False,
        "prerequisites": ["sequence"],
        "one_line": "Detect homopolymer repeats (>=4 nt) and flag strict poly-T termination signals",
    },
    "compute_melting_temp": {
        "category": "thermodynamics",
        "cost_tier": "cheap",
        "mutating": False,
        "prerequisites": ["sequence"],
        "one_line": "Calculate nearest-neighbor DNA/DNA melting temperature (Tm) with salt/cation corrections",
    },
    "compute_secondary_structure": {
        "category": "thermodynamics",
        "cost_tier": "moderate",
        "mutating": False,
        "prerequisites": ["sequence"],
        "one_line": "Predict Minimum Free Energy (MFE) secondary structures and guide hairpin folding",
    },
    "compute_positional_features": {
        "category": "features",
        "cost_tier": "cheap",
        "mutating": False,
        "prerequisites": ["sequence"],
        "one_line": "Extract single-nucleotide position weights, G-bias at position 20, and base distribution",
    },
    "compute_dinucleotide_composition": {
        "category": "features",
        "cost_tier": "cheap",
        "mutating": False,
        "prerequisites": ["sequence"],
        "one_line": "Compute adjacent 2-mer dinucleotide frequency matrices across spacer",
    },
    "compute_seed_gc": {
        "category": "sequence_qc",
        "cost_tier": "cheap",
        "mutating": False,
        "prerequisites": ["sequence"],
        "one_line": "Compute GC content specifically in the critical 10nt PAM-proximal seed region",
    },
    "analyze_mismatch_seed": {
        "category": "offtarget",
        "cost_tier": "cheap",
        "mutating": False,
        "prerequisites": ["guide_sequence", "offtarget_sequence"],
        "one_line": "Evaluate mismatch counts partitioned into PAM-proximal seed vs non-seed regions",
    },
    "offtarget_search": {
        "category": "offtarget",
        "cost_tier": "expensive",
        "mutating": False,
        "prerequisites": ["spacer_sequence", "genome_id"],
        "one_line": "Perform genome-wide alignment search for off-target loci up to specified mismatch tolerance",
    },
    "score_offtargets": {
        "category": "offtarget",
        "cost_tier": "moderate",
        "mutating": False,
        "prerequisites": ["spacer_sequence", "candidates"],
        "one_line": "Calculate Cutting Frequency Determination (CFD) specificity scores for off-target hits",
    },
    "predict_ontarget_efficiency": {
        "category": "scoring",
        "cost_tier": "moderate",
        "mutating": False,
        "prerequisites": ["context_sequence"],
        "one_line": "Predict on-target cleavage efficiency using Rule Set 3 or Doench 2014 models",
    },
    "rank_candidates": {
        "category": "ranking",
        "cost_tier": "cheap",
        "mutating": False,
        "prerequisites": ["guides"],
        "one_line": "Rank candidate guides deterministically using composite score, on-target score, or specificity",
    },
    "spcas9_gene_cutting": {
        "category": "skill",
        "cost_tier": "moderate",
        "mutating": False,
        "prerequisites": ["sequence_or_input_id"],
        "one_line": "Comprehensive pipeline skill: PAM scanning, geometry, QC, on-target scoring, and candidate ranking",
    },
    "offtarget_toxicity_risk": {
        "category": "skill",
        "cost_tier": "moderate",
        "mutating": False,
        "prerequisites": ["spacer_sequence"],
        "one_line": "Audit and compute off-target toxicity risk combining CFD, binding energy, and accessibility features",
    },
    "model_calibration": {
        "category": "skill",
        "cost_tier": "moderate",
        "mutating": False,
        "prerequisites": ["calibration_input_id"],
        "one_line": "Experimental model calibration skill: fit model coefficients on a validated labeled CSV/TSV dataset",
    },
}


@dataclass
class ToolCatalogEntry:
    name: str
    description: str
    category: str
    cost_tier: str
    mutating: bool
    prerequisites: list[str]
    schema: dict[str, Any]
    defaults: dict[str, Any]
    parameter_units: dict[str, str]
    availability: bool = True
    one_line: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolCatalog:
    version: str
    contract_hash: str
    tools: dict[str, ToolCatalogEntry] = field(default_factory=dict)

    def get_tool(self, name: str) -> ToolCatalogEntry | None:
        return self.tools.get(name)

    def list_tools(self) -> list[ToolCatalogEntry]:
        return list(self.tools.values())

    def get_tools_by_category(self, category: str) -> list[ToolCatalogEntry]:
        return [t for t in self.tools.values() if t.category == category]

    def get_native_schemas(self, tool_names: list[str] | None = None) -> list[dict[str, Any]]:
        if tool_names is None:
            return [t.schema for t in self.tools.values() if t.availability]
        return [self.tools[name].schema for name in tool_names if name in self.tools and self.tools[name].availability]


_CACHED_CATALOG: ToolCatalog | None = None
_CACHED_CONTRACT_HASH: str | None = None


def compute_contract_hash() -> str:
    """Compute sha256 checksum of midend.md and tool definitions for cache invalidation."""
    hasher = hashlib.sha256()
    # Check midend.md if it exists
    base_dir = Path(__file__).resolve().parent
    possible_contract_paths = [
        os.environ.get("MIDEND_CONTRACT_PATH"),
        os.environ.get("VEYRA_MIDEND_CONTRACT_PATH"),
        str(base_dir.parent.parent / "midend.md"),
        str(base_dir.parent / "midend.md"),
        str(base_dir.parent.parent.parent / "midend.md"),
        str(base_dir.parent.parent.parent / "veyra" / "midend.md"),
    ]
    contract_bytes = b""
    for p in possible_contract_paths:
        if p and os.path.isfile(p):
            try:
                with open(p, "rb") as f:
                    contract_bytes = f.read()
                break
            except Exception:
                pass
    hasher.update(contract_bytes)
    # Also hash tool definition keys and defaults
    for defn in NATIVE_TOOLS_DEFINITIONS:
        hasher.update(defn.get("function", {}).get("name", "").encode("utf-8"))
    for k, v in sorted(AUTHORITATIVE_DEFAULTS.items()):
        hasher.update(f"{k}:{sorted(v.items())}".encode("utf-8"))
    return hasher.hexdigest()[:16]


def build_tool_catalog(force_rebuild: bool = False) -> ToolCatalog:
    """Build or retrieve cached tool catalog derived from authoritative contracts."""
    global _CACHED_CATALOG, _CACHED_CONTRACT_HASH
    current_hash = compute_contract_hash()

    if not force_rebuild and _CACHED_CATALOG is not None and _CACHED_CONTRACT_HASH == current_hash:
        return _CACHED_CATALOG

    catalog_entries: dict[str, ToolCatalogEntry] = {}

    for defn in NATIVE_TOOLS_DEFINITIONS:
        func = defn.get("function", {})
        name = func.get("name", "")
        desc = func.get("description", "")
        ext = TOOL_METADATA_EXTENSIONS.get(name, {})
        category = ext.get("category", "general")
        cost_tier = ext.get("cost_tier", "cheap")
        mutating = ext.get("mutating", False)
        prerequisites = ext.get("prerequisites", [])
        one_line = ext.get("one_line", desc.split(".")[0] if desc else name)
        defaults = AUTHORITATIVE_DEFAULTS.get(name, {})
        units = PARAMETER_UNITS.get(name, {})

        entry = ToolCatalogEntry(
            name=name,
            description=desc,
            category=category,
            cost_tier=cost_tier,
            mutating=mutating,
            prerequisites=prerequisites,
            schema=defn,
            defaults=defaults,
            parameter_units=units,
            availability=True,
            one_line=one_line,
        )
        catalog_entries[name] = entry

    catalog = ToolCatalog(
        version="1.0.0",
        contract_hash=current_hash,
        tools=catalog_entries,
    )

    _CACHED_CATALOG = catalog
    _CACHED_CONTRACT_HASH = current_hash
    return catalog


def get_tool_catalog() -> ToolCatalog:
    """Get active in-memory cached tool catalog."""
    if _CACHED_CATALOG is None:
        return build_tool_catalog()
    return _CACHED_CATALOG


def get_compact_directory_entries(catalog: ToolCatalog | None = None) -> list[dict[str, str]]:
    """Return compact metadata dictionaries for all available tools."""
    cat = catalog or get_tool_catalog()
    entries = []
    for tool in cat.list_tools():
        if not tool.availability:
            continue
        entries.append({
            "name": tool.name,
            "purpose": tool.one_line,
            "category": tool.category,
            "cost_tier": tool.cost_tier,
            "prerequisites": ", ".join(tool.prerequisites) if tool.prerequisites else "none",
            "schema_id": f"{tool.name}.v1",
        })
    return entries


def generate_compact_tool_directory(catalog: ToolCatalog | None = None) -> str:
    """Generate a lightweight text directory of all tools for AI context discovery."""
    entries = get_compact_directory_entries(catalog)
    lines = ["AVAILABLE VEYRA CAPABILITY DIRECTORY:"]
    for e in entries:
        prereq = f" | Prereq: {e['prerequisites']}" if e['prerequisites'] != "none" else ""
        lines.append(f"- {e['name']} [{e['category']}, {e['cost_tier']} cost{prereq}]: {e['purpose']}")
    return "\n".join(lines)


SKILL_TOOL_MAPPINGS: dict[str, list[str]] = {
    "spcas9_gene_cutting": [
        "spcas9_gene_cutting",
        "pam_scan",
        "compute_cut_site",
        "compute_gc_content",
        "check_homopolymer_runs",
        "compute_melting_temp",
        "compute_secondary_structure",
        "compute_positional_features",
        "compute_dinucleotide_composition",
        "compute_seed_gc",
        "predict_ontarget_efficiency",
        "offtarget_search",
        "score_offtargets",
        "rank_candidates",
    ],
    "offtarget_toxicity_risk": [
        "offtarget_toxicity_risk",
        "score_offtargets",
        "offtarget_search",
        "analyze_mismatch_seed",
    ],
    "model_calibration": [
        "model_calibration",
        "offtarget_toxicity_risk",
        "score_offtargets",
    ],
}


def select_active_tool_names(
    *,
    user_task: str | None = None,
    active_skill: str | None = None,
    input_class: str | None = None,
    explicit_tools: list[str] | None = None,
    catalog: ToolCatalog | None = None,
) -> list[str]:
    """Select the relevant subset of active full tool schemas based on task, skill, and inputs."""
    cat = catalog or get_tool_catalog()
    all_valid_names = set(cat.tools.keys())
    selected: set[str] = set()

    # 1. If explicit tools were provided
    if explicit_tools:
        for t in explicit_tools:
            if t in all_valid_names:
                selected.add(t)

    # 2. Skill-based selection
    if active_skill and active_skill in SKILL_TOOL_MAPPINGS:
        selected.update(SKILL_TOOL_MAPPINGS[active_skill])

    # 3. Input class selection
    if input_class == "calibration_input":
        selected.update(SKILL_TOOL_MAPPINGS["model_calibration"])
    elif input_class == "analysis_input":
        selected.update(SKILL_TOOL_MAPPINGS["spcas9_gene_cutting"])

    # 4. Task intent analysis (if not already covered)
    if user_task:
        lower_task = user_task.lower()
        if any(kw in lower_task for kw in ["calibrat", "train", "fitting", "r2", "r^2", "mse", "coefficient"]):
            selected.update(SKILL_TOOL_MAPPINGS["model_calibration"])
        if any(kw in lower_task for kw in ["toxic", "cfd", "off-target", "offtarget", "mismatch"]):
            selected.update(SKILL_TOOL_MAPPINGS["offtarget_toxicity_risk"])
        if any(kw in lower_task for kw in ["pam", "guide", "crispr", "target", "cas9", "cut", "gc", "tm", "homopolymer"]):
            selected.update(SKILL_TOOL_MAPPINGS["spcas9_gene_cutting"])

    # 5. Default fallback: if nothing specific triggered, supply the primary guide design & QC toolkit
    if not selected:
        selected.update(SKILL_TOOL_MAPPINGS["spcas9_gene_cutting"])

    # Ensure all selected names actually exist and preserve canonical ordering
    return [name for name in cat.tools.keys() if name in selected]


def get_active_tool_schemas(
    *,
    user_task: str | None = None,
    active_skill: str | None = None,
    input_class: str | None = None,
    explicit_tools: list[str] | None = None,
    catalog: ToolCatalog | None = None,
) -> list[dict[str, Any]]:
    """Return full native tool schemas for the active tool selection."""
    cat = catalog or get_tool_catalog()
    selected_names = select_active_tool_names(
        user_task=user_task,
        active_skill=active_skill,
        input_class=input_class,
        explicit_tools=explicit_tools,
        catalog=cat,
    )
    return cat.get_native_schemas(selected_names)


