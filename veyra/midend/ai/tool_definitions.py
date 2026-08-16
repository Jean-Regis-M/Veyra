"""Authoritative native tool definitions and parameter contracts for VEYRA AI models.

Source of truth: veyra/midend.md and backend canonical schemas.
Translates live VEYRA tools and skills into OpenAI-compatible tool definitions.
"""

from __future__ import annotations

import json
from typing import Any

# Authoritative default parameter values and units per tool contract in midend.md
AUTHORITATIVE_DEFAULTS: dict[str, dict[str, Any]] = {
    "pam_scan": {
        "pam_pattern": "NGG",
        "protospacer_len": 20,
        "strand": "both",
        "chrom": None,
    },
    "pam_scan_region": {
        "pam_pattern": "NGG",
        "protospacer_len": 20,
        "strand": "both",
    },
    "compute_cut_site": {
        "spacer_length": 20,
        "strand": "+",
        "pam_position": "3prime",
        "return_genomic_coord": False,
        "return_relative_coord": True,
        "chrom": "",
    },
    "compute_gc_content": {
        "gc_window_size": 5,
        "gc_split_ratio": 0.5,
        "gc_min_threshold": 0.2,
        "gc_max_threshold": 0.8,
        "include_sliding_window": True,
        "include_half_split": True,
    },
    "check_homopolymer_runs": {
        "homopolymer_min_run": 4,
        "polyT_strict": True,
        "polyG_strict": False,
        "check_bases": "ACGT",
        "return_run_positions": False,
    },
    "compute_melting_temp": {
        "tm_method": "nearest_neighbor",
        "na_conc": 50.0,
        "mg_conc": 0.0,
        "primer_conc": 250.0,
        "compute_seed_tm": False,
        "seed_region_length": 10,
    },
    "compute_secondary_structure": {
        "mfe_include_scaffold": False,
        "temperature_celsius": 37.0,
        "mfe_threshold": -30.0,
        "return_structure_string": True,
    },
    "compute_positional_features": {
        "spacer_length": 20,
        "check_position20_bias": True,
        "return_onehot": False,
        "onehot_alphabet": "ACGT",
    },
    "compute_dinucleotide_composition": {
        "spacer_length": 20,
        "window_size": 2,
        "return_full_matrix": False,
        "normalize_counts": False,
    },
    "compute_seed_gc": {
        "seed_region_length": 10,
        "seed_anchor": "pam_proximal",
        "seed_min_threshold": 0.2,
        "seed_max_threshold": 0.8,
        "compute_seed_distal_delta": False,
    },
    "offtarget_search": {
        "pam_pattern": "NGG",
        "max_mismatches": 4,
        "allow_bulge": False,
        "cas_variant": "SpCas9",
        "backend": "bwa",
        "max_dna_bulge": 0,
        "max_rna_bulge": 0,
        "search_scope": "genome",
        "strand_search": "both",
        "max_results": 1000,
    },
    "score_offtargets": {
        "pam_pattern": "NGG",
    },
    "rank_candidates": {
        "sort_by": "composite",
    },
    "analyze_mismatch_seed": {
        "seed_region_length": 10,
        "pam_pattern": "NGG",
    },
    "predict_ontarget_efficiency": {
        "model": "auto",
        "spacer_length": 20,
    },
    "spcas9_gene_cutting": {
        "depth": "quick",
        "strand": "both",
        "model": "auto",
        "max_candidates": 100,
        "max_mismatches": 4,
        "max_results": 1000,
    },
    "offtarget_toxicity_risk": {
        "max_mismatches": 4,
        "coefficient_model_id": "offtarget_toxicity_prototype",
    },
    "model_calibration": {
        "derive_features": True,
    },
}

PARAMETER_UNITS: dict[str, str] = {
    "protospacer_len": "nt",
    "spacer_length": "nt",
    "seed_region_length": "nt",
    "max_mismatches": "mismatches",
    "max_dna_bulge": "nt",
    "max_rna_bulge": "nt",
    "temperature_celsius": "°C",
    "tm_celsius": "°C",
    "na_conc": "mM",
    "mg_conc": "mM",
    "primer_conc": "nM",
    "gc_content": "ratio (0-1)",
    "mfe_kcal_mol": "kcal/mol",
}


