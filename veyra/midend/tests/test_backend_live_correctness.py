"""Live backend and correctness verification test script for Freeze Gate."""

import sys
import math
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend_path))

from api import (
    compute_gc_content,
    check_homopolymer_runs,
    compute_melting_temp,
    compute_secondary_structure,
    compute_positional_features,
    compute_dinucleotide_composition,
    compute_seed_gc,
    compute_cut_site,
    pam_scan_raw,
    pam_scan_region,
    search_offtargets,
    score_offtargets_cfd,
    rank_guides,
    analyze_mismatch_seed,
    predict_ontarget_efficiency,
    get_genomes,
    get_genome_info,
)


def verify_all_backend_tools():
    print("=== STARTING BACKEND CORRECTNESS AND LIVE ENGINE TESTS ===")

    # 1. GC Content Correctness
    gc_50 = compute_gc_content("ATGC")
    assert gc_50.summary["gc_content"] == 0.5, f"Expected 0.5, got {gc_50.summary['gc_content']}"
    gc_100 = compute_gc_content("GGCC")
    assert gc_100.summary["gc_content"] == 1.0, f"Expected 1.0, got {gc_100.summary['gc_content']}"
    gc_0 = compute_gc_content("AATT")
    assert gc_0.summary["gc_content"] == 0.0, f"Expected 0.0, got {gc_0.summary['gc_content']}"
    print("✓ compute_gc_content correctness verified.")

    # 2. Homopolymer Runs
    homo = check_homopolymer_runs("ACGTTTTACGT", homopolymer_min_run=4)
    assert homo.summary["polyT_flag"] is True, "Expected poly-T run detected"
    assert homo.summary["polyG_flag"] is False, "Expected no poly-G run"
    assert homo.summary["passes_filter"] is False, "Expected filter failure"
    print("✓ check_homopolymer_runs verified.")

    # 3. Melting Temp
    tm = compute_melting_temp("GCGCGCGCGCGCGCGCGCGC")
    assert tm.summary["tm_celsius"] > 70.0, f"Expected Tm > 70, got {tm.summary['tm_celsius']}"
    print("✓ compute_melting_temp verified.")

    # 4. Secondary Structure (ViennaRNA)
    ss = compute_secondary_structure("GCGCGCGCGCGCGCGCGCGC", return_structure_string=True)
    assert ss.summary["mfe_kcal_mol"] < 0, f"Expected negative MFE, got {ss.summary['mfe_kcal_mol']}"
    assert "structure_string" in ss.summary, "Expected dot-bracket structure string"
    print("✓ compute_secondary_structure verified.")

    # 5. Positional Features
    pos = compute_positional_features("GCGCGCGCGCGCGCGCGCGG")
    assert pos.summary["position20_base"] == "G", f"Expected G at pos 20, got {pos.summary['position20_base']}"
    assert pos.summary["position20_bias_flag"] == "favored", f"Expected favored, got {pos.summary['position20_bias_flag']}"
    print("✓ compute_positional_features verified.")

    # 6. Dinucleotide Composition
    dinu = compute_dinucleotide_composition("GCGC", spacer_length=4)
    assert dinu.summary["counts"]["GC"] == 2
    assert dinu.summary["counts"]["CG"] == 1
    print("✓ compute_dinucleotide_composition verified.")

    # 7. Seed GC
    seed = compute_seed_gc("ATATATATATGCGCGCGCGC", seed_region_length=10, compute_seed_distal_delta=True)
    assert seed.summary["seed_gc_content"] == 1.0, f"Expected 1.0 seed GC, got {seed.summary['seed_gc_content']}"
    assert seed.summary["distal_gc_content"] == 0.0, f"Expected 0.0 distal GC, got {seed.summary['distal_gc_content']}"
    print("✓ compute_seed_gc verified.")

    # 8. Cut Site Coordinates
    # For SpCas9 on forward strand: 0-based spacer_start 100, spacer_len 20 -> cut site between relative 17-18 -> genomic coordinate 117
    cut_fwd = compute_cut_site(spacer_start=100, spacer_length=20, strand="+", pam_position="3prime", return_genomic_coord=True, chrom="chr1")
    assert cut_fwd.summary["cut_site_relative"] == 17, f"Expected 17, got {cut_fwd.summary['cut_site_relative']}"
    assert cut_fwd.summary["cut_site_genomic"] == 117, f"Expected 117, got {cut_fwd.summary['cut_site_genomic']}"

    # For SpCas9 on reverse strand: cut site is strand-reversed
    cut_rev = compute_cut_site(spacer_start=100, spacer_length=20, strand="-", pam_position="3prime", return_genomic_coord=True, chrom="chr1")
    assert cut_rev.summary["cut_site_relative"] == 17
    assert cut_rev.summary["cut_site_genomic"] == 103, f"Expected 103, got {cut_rev.summary['cut_site_genomic']}"
    print("✓ compute_cut_site coordinate arithmetic verified.")

    # 9. PAM Scanning
    # Test sequence: 20 nt spacer + TGG (forward) + spacer + CCA (reverse of TGG PAM)
    test_seq = "AAAAAAAAAAAAAAAAAAAATGG"  # 20 A's + TGG -> 1 site fwd
    pam_fwd = pam_scan_raw(test_seq, pam_pattern="NGG", protospacer_len=20, strand="both")
    assert len(pam_fwd.rows) == 1
    assert pam_fwd.rows[0].strand == "+"
    assert pam_fwd.rows[0].protospacer == "AAAAAAAAAAAAAAAAAAAA"
    assert pam_fwd.rows[0].pam == "TGG"
    assert pam_fwd.rows[0].start == 21  # 1-based start of PAM
    assert pam_fwd.rows[0].end == 24    # 1-based exclusive end of PAM

    # Reverse strand PAM
    test_seq_rev = "CCA" + "TTTTTTTTTTTTTTTTTTTT"  # CCA (rev PAM for TGG) + 20 T's (rev comp is 20 A's)
    pam_rev = pam_scan_raw(test_seq_rev, pam_pattern="NGG", protospacer_len=20, strand="both")
    assert len(pam_rev.rows) == 1
    assert pam_rev.rows[0].strand == "-"
    assert pam_rev.rows[0].protospacer == "AAAAAAAAAAAAAAAAAAAA"
    assert pam_rev.rows[0].pam == "TGG"
    print("✓ pam_scan strand, protospacer, and coordinate bounds verified.")

    # 10. Mismatch Seed Analysis
    mismatch_analysis = analyze_mismatch_seed(
        spacer_sequence="AAAAAAAAAAAAAAAAAAAA",
        candidate_sequence="AAAAAAAAAAAAAAAGAAAA",  # mismatch at pos 16 (PAM proximal, seed)
        seed_region_length=8
    )
    assert mismatch_analysis.summary["total_mismatches"] == 1
    assert mismatch_analysis.summary["seed_mismatch_count"] == 1
    assert mismatch_analysis.summary["distal_mismatch_count"] == 0
    print("✓ analyze_mismatch_seed verified.")

    # 11. CFD Scoring Correctness
    # Exact match must yield 1.0
    cfd_exact = score_offtargets_cfd(
        spacer_sequence="GAGTCCGAGCAGAAGAAGAA",
        candidates=[{
            "protospacer": "GAGTCCGAGCAGAAGAAGAA",
            "pam": "AGG",
            "mismatch_count": 0,
            "mismatch_positions": ""
        }]
    )
    assert cfd_exact.rows[0].cfd_score == 1.0, f"Expected 1.0, got {cfd_exact.rows[0].cfd_score}"

    # Single mismatch must reduce score below 1.0
    cfd_mismatch = score_offtargets_cfd(
        spacer_sequence="GAGTCCGAGCAGAAGAAGAA",
        candidates=[{
            "protospacer": "GAGTCCGAGCAGAAGAAGAT",  # pos 20 mismatch
            "pam": "AGG",
            "mismatch_count": 1,
            "mismatch_positions": "19"
        }]
    )
    assert 0.0 < cfd_mismatch.rows[0].cfd_score < 1.0, f"Expected (0, 1), got {cfd_mismatch.rows[0].cfd_score}"

    # Unsupported bulge handling
    cfd_bulge = score_offtargets_cfd(
        spacer_sequence="GAGTCCGAGCAGAAGAAGAA",
        candidates=[{
            "protospacer": None,
            "pam": "AGG",
            "bulge_type": "DNA",
            "bulge_size": 1
        }]
    )
    assert cfd_bulge.rows[0].cfd_score is None
    print("✓ score_offtargets_cfd exact match, mismatch penalty, and bulge handling verified.")

    # 12. On-Target Efficiency
    # 30-mer context for on-target prediction
    context_30 = "AAAAGAGTCCGAGCAGAAGAAGAAGGGTTT"
    ontarget_doench = predict_ontarget_efficiency(context_sequence=context_30, model="doench_2014")
    assert ontarget_doench.summary["ontarget_score"] is not None
    assert ontarget_doench.summary["model_used"] == "doench_2014"

    ontarget_auto = predict_ontarget_efficiency(context_sequence=context_30, model="auto")
    assert ontarget_auto.summary["ontarget_score"] is not None
    assert ontarget_auto.summary["model_used"] in {"doench_2014", "rule_set_3", "rule_set_2"}
    print("✓ predict_ontarget_efficiency explicit and auto selection verified.")

    # 13. Ranking Modes
    guide_list = [
        {"protospacer": "GUIDE_A", "cfd_score": 0.10, "rs2_score": 0.85},
        {"protospacer": "GUIDE_B", "cfd_score": 0.80, "rs2_score": 0.20},
        {"protospacer": "GUIDE_C", "cfd_score": 0.05, "rs2_score": 0.90},
    ]
    rank_res = rank_guides(
        guides=guide_list,
        on_target_scores={"GUIDE_A": 0.85, "GUIDE_B": 0.20, "GUIDE_C": 0.90},
        sort_by="composite"
    )
    assert len(rank_res.rows) == 3
    first_proto = rank_res.rows[0].protospacer if hasattr(rank_res.rows[0], "protospacer") else rank_res.rows[0]["protospacer"]
    assert first_proto == "GUIDE_C"
    print("✓ rank_candidates deterministic composite ordering verified.")

    # 14. Real E. Coli Off-Target Search (BWA & Cas-OFFinder)
    genomes = get_genomes()
    ecoli_registered = "ecoli_k12_mg1655" in genomes.summary.get("genome_ids", [])
    if ecoli_registered:
        bwa_search = search_offtargets(
            spacer_sequence="GATTGCCACCAAAGTGATGC",
            genome_id="ecoli_k12_mg1655",
            pam_pattern="NGG",
            max_mismatches=3,
            backend="bwa"
        )
        assert len(bwa_search.rows) >= 1, "Expected at least 1 hit in E. coli BWA search"

        cas_search = search_offtargets(
            spacer_sequence="GATTGCCACCAAAGTGATGC",
            genome_id="ecoli_k12_mg1655",
            pam_pattern="NGG",
            max_mismatches=3,
            allow_bulge=True,
            max_dna_bulge=1,
            max_rna_bulge=1,
            backend="cas_offinder"
        )
        assert len(cas_search.rows) >= 1, "Expected at least 1 hit in E. coli Cas-OFFinder search"
        print("✓ Real genome BWA and Cas-OFFinder off-target searches verified.")

    print("=== ALL BACKEND CORRECTNESS AND LIVE ENGINE TESTS PASSED ===")


if __name__ == "__main__":
    verify_all_backend_tools()