def analyze_parameters_meta(tool_name: str, supplied_args: dict[str, Any]) -> dict[str, Any]:
    """Compare supplied arguments against authoritative defaults to track overrides."""
    defaults = AUTHORITATIVE_DEFAULTS.get(tool_name, {})
    meta: dict[str, Any] = {}

    all_keys = set(defaults.keys()).union(supplied_args.keys())
    for key in sorted(all_keys):
        default_val = defaults.get(key)
        has_default = key in defaults
        supplied_val = supplied_args.get(key)
        is_supplied = key in supplied_args

        if not is_supplied:
            # Default used
            meta[key] = {
                "value": default_val,
                "default": default_val,
                "status": "default",
                "units": PARAMETER_UNITS.get(key),
            }
        elif has_default and supplied_val == default_val:
            meta[key] = {
                "value": supplied_val,
                "default": default_val,
                "status": "default",
                "units": PARAMETER_UNITS.get(key),
            }
        elif has_default:
            meta[key] = {
                "value": supplied_val,
                "default": default_val,
                "status": "overridden",
                "units": PARAMETER_UNITS.get(key),
            }
        else:
            meta[key] = {
                "value": supplied_val,
                "default": None,
                "status": "supplied",
                "units": PARAMETER_UNITS.get(key),
            }

    return meta


NATIVE_TOOLS_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "pam_scan",
            "description": "Scan a DNA sequence for Protospacer Adjacent Motif (PAM) sites (SpCas9 NGG) and extract protospacers on forward/reverse strands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sequence": {
                        "type": "string",
                        "description": "Raw DNA sequence (IUPAC characters allowed)",
                    },
                    "pam_pattern": {
                        "type": "string",
                        "description": "IUPAC PAM motif pattern",
                        "default": "NGG",
                    },
                    "protospacer_len": {
                        "type": "integer",
                        "description": "Length of protospacer in nucleotides",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "strand": {
                        "type": "string",
                        "enum": ["both", "fwd", "rev"],
                        "default": "both",
                        "description": "Strand orientation to scan",
                    },
                    "chrom": {
                        "type": "string",
                        "description": "Optional chromosome/contig label",
                    },
                },
                "required": ["sequence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pam_scan_region",
            "description": "Scan a genomic region in a registered reference genome (e.g. 'ecoli_k12_mg1655') for PAM sites.",
            "parameters": {
                "type": "object",
                "properties": {
                    "genome_id": {"type": "string", "description": "Registered genome identifier"},
                    "chrom": {"type": "string", "description": "Chromosome or contig identifier"},
                    "start": {"type": "integer", "description": "1-based inclusive start coordinate", "minimum": 1},
                    "end": {"type": "integer", "description": "1-based exclusive end coordinate", "minimum": 1},
                    "pam_pattern": {"type": "string", "default": "NGG"},
                    "protospacer_len": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                    "strand": {"type": "string", "enum": ["both", "fwd", "rev"], "default": "both"},
                },
                "required": ["genome_id", "chrom", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_cut_site",
            "description": "Compute canonical SpCas9 double-strand break cleavage anchor coordinates (relative position 17|18 and genomic coordinates).",
            "parameters": {
                "type": "object",
                "properties": {
                    "spacer_start": {"type": "integer", "description": "0-based start position of spacer in reference"},
                    "spacer_length": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                    "strand": {"type": "string", "enum": ["+", "-"], "default": "+"},
                    "pam_position": {"type": "string", "default": "3prime"},
                    "return_genomic_coord": {"type": "boolean", "default": False},
                    "return_relative_coord": {"type": "boolean", "default": True},
                    "chrom": {"type": "string", "default": ""},
                },
                "required": ["spacer_start"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_gc_content",
            "description": "Calculate overall GC content, 5'/3' split ratio, and sliding window GC profiles for a DNA sequence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sequence": {"type": "string", "description": "DNA sequence"},
                    "gc_window_size": {"type": "integer", "default": 5},
                    "gc_split_ratio": {"type": "number", "default": 0.5},
                    "gc_min_threshold": {"type": "number", "default": 0.2},
                    "gc_max_threshold": {"type": "number", "default": 0.8},
                },
                "required": ["sequence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_homopolymer_runs",
            "description": "Scan a DNA sequence for poly-T (transcription termination signal) and poly-G homopolymer runs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sequence": {"type": "string", "description": "DNA sequence"},
                    "homopolymer_min_run": {"type": "integer", "default": 4, "minimum": 2},
                    "polyT_strict": {"type": "boolean", "default": True},
                    "polyG_strict": {"type": "boolean", "default": False},
                    "check_bases": {"type": "string", "default": "ACGT"},
                },
                "required": ["sequence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_melting_temp",
            "description": "Compute thermodynamic melting temperature (Tm) of a DNA oligo using nearest-neighbor thermodynamics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sequence": {"type": "string", "description": "DNA sequence"},
                    "tm_method": {"type": "string", "enum": ["nearest_neighbor", "wallace", "gc_percent"], "default": "nearest_neighbor"},
                    "na_conc": {"type": "number", "default": 50.0, "description": "Sodium concentration in mM"},
                    "mg_conc": {"type": "number", "default": 0.0, "description": "Magnesium concentration in mM"},
                    "primer_conc": {"type": "number", "default": 250.0, "description": "Oligo concentration in nM"},
                },
                "required": ["sequence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_secondary_structure",
            "description": "Predict RNA secondary structure and Minimum Free Energy (MFE) in kcal/mol via ViennaRNA folding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sequence": {"type": "string", "description": "Guide/spacer sequence"},
                    "scaffold_sequence": {"type": "string", "description": "Optional tracrRNA/scaffold sequence"},
                    "mfe_include_scaffold": {"type": "boolean", "default": False},
                    "temperature_celsius": {"type": "number", "default": 37.0},
                    "return_structure_string": {"type": "boolean", "default": True},
                },
                "required": ["sequence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_positional_features",
            "description": "Extract 1-based biological position features (e.g. favored G / disfavored T at position 20) and one-hot encoding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sequence": {"type": "string", "description": "20nt protospacer sequence"},
                    "check_position20_bias": {"type": "boolean", "default": True},
                },
                "required": ["sequence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_dinucleotide_composition",
            "description": "Compute dinucleotide counts and matrix frequencies across a spacer sequence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sequence": {"type": "string", "description": "DNA sequence"},
                    "spacer_length": {"type": "integer", "default": 20},
                    "window_size": {"type": "integer", "default": 2},
                },
                "required": ["sequence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_seed_gc",
            "description": "Calculate PAM-proximal seed GC content (positions 11-20) and seed-distal GC delta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sequence": {"type": "string", "description": "DNA sequence"},
                    "seed_region_length": {"type": "integer", "default": 10},
                    "seed_anchor": {"type": "string", "default": "pam_proximal"},
                    "compute_seed_distal_delta": {"type": "boolean", "default": False},
                },
                "required": ["sequence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "offtarget_search",
            "description": "Search a reference genome (e.g. 'ecoli_k12_mg1655') for off-target sequence matches using BWA or Cas-OFFinder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spacer_sequence": {"type": "string", "description": "15-30nt guide sequence"},
                    "genome_id": {"type": "string", "description": "Registered genome ID"},
                    "pam_pattern": {"type": "string", "default": "NGG"},
                    "max_mismatches": {"type": "integer", "default": 4, "minimum": 0, "maximum": 10},
                    "allow_bulge": {"type": "boolean", "default": False, "description": "Enable bulge search (requires backend='cas_offinder')"},
                    "backend": {"type": "string", "enum": ["bwa", "cas_offinder"], "default": "bwa"},
                    "max_dna_bulge": {"type": "integer", "default": 0, "minimum": 0, "maximum": 5},
                    "max_rna_bulge": {"type": "integer", "default": 0, "minimum": 0, "maximum": 5},
                    "strand_search": {"type": "string", "enum": ["both", "fwd", "rev"], "default": "both"},
                    "max_results": {"type": "integer", "default": 1000, "minimum": 1, "maximum": 100000},
                },
                "required": ["spacer_sequence", "genome_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_offtargets",
            "description": "Calculate CFD (Cutting Frequency Determination / Doench et al. 2016) specificity scores for off-target candidates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spacer_sequence": {"type": "string", "description": "Wild-type 20nt spacer sequence"},
                    "candidates": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Array of candidate off-target objects with protospacer and mismatch positions",
                    },
                    "pam_pattern": {"type": "string", "default": "NGG"},
                },
                "required": ["spacer_sequence", "candidates"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rank_candidates",
            "description": "Rank CRISPR guide candidates deterministically using composite score, on-target score, or specificity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "guides": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Array of candidate guide dictionaries",
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": ["composite", "offtarget_score", "ontarget_score", "gc_content"],
                        "default": "composite",
                    },
                    "on_target_scores": {
                        "type": "object",
                        "description": "Optional mapping of protospacer to on-target efficiency score",
                    },
                },
                "required": ["guides"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "predict_ontarget_efficiency",
            "description": "Predict on-target cleavage efficiency using Rule Set 3 (native activity) or Doench 2014 models.",
            "parameters": {
                "type": "object",
                "properties": {
                    "context_sequence": {
                        "type": "string",
                        "description": "30nt genomic context (4nt 5' flank + 20nt spacer + 3nt PAM + 3nt 3' flank)",
                    },
                    "model": {
                        "type": "string",
                        "enum": ["auto", "doench_2014", "rule_set_3", "rule_set_2"],
                        "default": "auto",
                    },
                },
                "required": ["context_sequence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spcas9_gene_cutting",
            "description": "High-level skill: complete SpCas9 guide discovery, cut sites, sequence QC features, on-target prediction, and candidate ranking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sequence": {"type": "string", "description": "Target DNA sequence to analyze"},
                    "input_id": {"type": "string", "description": "Optional input_id of uploaded FASTA/GenBank file"},
                    "analysis_scope": {"type": "string", "enum": ["quick", "full"], "default": "quick", "description": "Scope of analysis: 'quick' bounds large genome-scale files to first 25 kb; 'full' scans the entire sequence/genome without truncation."},
                    "depth": {"type": "string", "enum": ["quick", "full"], "default": "quick"},
                    "strand": {"type": "string", "enum": ["both", "fwd", "rev"], "default": "both"},
                    "genome_id": {"type": "string", "description": "Genome ID for full off-target search"},
                    "max_candidates": {"type": "integer", "default": 100, "minimum": 1, "maximum": 1000},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "offtarget_toxicity_risk",
            "description": "Audit and combine explicitly available off-target risk features (Sh, delta_g_binding, Ca) using audited logistic formula.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spacer_sequence": {"type": "string", "description": "15-30nt spacer sequence"},
                    "genome_id": {"type": "string", "description": "Optional genome ID for off-target search"},
                    "features": {"type": "object", "description": "Explicit scientific features { Sh, delta_g_binding, Ca }"},
                    "coefficients": {"type": "object", "description": "Manual coefficient weights { alpha, beta, gamma, epsilon }"},
                    "coefficient_model_id": {"type": "string", "default": "offtarget_toxicity_prototype"},
                },
                "required": ["spacer_sequence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "model_calibration",
            "description": "Deterministic experimental model calibration skill: fit model parameters on a validated CSV/TSV dataset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "calibration_input_id": {"type": "string", "description": "Validated calibration CSV/TSV dataset ID"},
                    "model_id": {"type": "string", "description": "Target model identifier"},
                    "target_column": {"type": "string", "description": "Column name for target label/toxicity"},
                    "guide_column": {"type": "string", "description": "Column name for guide sequence"},
                },
                "required": ["calibration_input_id"],
            },
        },
    },
]


def get_native_tools() -> list[dict[str, Any]]:
    """Return all native callable tool definitions."""
    return NATIVE_TOOLS_DEFINITIONS
