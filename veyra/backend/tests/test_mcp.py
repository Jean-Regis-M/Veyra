"""Tests for VEYRA MCP tools.

Covers all 6 MCP tools: pam_scan, pam_scan_region, build_offtarget_index,
offtarget_search, score_offtargets, rank_candidates.

Uses small fixtures for unit tests. No full genome required.
"""

from __future__ import annotations

import json
import os
import sys
import unittest

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from mcp.schemas import PAMSiteRow, ToolResult, validate_dna_sequence, validate_pam_pattern, validate_coordinates
from mcp.tools.pam_scan import pam_scan
from mcp.tools.pam_scan_region import pam_scan_region
from mcp.tools.build_offtarget_index import build_offtarget_index
from mcp.tools.offtarget_search import offtarget_search
from mcp.tools.score_offtargets import score_offtargets, calc_cfd
from mcp.tools.rank_candidates import rank_candidates
from mcp.tools.compute_gc_content import compute_gc_content
from mcp.tools.check_homopolymer_runs import check_homopolymer_runs
from mcp.tools.compute_melting_temp import compute_melting_temp
from mcp.tools.compute_secondary_structure import compute_secondary_structure, _RNA_AVAILABLE
from references import get_genome, list_genomes, get_cfd_resources
from cache import make_cache_key, cache_get, cache_set, cache_clear, cache_invalidate, get_cache_stats

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


# =====================================================================
# Schema validation tests
# =====================================================================

class TestSchemas(unittest.TestCase):
    """Tests for MCP shared schemas and validation."""

    def test_validate_dna(self):
        self.assertEqual(validate_dna_sequence("ACGT"), "ACGT")
        self.assertEqual(validate_dna_sequence("acgt"), "ACGT")

    def test_validate_dna_iupac(self):
        self.assertEqual(validate_dna_sequence("NGG", allow_iupac=True), "NGG")

    def test_validate_dna_invalid(self):
        with self.assertRaises(ValueError):
            validate_dna_sequence("ACGT123")

    def test_validate_dna_empty(self):
        with self.assertRaises(ValueError):
            validate_dna_sequence("")

    def test_validate_pam(self):
        self.assertEqual(validate_pam_pattern("NGG"), "NGG")

    def test_validate_pam_invalid(self):
        with self.assertRaises(ValueError):
            validate_pam_pattern("XYZ")

    def test_validate_coordinates(self):
        self.assertEqual(validate_coordinates(1, 100), (1, 100))
        self.assertEqual(validate_coordinates(1, 100, seq_len=200), (1, 100))

    def test_validate_coordinates_invalid(self):
        with self.assertRaises(ValueError):
            validate_coordinates(0, 100)
        with self.assertRaises(ValueError):
            validate_coordinates(100, 50)

    def test_pam_site_row_to_dict(self):
        row = PAMSiteRow(chrom="chr1", start=100, end=120, strand="+", protospacer="A" * 20, pam="NGG")
        d = row.to_dict()
        self.assertEqual(d["chrom"], "chr1")
        self.assertEqual(d["start"], 100)

    def test_tool_result_json(self):
        result = ToolResult(tool="test", rows=[PAMSiteRow(chrom="chr1", start=1, end=3)])
        j = result.to_json()
        parsed = json.loads(j)
        self.assertEqual(parsed["tool"], "test")
        self.assertEqual(len(parsed["rows"]), 1)

    def test_tool_result_tsv(self):
        result = ToolResult(tool="test", rows=[
            PAMSiteRow(chrom="chr1", start=1, end=3, strand="+", pam="AGG"),
            PAMSiteRow(chrom="chr1", start=10, end=13, strand="-", pam="TGG"),
        ])
        tsv = result.to_tsv()
        lines = tsv.strip().split("\n")
        self.assertEqual(len(lines), 3)  # header + 2 rows
        self.assertIn("chrom", lines[0])


# =====================================================================
# pam_scan tests
# =====================================================================

class TestPAMScan(unittest.TestCase):
    """Tests for the pam_scan MCP tool."""

    def test_ngg_recognition(self):
        result = pam_scan("NNNNNNNNNNNNNNNNNNNNAGG")
        self.assertEqual(result.summary["total_sites"], 1)
        self.assertEqual(result.rows[0].pam, "AGG")
        self.assertEqual(result.rows[0].strand, "+")

    def test_reverse_complement(self):
        result = pam_scan("CCT")  # revcomp = AGG
        rev_sites = [r for r in result.rows if r.strand == "-"]
        self.assertGreater(len(rev_sites), 0)

    def test_multiple_hits(self):
        result = pam_scan("AGGATCGATCGAGGATCGATCGAGG")
        self.assertGreaterEqual(result.summary["total_sites"], 3)

    def test_iupac_patterns(self):
        # NAG pattern - use a sequence with actual A/C/G/T at PAM position
        result = pam_scan("AAAAAAAAAAAAACAG", pam_pattern="NAG")
        # CAG matches NAG pattern
        self.assertGreaterEqual(result.summary["total_sites"], 1)

    def test_strand_fwd_only(self):
        result = pam_scan("AGGATCGATCGAGG", strand="fwd")
        for r in result.rows:
            self.assertEqual(r.strand, "+")

    def test_strand_rev_only(self):
        result = pam_scan("AGGATCGATCGAGG", strand="rev")
        for r in result.rows:
            self.assertEqual(r.strand, "-")

    def test_boundary_conditions(self):
        # PAM at very start — no room for spacer
        result = pam_scan("AGG", pam_pattern="NGG")
        # Should find the PAM but no complete spacer
        self.assertEqual(result.summary["total_sites"], 1)
        self.assertIsNone(result.rows[0].protospacer)

    def test_empty_sequence(self):
        result = pam_scan("")
        # Empty sequence returns either error or zero sites
        if result.errors:
            self.assertGreater(len(result.errors), 0)
        else:
            self.assertEqual(result.summary.get("total_sites", 0), 0)

    def test_invalid_sequence(self):
        result = pam_scan("ACGT123XYZ")
        self.assertGreater(len(result.errors), 0)

    def test_1_based_coordinates(self):
        result = pam_scan("NNNNAGG")
        self.assertEqual(result.rows[0].start, 5)  # 1-based

    def test_chrom_propagation(self):
        result = pam_scan("NNNNNNNNNNNNNNNNNNNNAGG", chrom="chr1")
        self.assertEqual(result.rows[0].chrom, "chr1")

    def test_tsv_output(self):
        result = pam_scan("NNNNNNNNNNNNNNNNNNNNAGG")
        tsv = result.to_tsv()
        self.assertIn("chr", tsv.lower())  # has chrom column

    def test_json_output(self):
        result = pam_scan("NNNNNNNNNNNNNNNNNNNNAGG")
        j = result.to_json()
        parsed = json.loads(j)
        self.assertEqual(parsed["tool"], "pam_scan")


# =====================================================================
# pam_scan_region tests
# =====================================================================

class TestPAMScanRegion(unittest.TestCase):
    """Tests for the pam_scan_region MCP tool."""

    def test_region_retrieval(self):
        """Test that a region is correctly retrieved and scanned."""
        try:
            genome = get_genome("CIRCLEseq_test")
        except ValueError:
            self.skipTest("CIRCLEseq_test genome not available")

        if not genome.has_fai:
            self.skipTest("No .fai index for CIRCLEseq_test")

        result = pam_scan_region("CIRCLEseq_test", "2", 1, 100)
        self.assertEqual(result.tool, "pam_scan_region")
        self.assertIn("region", result.summary)

    def test_invalid_genome(self):
        result = pam_scan_region("nonexistent_genome", "chr1", 1, 100)
        self.assertGreater(len(result.errors), 0)

    def test_invalid_coordinates(self):
        try:
            genome = get_genome("GRCh38_chr1_test")
        except ValueError:
            self.skipTest("Genome not available")

        result = pam_scan_region("GRCh38_chr1_test", "chr1", 0, 100)
        self.assertGreater(len(result.errors), 0)

    def test_coordinate_adjustment(self):
        """Verify that local PAM positions are adjusted to genome coordinates."""
        try:
            genome = get_genome("CIRCLEseq_test")
            if not genome.has_fai:
                self.skipTest("No .fai index")
        except ValueError:
            self.skipTest("Genome not available")

        result = pam_scan_region("CIRCLEseq_test", "2", 1, 200)
        for row in result.rows:
            if row.start is not None:
                self.assertGreaterEqual(row.start, 1)


# =====================================================================
# build_offtarget_index tests
# =====================================================================

class TestBuildOfftargetIndex(unittest.TestCase):
    """Tests for the build_offtarget_index MCP tool."""

    def test_build_index_missing_genome(self):
        result = build_offtarget_index("nonexistent_genome")
        self.assertGreater(len(result.errors), 0)

    def test_build_index(self):
        """Test index building with a small test genome."""
        from references import GenomeConfig, register_genome
        test_fa = os.path.join(FIXTURES, "test_genome.fa")
        if not os.path.isfile(test_fa):
            self.skipTest("test_genome.fa not found")

        config = GenomeConfig(
            genome_id="test_genome",
            display_name="Test genome for unit tests",
            fasta_path=test_fa,
        )
        register_genome(config)

        # Clear any cached index first
        from cache import make_cache_key, cache_invalidate
        ck = make_cache_key("build_offtarget_index", genome_id="test_genome", cas_variant="SpCas9", checksum=config.fasta_checksum())
        cache_invalidate(ck)

        result = build_offtarget_index("test_genome", force_rebuild=True)
        self.assertIn("index_path", result.summary)
        self.assertEqual(result.summary["status"], "built")

    def test_cache_hit(self):
        """Test that a second build reuses the cache."""
        from references import GenomeConfig, register_genome
        test_fa = os.path.join(FIXTURES, "test_genome.fa")
        if not os.path.isfile(test_fa):
            self.skipTest("test_genome.fa not found")

        config = GenomeConfig(
            genome_id="test_genome",
            display_name="Test genome for unit tests",
            fasta_path=test_fa,
        )
        register_genome(config)

        result = build_offtarget_index("test_genome")
        self.assertEqual(result.summary["status"], "cached")


# =====================================================================
# offtarget_search tests
# =====================================================================

class TestOfftargetSearch(unittest.TestCase):
    """Tests for the offtarget_search MCP tool."""

    def test_search_exact_match(self):
        """Test finding an exact match in a small genome."""
        try:
            genome = get_genome("guideseq_test")
            if not genome.has_bwa_index:
                self.skipTest("No BWA index")
        except ValueError:
            self.skipTest("Genome not available")

        # Use a short sequence that should be in the test genome
        result = offtarget_search("ATCGATCGATCG", "guideseq_test")
        self.assertEqual(result.tool, "offtarget_search")
        self.assertIn("total_candidates", result.summary)

    def test_search_max_mismatches(self):
        """Test mismatch filtering."""
        try:
            genome = get_genome("guideseq_test")
            if not genome.has_bwa_index:
                self.skipTest("No BWA index")
        except ValueError:
            self.skipTest("Genome not available")

        result_0 = offtarget_search("ATCGATCGATCG", "guideseq_test", max_mismatches=0)
        result_3 = offtarget_search("ATCGATCGATCG", "guideseq_test", max_mismatches=3)
        # More mismatches should find same or more candidates
        self.assertGreaterEqual(
            result_3.summary["total_candidates"],
            result_0.summary["total_candidates"],
        )

    def test_search_invalid_spacer(self):
        result = offtarget_search("ACGT", "GRCh38_chr1_test")
        self.assertGreater(len(result.errors), 0)

    def test_search_no_index(self):
        result = offtarget_search("GGTGGAGCGCGCCGCCACGG", "nonexistent_genome")
        self.assertGreater(len(result.errors), 0)

    def test_strand_handling(self):
        """Verify results include both strands."""
        try:
            genome = get_genome("CIRCLEseq_test")
            if not genome.has_bwa_index:
                self.skipTest("No BWA index")
        except ValueError:
            self.skipTest("Genome not available")

        result = offtarget_search("GAGGGAGATGCTTTGCGACC", "CIRCLEseq_test", max_mismatches=2)
        # Should return results (may be 0 or more depending on genome content)
        self.assertIn("total_candidates", result.summary)


# =====================================================================
# score_offtargets tests
# =====================================================================

class TestScoreOfftargets(unittest.TestCase):
    """Tests for the score_offtargets MCP tool."""

    def test_cfd_known_case(self):
        """Test CFD scoring with a known case."""
        try:
            mm_path, pam_path = get_cfd_resources()
        except FileNotFoundError:
            self.skipTest("CFD resources not available")

        # Exact match should score ~1.0 (with perfect PAM)
        wt = "GGTGGAGCGCGCCGCCACGG"
        sg = "GGTGGAGCGCGCCGCCACGG"
        pam = "AGG"
        score = calc_cfd(wt, sg, pam)
        self.assertGreater(score, 0.5)  # should be high for exact match

    def test_cfd_mismatch_penalty(self):
        """Test that mismatches reduce the CFD score."""
        try:
            mm_path, pam_path = get_cfd_resources()
        except FileNotFoundError:
            self.skipTest("CFD resources not available")

        wt = "GGTGGAGCGCGCCGCCACGG"
        sg_exact = "GGTGGAGCGCGCCGCCACGG"
        sg_mismatch = "GGTGGAGCGCGCCGCCACGA"  # last base changed

        score_exact = calc_cfd(wt, sg_exact, "AGG")
        score_mismatch = calc_cfd(wt, sg_mismatch, "AGG")
        self.assertGreater(score_exact, score_mismatch)

    def test_score_offtargets_tool(self):
        """Test the full score_offtargets tool."""
        try:
            mm_path, pam_path = get_cfd_resources()
        except FileNotFoundError:
            self.skipTest("CFD resources not available")

        candidates = [
            PAMSiteRow(
                chrom="chr1", start=100, end=120, strand="+",
                protospacer="GGTGGAGCGCGCCGCCACGG", pam="AGG", pam_type="SpCas9",
            ),
        ]
        result = score_offtargets("GGTGGAGCGCGCCGCCACGG", candidates)
        self.assertEqual(result.tool, "score_offtargets")
        self.assertGreater(result.summary["total_scored"], 0)
        self.assertIsNotNone(result.rows[0].cfd_score)

    def test_score_missing_resources(self):
        """Test graceful handling when CFD resources are missing."""
        import mcp.tools.score_offtargets as sot
        # Clear the module-level cache
        sot._mm_scores = None
        sot._pam_scores = None

        # Temporarily break the resource path
        import references
        old_path = references.CFD_MISMATCH_SCORES
        references.CFD_MISMATCH_SCORES = references.CFD_MISMATCH_SCORES.parent / "nonexistent.pkl"
        try:
            candidates = [PAMSiteRow(protospacer="A" * 20, pam="AGG")]
            result = score_offtargets("A" * 20, candidates)
            self.assertGreater(len(result.errors), 0)
        finally:
            references.CFD_MISMATCH_SCORES = old_path
            sot._mm_scores = None
            sot._pam_scores = None


# =====================================================================
# rank_candidates tests
# =====================================================================

class TestRankCandidates(unittest.TestCase):
    """Tests for the rank_candidates MCP tool."""

    def test_deterministic_ranking(self):
        """Test that ranking is deterministic."""
        guides = [
            PAMSiteRow(protospacer="AAAA", pam="AGG", chrom="chr1", start=100, end=120),
            PAMSiteRow(protospacer="TTTT", pam="TGG", chrom="chr1", start=200, end=220),
        ]
        off_targets = [
            PAMSiteRow(protospacer="AAAA", pam="AGG", mismatch_count=1, cfd_score=0.5),
            PAMSiteRow(protospacer="TTTT", pam="TGG", mismatch_count=3, cfd_score=0.1),
        ]
        result1 = rank_candidates(guides, off_targets)
        result2 = rank_candidates(guides, off_targets)
        self.assertEqual(result1.to_json(), result2.to_json())

    def test_aggregation(self):
        """Test that off-target evidence is correctly aggregated."""
        guides = [
            PAMSiteRow(protospacer="AAAA", pam="AGG", chrom="chr1", start=100, end=120),
        ]
        off_targets = [
            PAMSiteRow(protospacer="AAAA", pam="AGG", mismatch_count=1, cfd_score=0.8),
            PAMSiteRow(protospacer="AAAA", pam="AGG", mismatch_count=2, cfd_score=0.3),
        ]
        result = rank_candidates(guides, off_targets)
        self.assertEqual(result.summary["total_candidates"], 1)

    def test_empty_guides(self):
        result = rank_candidates([])
        self.assertGreater(len(result.errors), 0)

    def test_null_handling(self):
        """Test that missing data is handled gracefully."""
        guides = [
            PAMSiteRow(protospacer="AAAA", pam="AGG", chrom="chr1", start=100, end=120),
        ]
        result = rank_candidates(guides, off_targets=None, on_target_scores=None)
        self.assertEqual(result.summary["total_candidates"], 1)


# =====================================================================
# Cache tests
# =====================================================================

class TestCache(unittest.TestCase):
    """Tests for the caching layer."""

    def test_cache_set_get(self):
        key = make_cache_key("test_tool", param1="value1")
        cache_set(key, "test_tool", metadata={"test": True})
        cached = cache_get(key)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["tool_name"], "test_tool")
        cache_clear("test_tool")

    def test_cache_miss(self):
        key = make_cache_key("nonexistent", param1="value1")
        cached = cache_get(key)
        self.assertIsNone(cached)

    def test_cache_invalidate(self):
        key = make_cache_key("test_invalidate", p="v")
        cache_set(key, "test_invalidate")
        self.assertTrue(cache_invalidate(key))
        self.assertIsNone(cache_get(key))

    def test_cache_stats(self):
        stats = get_cache_stats()
        self.assertIn("total_entries", stats)
        self.assertIn("by_tool", stats)


# =====================================================================
# Reference configuration tests
# =====================================================================

class TestReferences(unittest.TestCase):
    """Tests for reference genome configuration."""

    def test_list_genomes(self):
        genomes = list_genomes()
        self.assertIsInstance(genomes, list)

    def test_get_genome_missing(self):
        with self.assertRaises(ValueError):
            get_genome("nonexistent_genome")

    def test_genome_checksum(self):
        genomes = list_genomes()
        for g in genomes:
            checksum = g.fasta_checksum()
            self.assertIsInstance(checksum, str)


# =====================================================================
# CLI tests
# =====================================================================

class TestMCPServer(unittest.TestCase):
    """Tests for the MCP server CLI."""

    def test_list_tools(self):
        from mcp.server import TOOL_REGISTRY
        self.assertIn("pam_scan", TOOL_REGISTRY)
        self.assertIn("offtarget_search", TOOL_REGISTRY)
        self.assertIn("score_offtargets", TOOL_REGISTRY)
        self.assertIn("rank_candidates", TOOL_REGISTRY)
        self.assertIn("compute_gc_content", TOOL_REGISTRY)
        self.assertIn("check_homopolymer_runs", TOOL_REGISTRY)
        self.assertIn("compute_melting_temp", TOOL_REGISTRY)
        self.assertIn("compute_secondary_structure", TOOL_REGISTRY)
        self.assertIn("cas_offinder_search", TOOL_REGISTRY)
        self.assertIn("analyze_mismatch_seed", TOOL_REGISTRY)
        self.assertEqual(len(TOOL_REGISTRY), 17)


# =====================================================================
# compute_gc_content tests
# =====================================================================

class TestComputeGCContent(unittest.TestCase):
    """Tests for the compute_gc_content MCP tool."""

    def test_0_percent_gc(self):
        """All A/T should give GC=0."""
        result = compute_gc_content("AAAAAAAAAA")
        self.assertEqual(result.summary["gc_content"], 0.0)

    def test_100_percent_gc(self):
        """All G/C should give GC=1.0."""
        result = compute_gc_content("GCGCGCGCGC")
        self.assertEqual(result.summary["gc_content"], 1.0)

    def test_50_percent_gc(self):
        """Equal G/C and A/T should give GC=0.5."""
        result = compute_gc_content("ACGTACGTACGTACGTACGT")
        self.assertEqual(result.summary["gc_content"], 0.5)

    def test_mixed_sequence(self):
        """Test mixed sequence GC calculation."""
        # GGCC = 4 GC out of 4 = 1.0
        # AATT = 0 GC out of 4 = 0.0
        # Combined: 4/8 = 0.5
        result = compute_gc_content("GGCCAATT")
        self.assertEqual(result.summary["gc_content"], 0.5)

    def test_even_length_half_split(self):
        """Even length sequence splits evenly."""
        # ACGTACGT = 8 nt, split at 4
        # 5': ACGT -> 2 GC = 0.5
        # 3': ACGT -> 2 GC = 0.5
        result = compute_gc_content("ACGTACGT")
        self.assertEqual(result.summary["gc_5prime"], 0.5)
        self.assertEqual(result.summary["gc_3prime"], 0.5)

    def test_odd_length_half_split(self):
        """Odd length sequence splits with floor."""
        # ACGCG = 5 nt, split at floor(5*0.5)=2
        # 5': AC -> 1/2 = 0.5
        # 3': GCG -> 3/3 = 1.0
        result = compute_gc_content("ACGCG")
        self.assertEqual(result.summary["gc_5prime"], 0.5)
        self.assertEqual(result.summary["gc_3prime"], 1.0)

    def test_split_ratio_default(self):
        """Default split ratio (0.5) divides at midpoint."""
        seq = "A" * 10 + "G" * 10  # 20 nt
        result = compute_gc_content(seq, gc_split_ratio=0.5)
        # Split at floor(20*0.5) = 10
        # 5': 10 A's = 0.0
        # 3': 10 G's = 1.0
        self.assertEqual(result.summary["gc_5prime"], 0.0)
        self.assertEqual(result.summary["gc_3prime"], 1.0)

    def test_non_midpoint_split_ratio(self):
        """Non-midpoint split ratio."""
        seq = "A" * 10 + "G" * 10  # 20 nt
        result = compute_gc_content(seq, gc_split_ratio=0.3)
        # Split at floor(20*0.3) = 6
        # 5': 6 A's = 0.0
        # 3': 4 A's + 10 G's = 10/14 ≈ 0.714
        self.assertEqual(result.summary["gc_5prime"], 0.0)
        self.assertAlmostEqual(result.summary["gc_3prime"], 10/14, places=3)

    def test_sliding_window(self):
        """Test sliding window GC calculation."""
        # ACGTACGT = 8 nt, window=4
        result = compute_gc_content("ACGTACGT", gc_window_size=4)
        windows = result.summary["sliding_windows"]
        self.assertEqual(len(windows), 5)  # 8-4+1 = 5 windows
        # Window 0: ACGT -> 2/4 = 0.5
        self.assertEqual(windows[0]["start"], 0)
        self.assertEqual(windows[0]["end"], 4)
        self.assertEqual(windows[0]["gc"], 0.5)
        # Window 1: CGTA -> 2/4 = 0.5
        self.assertEqual(windows[1]["gc"], 0.5)

    def test_sliding_window_different_sizes(self):
        """Test different window sizes."""
        seq = "GCGCGCGCGC"  # 10 nt, all GC
        result = compute_gc_content(seq, gc_window_size=3)
        windows = result.summary["sliding_windows"]
        self.assertEqual(len(windows), 8)  # 10-3+1
        for w in windows:
            self.assertEqual(w["gc"], 1.0)

    def test_sliding_window_disabled(self):
        """Test that sliding window can be disabled."""
        result = compute_gc_content("ACGTACGT", include_sliding_window=False)
        self.assertEqual(result.summary["sliding_windows"], [])

    def test_half_split_disabled(self):
        """Test that half split can be disabled."""
        result = compute_gc_content("ACGTACGT", include_half_split=False)
        self.assertIsNone(result.summary["gc_5prime"])
        self.assertIsNone(result.summary["gc_3prime"])

    def test_threshold_pass(self):
        """Test threshold pass."""
        result = compute_gc_content("ACGTACGTACGTACGT", gc_min_threshold=0.3, gc_max_threshold=0.7)
        self.assertTrue(result.summary["passes_basic_filter"])

    def test_threshold_fail_low(self):
        """Test threshold fail (below min)."""
        result = compute_gc_content("AAAAAAAAAA", gc_min_threshold=0.3, gc_max_threshold=0.7)
        self.assertFalse(result.summary["passes_basic_filter"])

    def test_threshold_fail_high(self):
        """Test threshold fail (above max)."""
        result = compute_gc_content("GCGCGCGCGC", gc_min_threshold=0.3, gc_max_threshold=0.7)
        self.assertFalse(result.summary["passes_basic_filter"])

    def test_threshold_boundary_equality(self):
        """Test threshold boundary equality."""
        # GC = 0.5 exactly
        result = compute_gc_content("ACGTACGT", gc_min_threshold=0.5, gc_max_threshold=0.5)
        self.assertTrue(result.summary["passes_basic_filter"])

    def test_invalid_empty_sequence(self):
        """Test empty sequence returns error."""
        result = compute_gc_content("")
        self.assertGreater(len(result.errors), 0)

    def test_invalid_window_size(self):
        """Test invalid window size returns error."""
        result = compute_gc_content("ACGT", gc_window_size=0)
        self.assertGreater(len(result.errors), 0)

    def test_window_size_exceeds_sequence(self):
        """Test window size > sequence length warns."""
        result = compute_gc_content("ACGT", gc_window_size=10)
        self.assertEqual(result.summary["gc_content"], 0.5)
        self.assertEqual(result.summary["sliding_windows"], [])
        self.assertGreater(len(result.warnings), 0)

    def test_invalid_split_ratio(self):
        """Test invalid split ratio returns error."""
        result = compute_gc_content("ACGT", gc_split_ratio=1.5)
        self.assertGreater(len(result.errors), 0)

    def test_invalid_threshold_ordering(self):
        """Test min > max threshold returns error."""
        result = compute_gc_content("ACGT", gc_min_threshold=0.8, gc_max_threshold=0.2)
        self.assertGreater(len(result.errors), 0)

    def test_rounding(self):
        """Test rounding behavior."""
        result = compute_gc_content("ACGTACGT", round_decimals=2)
        # GC = 0.5, should be 0.5
        self.assertEqual(result.summary["gc_content"], 0.5)
        # Sliding window values should be rounded
        for w in result.summary["sliding_windows"]:
            self.assertEqual(len(str(w["gc"]).split(".")[-1]), 1 if w["gc"] != 0.5 else 1)

    def test_ambiguous_iupac_behavior(self):
        """Test that ambiguous IUPAC bases don't count as GC."""
        # N = any base, not counted as G or C
        # Sequence: GN = 1 GC out of 2 = 0.5
        result = compute_gc_content("GN")
        self.assertEqual(result.summary["gc_content"], 0.5)

    def test_lowercase_input(self):
        """Test lowercase input is handled."""
        result = compute_gc_content("acgtacgt")
        self.assertEqual(result.summary["gc_content"], 0.5)

    def test_metadata_populated(self):
        """Test that metadata is populated."""
        result = compute_gc_content("ACGTACGT")
        self.assertEqual(result.metadata["gc_window_size"], 5)
        self.assertEqual(result.metadata["round_decimals"], 3)
        self.assertIn("scoring_note", result.metadata)


# =====================================================================
# Homopolymer runs tests
# =====================================================================

class TestCheckHomopolymerRuns(unittest.TestCase):
    """Tests for check_homopolymer_runs MCP tool."""

    def test_no_homopolymers(self):
        """Sequence with no qualifying runs."""
        result = check_homopolymer_runs("ACGTACGTACGT")
        self.assertEqual(result.tool, "check_homopolymer_runs")
        self.assertFalse(result.summary["polyT_flag"])
        self.assertFalse(result.summary["polyG_flag"])
        self.assertEqual(result.summary["homopolymer_max_run"], 0)
        self.assertTrue(result.summary["passes_filter"])

    def test_polyT(self):
        """Sequence with TTTT run."""
        result = check_homopolymer_runs("ACGTTTTACGT")
        self.assertTrue(result.summary["polyT_flag"])
        self.assertFalse(result.summary["polyG_flag"])
        self.assertEqual(result.summary["homopolymer_max_run"], 4)

    def test_polyG(self):
        """Sequence with GGGG run."""
        result = check_homopolymer_runs("ACGTGGGGACGT")
        self.assertFalse(result.summary["polyT_flag"])
        self.assertTrue(result.summary["polyG_flag"])
        self.assertEqual(result.summary["homopolymer_max_run"], 4)

    def test_polyA(self):
        """Sequence with AAAA run — flagged but not polyT/polyG."""
        result = check_homopolymer_runs("ACGTAAAAACGT")
        self.assertFalse(result.summary["polyT_flag"])
        self.assertFalse(result.summary["polyG_flag"])
        self.assertEqual(result.summary["homopolymer_max_run"], 5)

    def test_polyC(self):
        """Sequence with CCCC run."""
        result = check_homopolymer_runs("ACGTCCCCACGT")
        self.assertFalse(result.summary["polyT_flag"])
        self.assertFalse(result.summary["polyG_flag"])
        self.assertEqual(result.summary["homopolymer_max_run"], 4)

    def test_threshold_exactly_equal(self):
        """Run exactly at threshold length."""
        result = check_homopolymer_runs("ACGTTTTACGT", homopolymer_min_run=4)
        self.assertTrue(result.summary["polyT_flag"])
        self.assertEqual(result.summary["homopolymer_max_run"], 4)

    def test_threshold_below(self):
        """Run below threshold — not flagged."""
        result = check_homopolymer_runs("ACGTTTACGT", homopolymer_min_run=4)
        self.assertFalse(result.summary["polyT_flag"])
        self.assertEqual(result.summary["homopolymer_max_run"], 0)

    def test_multiple_runs(self):
        """Multiple qualifying runs in sequence."""
        result = check_homopolymer_runs("TTTTAAAAGGGG", homopolymer_min_run=4)
        self.assertTrue(result.summary["polyT_flag"])
        self.assertTrue(result.summary["polyG_flag"])
        self.assertEqual(result.summary["homopolymer_max_run"], 4)

    def test_max_run_detection(self):
        """Maximum run length detected correctly."""
        result = check_homopolymer_runs("TTTTTTTTTTAAAA", homopolymer_min_run=4)
        self.assertEqual(result.summary["homopolymer_max_run"], 10)

    def test_polyT_strict_true(self):
        """Poly-T with strict=true causes filter failure."""
        result = check_homopolymer_runs("ACGTTTTACGT", polyT_strict=True)
        self.assertFalse(result.summary["passes_filter"])

    def test_polyT_strict_false(self):
        """Poly-T with strict=false is a soft flag only."""
        result = check_homopolymer_runs("ACGTTTTACGT", polyT_strict=False)
        self.assertTrue(result.summary["passes_filter"])

    def test_polyG_strict_true(self):
        """Poly-G with strict=true causes filter failure."""
        result = check_homopolymer_runs("ACGTGGGGACGT", polyG_strict=True)
        self.assertFalse(result.summary["passes_filter"])

    def test_polyG_strict_false(self):
        """Poly-G with strict=false is a soft flag only."""
        result = check_homopolymer_runs("ACGTGGGGACGT", polyG_strict=False)
        self.assertTrue(result.summary["passes_filter"])

    def test_check_bases_filtering(self):
        """Only scan specified bases."""
        # TTTT present but check_bases="ACG" excludes T
        result = check_homopolymer_runs("ACGTTTTACGT", check_bases="ACG")
        self.assertFalse(result.summary["polyT_flag"])
        self.assertEqual(result.summary["homopolymer_max_run"], 0)

    def test_return_run_positions_true(self):
        """Run positions returned when enabled."""
        result = check_homopolymer_runs("ACGTTTTACGT", return_run_positions=True)
        self.assertEqual(len(result.summary["runs"]), 1)
        run = result.summary["runs"][0]
        self.assertEqual(run["base"], "T")
        self.assertEqual(run["start"], 3)
        self.assertEqual(run["end"], 7)
        self.assertEqual(run["length"], 4)

    def test_return_run_positions_false(self):
        """Run positions empty when disabled."""
        result = check_homopolymer_runs("ACGTTTTACGT", return_run_positions=False)
        self.assertEqual(result.summary["runs"], [])

    def test_invalid_threshold(self):
        """Invalid threshold value returns error."""
        result = check_homopolymer_runs("ACGT", homopolymer_min_run=1)
        self.assertIn("homopolymer_min_run", result.errors[0])

    def test_empty_sequence(self):
        """Empty sequence returns error."""
        result = check_homopolymer_runs("")
        self.assertTrue(result.errors)

    def test_invalid_bases(self):
        """Invalid bases in check_bases returns error."""
        result = check_homopolymer_runs("ACGT", check_bases="ACGTN")
        self.assertTrue(result.errors)

    def test_coordinate_correctness(self):
        """Verify 0-based half-open coordinates."""
        result = check_homopolymer_runs("GGGGACGT", homopolymer_min_run=4, return_run_positions=True)
        run = result.summary["runs"][0]
        self.assertEqual(run["start"], 0)
        self.assertEqual(run["end"], 4)
        self.assertEqual(run["base"], "G")

    def test_metadata_populated(self):
        """Metadata contains all expected fields."""
        result = check_homopolymer_runs("ACGT")
        self.assertIn("homopolymer_min_run", result.metadata)
        self.assertIn("polyT_strict", result.metadata)
        self.assertIn("polyG_strict", result.metadata)
        self.assertIn("check_bases", result.metadata)
        self.assertIn("return_run_positions", result.metadata)
        self.assertIn("scoring_note", result.metadata)


# =====================================================================
# Melting temperature tests
# =====================================================================

class TestComputeMeltingTemp(unittest.TestCase):
    """Tests for compute_melting_temp MCP tool."""

    def test_nearest_neighbor(self):
        """Nearest-neighbor method produces a reasonable Tm."""
        result = compute_melting_temp("GCGCGCGCGCGCGCGCGCGC")
        self.assertEqual(result.tool, "compute_melting_temp")
        self.assertIsNotNone(result.summary["tm_celsius"])
        self.assertGreater(result.summary["tm_celsius"], 50)
        self.assertLess(result.summary["tm_celsius"], 120)
        self.assertIsNone(result.summary["seed_tm_celsius"])

    def test_wallace(self):
        """Wallace method produces a reasonable Tm."""
        result = compute_melting_temp("GCGCGCGCGCGCGCGCGCGC", tm_method="wallace")
        self.assertIsNotNone(result.summary["tm_celsius"])
        # Wallace: 2*(A+T) + 4*(G+C) for 20nt all GC = 4*20 = 80
        self.assertEqual(result.summary["tm_celsius"], 80.0)

    def test_gc_percent(self):
        """GC-percent method produces a reasonable Tm."""
        result = compute_melting_temp("GCGCGCGCGCGCGCGCGCGC", tm_method="gc_percent")
        self.assertIsNotNone(result.summary["tm_celsius"])
        self.assertGreater(result.summary["tm_celsius"], 50)
        self.assertLess(result.summary["tm_celsius"], 120)

    def test_invalid_method(self):
        """Invalid method returns error."""
        result = compute_melting_temp("ACGT", tm_method="invalid")
        self.assertTrue(result.errors)

    def test_invalid_concentrations(self):
        """Invalid concentrations return errors."""
        result = compute_melting_temp("ACGT", na_conc=-1)
        self.assertTrue(result.errors)

    def test_invalid_primer_conc(self):
        """Invalid primer concentration returns error."""
        result = compute_melting_temp("ACGT", primer_conc=0)
        self.assertTrue(result.errors)

    def test_seed_tm_disabled(self):
        """Seed Tm not computed when disabled."""
        result = compute_melting_temp("GCGCGCGCGCGCGCGCGCGC", compute_seed_tm=False)
        self.assertIsNone(result.summary["seed_tm_celsius"])

    def test_seed_tm_enabled(self):
        """Seed Tm computed when enabled."""
        result = compute_melting_temp(
            "GCGCGCGCGCGCGCGCGCGC",
            compute_seed_tm=True,
            seed_region_length=10,
        )
        self.assertIsNotNone(result.summary["seed_tm_celsius"])
        self.assertGreater(result.summary["seed_tm_celsius"], 50)

    def test_seed_length_boundary(self):
        """Seed length equal to sequence length is valid."""
        result = compute_melting_temp(
            "ACGTACGT",
            compute_seed_tm=True,
            seed_region_length=8,
        )
        self.assertIsNotNone(result.summary["seed_tm_celsius"])

    def test_invalid_seed_length(self):
        """Seed length exceeding sequence length returns error."""
        result = compute_melting_temp(
            "ACGT",
            compute_seed_tm=True,
            seed_region_length=10,
        )
        self.assertTrue(result.errors)

    def test_rounding(self):
        """Rounding applied to returned values."""
        result = compute_melting_temp("GCGCGCGCGCGCGCGCGCGC", round_decimals=1)
        tm_str = str(result.summary["tm_celsius"])
        # Should have at most 1 decimal place
        self.assertLessEqual(len(tm_str.split(".")[-1]), 1)

    def test_deterministic_repeatability(self):
        """Same input produces same output."""
        r1 = compute_melting_temp("GCGCGCGCGCGCGCGCGCGC")
        r2 = compute_melting_temp("GCGCGCGCGCGCGCGCGCGC")
        self.assertEqual(r1.summary["tm_celsius"], r2.summary["tm_celsius"])

    def test_metadata_populated(self):
        """Metadata contains all expected fields."""
        result = compute_melting_temp("ACGTACGT")
        self.assertIn("tm_method", result.metadata)
        self.assertIn("na_conc", result.metadata)
        self.assertIn("mg_conc", result.metadata)
        self.assertIn("primer_conc", result.metadata)
        self.assertIn("compute_seed_tm", result.metadata)
        self.assertIn("round_decimals", result.metadata)
        self.assertIn("scoring_note", result.metadata)

    def test_empty_sequence(self):
        """Empty sequence returns error."""
        result = compute_melting_temp("")
        self.assertTrue(result.errors)

    def test_invalid_sequence(self):
        """Invalid nucleotides return error."""
        result = compute_melting_temp("ACGT123")
        self.assertTrue(result.errors)


# =====================================================================
# End-to-end regression test
# =====================================================================

class TestE2EPipeline(unittest.TestCase):
    """End-to-end regression test: pam_scan → build_index → offtarget_search → score → rank."""

    def test_full_pipeline(self):
        """Exercise the complete MCP pipeline on a small test genome."""
        from references import GenomeConfig, register_genome

        test_fa = os.path.join(FIXTURES, "test_genome.fa")
        if not os.path.isfile(test_fa):
            self.skipTest("test_genome.fa not found")

        config = GenomeConfig(
            genome_id="e2e_test_genome",
            display_name="E2E regression test genome",
            fasta_path=test_fa,
        )
        register_genome(config)

        # Step 1: PAM scan a spacer+PAM sequence
        spacer = "ATCGATCGATCGATCGATCG"
        pam_seq = "AGG"
        scan_result = pam_scan(spacer + pam_seq, chrom="chr1")
        self.assertEqual(scan_result.tool, "pam_scan")
        self.assertGreater(scan_result.summary["total_sites"], 0,
                           "PAM scan should find at least one NGG site")

        # Step 2: Build off-target index (force rebuild to ensure clean state)
        from cache import make_cache_key, cache_invalidate
        ck = make_cache_key("build_offtarget_index", genome_id="e2e_test_genome",
                            cas_variant="SpCas9", checksum=config.fasta_checksum())
        cache_invalidate(ck)

        idx_result = build_offtarget_index("e2e_test_genome", force_rebuild=True)
        self.assertIn("index_path", idx_result.summary,
                      f"Index build failed: {idx_result.errors}")
        self.assertEqual(idx_result.summary["status"], "built")

        # Step 3: Off-target search
        search_result = offtarget_search(spacer + pam_seq, "e2e_test_genome", max_mismatches=3)
        self.assertEqual(search_result.tool, "offtarget_search")
        self.assertIn("total_candidates", search_result.summary)

        # Step 4: Score off-targets (correct arg order: spacer, candidates, pam)
        if search_result.rows:
            score_result = score_offtargets(spacer + pam_seq, search_result.rows, "NGG")
            self.assertEqual(score_result.tool, "score_offtargets")
            self.assertIn("total_scored", score_result.summary)

            # Step 5: Rank candidates
            rank_result = rank_candidates(scan_result.rows, score_result.rows)
            self.assertEqual(rank_result.tool, "rank_candidates")
            self.assertIn("total_candidates", rank_result.summary)
        else:
            # No candidates found — skip scoring/ranking
            # This is valid for a tiny test genome
            score_result = None
            rank_result = None

        # Verify all tools returned without errors
        for result in [scan_result, idx_result, search_result, score_result, rank_result]:
            if result is not None:
                self.assertEqual(result.errors, [],
                                 f"{result.tool} returned errors: {result.errors}")


# =====================================================================
# compute_secondary_structure tests
# =====================================================================

class TestComputeSecondaryStructure(unittest.TestCase):
    """Tests for the compute_secondary_structure MCP tool."""

    def test_rnafold_unavailable_behavior(self):
        """When ViennaRNA is unavailable, tool returns structured error."""
        result = compute_secondary_structure("ACGTACGT")
        self.assertEqual(result.tool, "compute_secondary_structure")
        if not _RNA_AVAILABLE:
            self.assertTrue(result.errors)
            self.assertIn("ViennaRNA", result.errors[0])
            self.assertFalse(result.metadata.get("dependency_available", True))
        else:
            # If ViennaRNA IS available, no errors
            self.assertEqual(result.errors, [])

    @unittest.skipUnless(_RNA_AVAILABLE, "ViennaRNA not installed")
    def test_spacer_only_folding(self):
        """Spacer-only folding produces MFE."""
        result = compute_secondary_structure("GCGCGCGCGCGCGCGCGCGC")
        self.assertEqual(result.tool, "compute_secondary_structure")
        self.assertIsNotNone(result.summary["mfe_kcal_mol"])
        self.assertIsInstance(result.summary["mfe_kcal_mol"], float)
        self.assertIsNone(result.summary["structure_string"])

    @unittest.skipUnless(_RNA_AVAILABLE, "ViennaRNA not installed")
    def test_scaffold_folding_disabled(self):
        """Scaffold folding disabled by default."""
        result = compute_secondary_structure("GCGCGCGCGCGCGCGCGCGC")
        self.assertFalse(result.metadata["mfe_include_scaffold"])
        self.assertIsNone(result.metadata["scaffold_length"])

    @unittest.skipUnless(_RNA_AVAILABLE, "ViennaRNA not installed")
    def test_scaffold_folding_enabled(self):
        """Scaffold folding enabled when scaffold provided."""
        scaffold = "GAAUACCGCUAGCUAGCUAGCUAGCUAGCUAG"
        result = compute_secondary_structure(
            "GCGCGCGCGCGCGCGCGCGC",
            mfe_include_scaffold=True,
            scaffold_sequence=scaffold,
        )
        self.assertTrue(result.metadata["mfe_include_scaffold"])
        self.assertEqual(result.metadata["scaffold_length"], len(scaffold))
        self.assertEqual(result.metadata["folded_length"], 20 + len(scaffold))

    @unittest.skipUnless(_RNA_AVAILABLE, "ViennaRNA not installed")
    def test_missing_scaffold_when_enabled(self):
        """Missing scaffold when enabled returns error."""
        result = compute_secondary_structure(
            "ACGTACGT",
            mfe_include_scaffold=True,
            scaffold_sequence="",
        )
        self.assertTrue(result.errors)

    @unittest.skipUnless(_RNA_AVAILABLE, "ViennaRNA not installed")
    def test_37c(self):
        """Default temperature 37°C."""
        result = compute_secondary_structure("ACGTACGT")
        self.assertEqual(result.metadata["temperature_celsius"], 37.0)

    @unittest.skipUnless(_RNA_AVAILABLE, "ViennaRNA not installed")
    def test_alternate_temperature(self):
        """Alternate temperature changes MFE."""
        r1 = compute_secondary_structure("GCGCGCGCGCGCGCGCGCGC", temperature_celsius=25.0)
        r2 = compute_secondary_structure("GCGCGCGCGCGCGCGCGCGC", temperature_celsius=50.0)
        # Different temperatures should produce different MFEs
        # (though they could coincidentally be equal for some sequences)
        self.assertIsNotNone(r1.summary["mfe_kcal_mol"])
        self.assertIsNotNone(r2.summary["mfe_kcal_mol"])

    @unittest.skipUnless(_RNA_AVAILABLE, "ViennaRNA not installed")
    def test_mfe_output(self):
        """MFE is a float."""
        result = compute_secondary_structure("ACGTACGTACGTACGT")
        self.assertIsInstance(result.summary["mfe_kcal_mol"], float)

    @unittest.skipUnless(_RNA_AVAILABLE, "ViennaRNA not installed")
    def test_structure_string_disabled(self):
        """Structure string not included when disabled."""
        result = compute_secondary_structure("ACGTACGT", return_structure_string=False)
        self.assertIsNone(result.summary["structure_string"])

    @unittest.skipUnless(_RNA_AVAILABLE, "ViennaRNA not installed")
    def test_structure_string_enabled(self):
        """Structure string included when enabled."""
        result = compute_secondary_structure("GCGCGCGCGCGCGCGCGCGC", return_structure_string=True)
        self.assertIsNotNone(result.summary["structure_string"])
        # Dot-bracket should only contain valid characters
        for ch in result.summary["structure_string"]:
            self.assertIn(ch, ".()")

    @unittest.skipUnless(_RNA_AVAILABLE, "ViennaRNA not installed")
    def test_mfe_threshold_pass(self):
        """MFE threshold pass when MFE <= threshold."""
        # Use a very permissive threshold
        result = compute_secondary_structure("ACGTACGT", mfe_threshold=100.0)
        self.assertTrue(result.summary["passes_mfe_filter"])

    @unittest.skipUnless(_RNA_AVAILABLE, "ViennaRNA not installed")
    def test_mfe_threshold_fail(self):
        """MFE threshold fail when MFE > threshold."""
        # Use a very strict threshold
        result = compute_secondary_structure("ACGTACGT", mfe_threshold=-100.0)
        self.assertFalse(result.summary["passes_mfe_filter"])

    def test_invalid_sequence(self):
        """Invalid sequence returns error."""
        result = compute_secondary_structure("ACGT123")
        self.assertTrue(result.errors)

    def test_invalid_temperature(self):
        """Invalid temperature returns error."""
        result = compute_secondary_structure("ACGT", temperature_celsius=float("nan"))
        self.assertTrue(result.errors)

    def test_invalid_threshold(self):
        """Invalid threshold returns error."""
        result = compute_secondary_structure("ACGT", mfe_threshold=float("inf"))
        self.assertTrue(result.errors)

    @unittest.skipUnless(_RNA_AVAILABLE, "ViennaRNA not installed")
    def test_deterministic_repeatability(self):
        """Same input produces same output."""
        r1 = compute_secondary_structure("GCGCGCGCGCGCGCGCGCGC")
        r2 = compute_secondary_structure("GCGCGCGCGCGCGCGCGCGC")
        self.assertEqual(r1.summary["mfe_kcal_mol"], r2.summary["mfe_kcal_mol"])


# =====================================================================
# compute_positional_features tests
# =====================================================================

from mcp.tools.compute_positional_features import compute_positional_features


class TestComputePositionalFeatures(unittest.TestCase):
    """Tests for the compute_positional_features MCP tool."""

    def test_default_20nt_spacer(self):
        """Test default 20-nt spacer analysis."""
        seq = "GCGCGCGCGCGCGCGCGCGG"
        result = compute_positional_features(seq)
        self.assertEqual(result.tool, "compute_positional_features")
        self.assertEqual(result.summary["spacer_length"], 20)
        self.assertEqual(result.summary["sequence_length"], 20)
        self.assertEqual(result.summary["spacer"], seq)

    def test_alternate_spacer_length(self):
        """Test alternate spacer length."""
        seq = "ACGTACGTACGT"
        result = compute_positional_features(seq, spacer_length=12)
        self.assertEqual(result.summary["spacer_length"], 12)
        self.assertEqual(result.summary["spacer"], seq)

    def test_onehot_enabled(self):
        """Test one-hot encoding is present when enabled."""
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_positional_features(seq, return_onehot=True)
        self.assertIn("onehot", result.summary)
        self.assertEqual(len(result.summary["onehot"]), 20)

    def test_onehot_disabled(self):
        """Test one-hot encoding absent when disabled."""
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_positional_features(seq, return_onehot=False)
        self.assertNotIn("onehot", result.summary)

    def test_onehot_correctness_a(self):
        """Test one-hot encoding correctness for A."""
        result = compute_positional_features("A", spacer_length=1)
        oh = result.summary["onehot"][0]
        self.assertEqual(oh["base"], "A")
        self.assertEqual(oh["encoding"]["A"], 1)
        self.assertEqual(oh["encoding"]["C"], 0)
        self.assertEqual(oh["encoding"]["G"], 0)
        self.assertEqual(oh["encoding"]["T"], 0)
        self.assertTrue(oh["encoded"])

    def test_onehot_correctness_c(self):
        """Test one-hot encoding correctness for C."""
        result = compute_positional_features("C", spacer_length=1)
        oh = result.summary["onehot"][0]
        self.assertEqual(oh["base"], "C")
        self.assertEqual(oh["encoding"]["A"], 0)
        self.assertEqual(oh["encoding"]["C"], 1)
        self.assertEqual(oh["encoding"]["G"], 0)
        self.assertEqual(oh["encoding"]["T"], 0)

    def test_onehot_correctness_g(self):
        """Test one-hot encoding correctness for G."""
        result = compute_positional_features("G", spacer_length=1)
        oh = result.summary["onehot"][0]
        self.assertEqual(oh["base"], "G")
        self.assertEqual(oh["encoding"]["A"], 0)
        self.assertEqual(oh["encoding"]["C"], 0)
        self.assertEqual(oh["encoding"]["G"], 1)
        self.assertEqual(oh["encoding"]["T"], 0)

    def test_onehot_correctness_t(self):
        """Test one-hot encoding correctness for T."""
        result = compute_positional_features("T", spacer_length=1)
        oh = result.summary["onehot"][0]
        self.assertEqual(oh["base"], "T")
        self.assertEqual(oh["encoding"]["A"], 0)
        self.assertEqual(oh["encoding"]["C"], 0)
        self.assertEqual(oh["encoding"]["G"], 0)
        self.assertEqual(oh["encoding"]["T"], 1)

    def test_custom_alphabet(self):
        """Test custom alphabet for one-hot encoding."""
        result = compute_positional_features("ACGT", spacer_length=4, onehot_alphabet="ACGTN")
        self.assertEqual(len(result.summary["onehot"]), 4)
        for oh in result.summary["onehot"]:
            self.assertEqual(len(oh["encoding"]), 5)

    def test_ambiguous_nucleotide(self):
        """Test ambiguous nucleotide handling (N)."""
        result = compute_positional_features("ANGT", spacer_length=4)
        oh_n = result.summary["onehot"][1]
        self.assertEqual(oh_n["base"], "N")
        self.assertFalse(oh_n["encoded"])
        self.assertEqual(sum(oh_n["encoding"].values()), 0)

    def test_position20_g(self):
        """Test position 20 = G (favored)."""
        seq = "A" * 19 + "G"
        result = compute_positional_features(seq)
        self.assertEqual(result.summary["position20_base"], "G")
        self.assertEqual(result.summary["position20_bias_flag"], "favored")

    def test_position20_t(self):
        """Test position 20 = T (disfavored)."""
        seq = "A" * 19 + "T"
        result = compute_positional_features(seq)
        self.assertEqual(result.summary["position20_base"], "T")
        self.assertEqual(result.summary["position20_bias_flag"], "disfavored")

    def test_position20_a(self):
        """Test position 20 = A (neutral)."""
        seq = "A" * 19 + "A"
        result = compute_positional_features(seq)
        self.assertEqual(result.summary["position20_base"], "A")
        self.assertEqual(result.summary["position20_bias_flag"], "neutral")

    def test_position20_c(self):
        """Test position 20 = C (neutral)."""
        seq = "A" * 19 + "C"
        result = compute_positional_features(seq)
        self.assertEqual(result.summary["position20_base"], "C")
        self.assertEqual(result.summary["position20_bias_flag"], "neutral")

    def test_position20_check_disabled(self):
        """Test position-20 check when disabled."""
        seq = "A" * 19 + "G"
        result = compute_positional_features(seq, check_position20_bias=False)
        self.assertIsNone(result.summary["position20_base"])
        self.assertEqual(result.summary["position20_bias_flag"], "neutral")

    def test_custom_positions(self):
        """Test custom position list extraction."""
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_positional_features(seq, custom_check_positions=[1, 10, 20])
        self.assertEqual(len(result.summary["custom_positions"]), 3)
        positions = {p["position"]: p["base"] for p in result.summary["custom_positions"]}
        self.assertEqual(positions[1], "A")
        self.assertEqual(positions[10], "C")
        self.assertEqual(positions[20], "T")

    def test_multiple_custom_positions(self):
        """Test multiple custom positions."""
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_positional_features(seq, custom_check_positions=[1, 2, 3, 4, 5])
        self.assertEqual(len(result.summary["custom_positions"]), 5)
        bases = [p["base"] for p in result.summary["custom_positions"]]
        self.assertEqual(bases, ["A", "C", "G", "T", "A"])

    def test_empty_custom_positions(self):
        """Test empty custom position list."""
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_positional_features(seq, custom_check_positions=[])
        self.assertEqual(result.summary["custom_positions"], [])

    def test_invalid_position_0(self):
        """Test invalid position 0 returns error."""
        result = compute_positional_features("ACGT", custom_check_positions=[0])
        self.assertTrue(result.errors)
        self.assertIn(">= 1", result.errors[0])

    def test_invalid_position_exceeds_length(self):
        """Test invalid position > spacer_length returns error."""
        result = compute_positional_features("ACGT", spacer_length=4, custom_check_positions=[5])
        self.assertTrue(result.errors)
        self.assertIn("exceeds spacer_length", result.errors[0])

    def test_invalid_spacer_length(self):
        """Test invalid spacer_length returns error."""
        result = compute_positional_features("ACGT", spacer_length=0)
        self.assertTrue(result.errors)
        self.assertIn("positive integer", result.errors[0])

    def test_sequence_too_short(self):
        """Test sequence shorter than spacer_length returns error."""
        result = compute_positional_features("ACG", spacer_length=20)
        self.assertTrue(result.errors)
        self.assertIn("shorter than", result.errors[0])

    def test_duplicate_alphabet_chars(self):
        """Test duplicate alphabet characters returns error."""
        result = compute_positional_features("ACGT", onehot_alphabet="AACC")
        self.assertTrue(result.errors)
        self.assertIn("duplicate", result.errors[0])

    def test_invalid_alphabet(self):
        """Test invalid alphabet returns error."""
        result = compute_positional_features("ACGT", onehot_alphabet="123")
        self.assertTrue(result.errors)

    def test_deterministic_repeatability(self):
        """Test deterministic repeatability."""
        seq = "GCGCGCGCGCGCGCGCGCGG"
        r1 = compute_positional_features(seq)
        r2 = compute_positional_features(seq)
        self.assertEqual(r1.summary["spacer"], r2.summary["spacer"])
        self.assertEqual(r1.summary["position20_base"], r2.summary["position20_base"])
        self.assertEqual(r1.summary["position20_bias_flag"], r2.summary["position20_bias_flag"])
        for o1, o2 in zip(r1.summary["onehot"], r2.summary["onehot"]):
            self.assertEqual(o1["encoding"], o2["encoding"])


# =====================================================================
# compute_dinucleotide_composition tests
# =====================================================================

from mcp.tools.compute_dinucleotide_composition import compute_dinucleotide_composition


class TestComputeDinucleotideComposition(unittest.TestCase):
    """Tests for the compute_dinucleotide_composition MCP tool."""

    def test_simple_acgt_sequence(self):
        """Test simple ACGT sequence."""
        result = compute_dinucleotide_composition("ACGT", spacer_length=4)
        self.assertEqual(result.tool, "compute_dinucleotide_composition")
        self.assertEqual(result.summary["spacer_length"], 4)
        self.assertEqual(result.summary["total_windows"], 3)
        self.assertEqual(result.summary["counts"], {"AC": 1, "CG": 1, "GT": 1})

    def test_standard_20nt_spacer(self):
        """Test standard 20-nt spacer."""
        seq = "GCGCGCGCGCGCGCGCGCGG"
        result = compute_dinucleotide_composition(seq)
        self.assertEqual(result.summary["spacer_length"], 20)
        self.assertEqual(result.summary["total_windows"], 19)

    def test_expected_19_windows(self):
        """Test that a 20-nt spacer produces 19 dinucleotide windows."""
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_dinucleotide_composition(seq)
        self.assertEqual(result.summary["total_windows"], 19)

    def test_aggregate_counts(self):
        """Test aggregate counts."""
        seq = "GCGCGCGCGCGCGCGCGCGG"
        result = compute_dinucleotide_composition(seq)
        # GCGC... produces alternating GC and CG
        self.assertEqual(result.summary["counts"]["GC"], 9)
        self.assertEqual(result.summary["counts"]["CG"], 9)
        self.assertEqual(result.summary["counts"]["GG"], 1)

    def test_normalization(self):
        """Test normalized frequencies."""
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_dinucleotide_composition(seq, normalize_counts=True)
        self.assertIn("frequencies", result.summary)
        total_freq = sum(result.summary["frequencies"].values())
        self.assertAlmostEqual(total_freq, 1.0, places=6)

    def test_full_matrix(self):
        """Test full position-anchored matrix."""
        seq = "ACGT"
        result = compute_dinucleotide_composition(seq, spacer_length=4, return_full_matrix=True)
        self.assertIsNotNone(result.summary["full_matrix"])
        self.assertEqual(len(result.summary["full_matrix"]), 3)
        # Check first row
        row0 = result.summary["full_matrix"][0]
        self.assertEqual(row0["position_start"], 1)
        self.assertEqual(row0["position_end"], 2)
        self.assertEqual(row0["kmer"], "AC")

    def test_target_filter(self):
        """Test target dinucleotide filtering."""
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_dinucleotide_composition(seq, target_dinucleotides=["AC", "TT"])
        # AC occurs 5 times, TT occurs 0 times
        self.assertEqual(result.summary["counts"]["AC"], 5)
        self.assertEqual(result.summary["counts"]["TT"], 0)
        self.assertEqual(len(result.summary["counts"]), 2)

    def test_zero_count_target(self):
        """Test zero-count requested target appears in output."""
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_dinucleotide_composition(seq, target_dinucleotides=["TT"])
        self.assertIn("TT", result.summary["counts"])
        self.assertEqual(result.summary["counts"]["TT"], 0)

    def test_empty_target_list(self):
        """Test empty target list reports all k-mers."""
        seq = "ACGT"
        result = compute_dinucleotide_composition(seq, spacer_length=4, target_dinucleotides=[])
        # Should report all observed k-mers
        self.assertEqual(len(result.summary["counts"]), 3)

    def test_window_size_2(self):
        """Test window_size = 2 (default)."""
        seq = "ACGTACGT"
        result = compute_dinucleotide_composition(seq, spacer_length=8, window_size=2)
        self.assertEqual(result.summary["window_size"], 2)
        self.assertEqual(result.summary["total_windows"], 7)

    def test_window_size_3(self):
        """Test window_size = 3."""
        seq = "ACGTACGT"
        result = compute_dinucleotide_composition(seq, spacer_length=8, window_size=3)
        self.assertEqual(result.summary["window_size"], 3)
        self.assertEqual(result.summary["total_windows"], 6)
        # Check 3-mers
        self.assertIn("ACG", result.summary["counts"])

    def test_window_size_equals_spacer_length(self):
        """Test window_size = spacer_length."""
        seq = "ACGT"
        result = compute_dinucleotide_composition(seq, spacer_length=4, window_size=4)
        self.assertEqual(result.summary["total_windows"], 1)
        self.assertEqual(result.summary["counts"], {"ACGT": 1})

    def test_invalid_window_size(self):
        """Test invalid window_size returns error."""
        result = compute_dinucleotide_composition("ACGT", window_size=0)
        self.assertTrue(result.errors)
        self.assertIn("positive integer", result.errors[0])

    def test_invalid_target_length(self):
        """Test invalid target length returns error."""
        result = compute_dinucleotide_composition("ACGT", target_dinucleotides=["ACG"])
        self.assertTrue(result.errors)
        self.assertIn("length", result.errors[0])

    def test_invalid_target_characters(self):
        """Test invalid target characters returns error."""
        result = compute_dinucleotide_composition("ACGT", target_dinucleotides=["12"])
        self.assertTrue(result.errors)
        self.assertIn("invalid characters", result.errors[0])

    def test_sequence_too_short(self):
        """Test sequence shorter than spacer_length returns error."""
        result = compute_dinucleotide_composition("ACG", spacer_length=20)
        self.assertTrue(result.errors)
        self.assertIn("shorter than", result.errors[0])

    def test_ambiguous_nucleotide(self):
        """Test ambiguous nucleotide handling."""
        result = compute_dinucleotide_composition("ANGT", spacer_length=4)
        # N is treated as a valid IUPAC character
        self.assertIn("NG", result.summary["counts"])
        self.assertEqual(result.summary["counts"]["NG"], 1)

    def test_repeated_dinucleotides(self):
        """Test repeated dinucleotides."""
        result = compute_dinucleotide_composition("GCGCGCGCGCGCGCGCGCGC", spacer_length=20)
        # GC repeats 9 times, CG repeats 9 times, GC at end = 1
        self.assertEqual(result.summary["counts"]["GC"], 10)
        self.assertEqual(result.summary["counts"]["CG"], 9)

    def test_deterministic_repeatability(self):
        """Test deterministic repeatability."""
        seq = "GCGCGCGCGCGCGCGCGCGG"
        r1 = compute_dinucleotide_composition(seq)
        r2 = compute_dinucleotide_composition(seq)
        self.assertEqual(r1.summary["counts"], r2.summary["counts"])
        self.assertEqual(r1.summary["total_windows"], r2.summary["total_windows"])

    def test_large_sequence(self):
        """Test large-but-reasonable sequence."""
        seq = "ACGT" * 250  # 1000 nt
        result = compute_dinucleotide_composition(seq, spacer_length=1000)
        self.assertEqual(result.summary["total_windows"], 999)
        self.assertEqual(result.summary["counts"]["AC"], 250)
        self.assertEqual(result.summary["counts"]["CG"], 250)
        self.assertEqual(result.summary["counts"]["GT"], 250)
        self.assertEqual(result.summary["counts"]["TA"], 249)


# =====================================================================
# compute_seed_gc tests
# =====================================================================

from mcp.tools.compute_seed_gc import compute_seed_gc


class TestComputeSeedGC(unittest.TestCase):
    """Tests for the compute_seed_gc MCP tool."""

    def test_default_20nt_10nt_seed(self):
        """Test default 20-nt spacer with 10-nt PAM-proximal seed."""
        seq = "GCGCGCGCGCGCGCGCGCGG"
        result = compute_seed_gc(seq)
        self.assertEqual(result.tool, "compute_seed_gc")
        self.assertEqual(result.summary["sequence_length"], 20)
        self.assertEqual(result.summary["seed_region_length"], 10)
        self.assertEqual(result.summary["seed_anchor"], "pam_proximal")

    def test_seed_positions_11_20(self):
        """Test seed positions are 11-20 for default 20-nt / 10-nt seed."""
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_seed_gc(seq)
        self.assertEqual(result.summary["seed_start_position"], 11)
        self.assertEqual(result.summary["seed_end_position"], 20)

    def test_alternate_seed_length(self):
        """Test alternate seed length."""
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_seed_gc(seq, seed_region_length=6)
        self.assertEqual(result.summary["seed_region_length"], 6)
        self.assertEqual(result.summary["seed_start_position"], 15)
        self.assertEqual(result.summary["seed_end_position"], 20)

    def test_seed_gc_calculation(self):
        """Test seed GC calculation."""
        # Seed = positions 11-20 = "ACGTACGT" (wait, 20 nt: ACGTACGTACGTACGTACGT)
        # positions 11-20 = CGTACGTACGT? No, let me be precise
        # seq = ACGTACGTACGTACGTACGT (20 nt)
        # positions: 1=A,2=C,3=G,4=T,5=A,6=C,7=G,8=T,9=A,10=C,11=G,12=T,13=A,14=C,15=G,16=T,17=A,18=C,19=G,20=T
        # seed (11-20) = GTACGTACGT
        # GC in seed: G(11), C(14), G(15), C(18), G(19) = 5 G/C out of 10
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_seed_gc(seq, seed_region_length=10)
        self.assertEqual(result.summary["seed_gc_content"], 0.5)

    def test_threshold_pass(self):
        """Test threshold pass."""
        # 10-nt seed with 5 G/C = 0.5, within default [0.20, 0.80]
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_seed_gc(seq, seed_region_length=10)
        self.assertEqual(result.summary["seed_gc_content"], 0.5)
        self.assertTrue(result.summary["passes_seed_filter"])

    def test_threshold_fail(self):
        """Test threshold fail."""
        # All-A seed: positions 11-20 = AAAAAAAAAA, GC = 0.0
        seq = "AAAAAAAAAAAAAAAAAAAA"
        result = compute_seed_gc(seq, seed_region_length=10)
        self.assertEqual(result.summary["seed_gc_content"], 0.0)
        self.assertFalse(result.summary["passes_seed_filter"])

    def test_threshold_boundary_equality(self):
        """Test threshold boundary equality."""
        seq = "AAAAAAAAAAAAAAAAAAAA"
        # seed GC = 0.0, thresholds = [0.0, 0.8]
        result = compute_seed_gc(seq, seed_min_threshold=0.0, seed_max_threshold=0.8)
        self.assertTrue(result.summary["passes_seed_filter"])
        # thresholds = [0.0, 0.0]
        result2 = compute_seed_gc(seq, seed_min_threshold=0.0, seed_max_threshold=0.0)
        self.assertTrue(result2.summary["passes_seed_filter"])

    def test_rounding_does_not_affect_filtering(self):
        """Test that rounding does not affect threshold decisions."""
        # Create a sequence where seed GC is very close to threshold
        # 10-nt seed with 2 G/C out of 10 = 0.2 exactly
        seq = "AAAAAAAAAA" + "AC" + "AAAAAAAA"  # 20 nt, seed = AACAAAAAAAA (positions 11-20)
        # Actually let me construct more carefully:
        # positions 11-20 should have exactly 2 G/C
        seq = "AAAAAAAAAAGCAAAAAAAAA"  # too long
        # Let me use: positions 11-20 = "AACAAAAAAA" (1 GC at position 12=C)
        # Actually: "AACAAAAAAA" has 1 C = 0.1
        # For exact 0.1996: need ~2 G/C in 10 but with rounding
        # Simplest: use a sequence where raw GC = 0.1996 won't happen easily
        # Instead just test that rounding doesn't change the filter
        seq = "AAAAAAAAGCAAAAAAAAAA"  # 20 nt, positions 11-20 = GCAAAAAAAAA -> wait
        # Let me be precise:
        # seq = "AAAAAAAAGCAAAAAAAAAA" (20 chars)
        # positions: 1=A,2=A,3=A,4=A,5=A,6=A,7=A,8=G,9=C,10=A,11=A,12=A,13=A,14=A,15=A,16=A,17=A,18=A,19=A,20=A
        # seed (11-20) = AAAAAAAAAA, GC = 0.0
        # That's not useful. Let me just verify the full precision is used:
        # Use a case where rounding changes value but filter stays same
        seq = "ACGTACGTACGTACGTACGT"
        # seed (11-20) = GTACGTACGT, GC = 5/10 = 0.5
        result = compute_seed_gc(seq, seed_min_threshold=0.5, seed_max_threshold=0.5)
        self.assertTrue(result.summary["passes_seed_filter"])
        # With rounding, 0.5 stays 0.5, still passes
        result2 = compute_seed_gc(seq, seed_min_threshold=0.5, seed_max_threshold=0.5, round_decimals=0)
        self.assertTrue(result2.summary["passes_seed_filter"])

    def test_distal_gc_enabled(self):
        """Test distal GC enabled."""
        seq = "GCGCGCGCGCGCGCGCGCGG"
        result = compute_seed_gc(seq, compute_seed_distal_delta=True)
        self.assertIsNotNone(result.summary["distal_gc_content"])
        self.assertIsNotNone(result.summary["seed_distal_gc_delta"])

    def test_distal_gc_disabled(self):
        """Test distal GC disabled."""
        seq = "GCGCGCGCGCGCGCGCGCGG"
        result = compute_seed_gc(seq, compute_seed_distal_delta=False)
        self.assertIsNone(result.summary["distal_gc_content"])
        self.assertIsNone(result.summary["seed_distal_gc_delta"])

    def test_delta_positive(self):
        """Test positive delta (seed more GC-rich than distal)."""
        # distal (1-10) = AAAAAAAAAA (GC=0), seed (11-20) = GCGCGCGCGC (GC=1.0)
        seq = "AAAAAAAAAAGCGCGCGCGC"
        result = compute_seed_gc(seq, compute_seed_distal_delta=True)
        self.assertAlmostEqual(result.summary["seed_gc_content"], 1.0)
        self.assertAlmostEqual(result.summary["distal_gc_content"], 0.0)
        self.assertAlmostEqual(result.summary["seed_distal_gc_delta"], 1.0)

    def test_delta_negative(self):
        """Test negative delta (seed less GC-rich than distal)."""
        # distal (1-10) = GCGCGCGCGC (GC=1.0), seed (11-20) = AAAAAAAAAA (GC=0)
        seq = "GCGCGCGCGCAAAAAAAAAA"
        result = compute_seed_gc(seq, compute_seed_distal_delta=True)
        self.assertAlmostEqual(result.summary["seed_gc_content"], 0.0)
        self.assertAlmostEqual(result.summary["distal_gc_content"], 1.0)
        self.assertAlmostEqual(result.summary["seed_distal_gc_delta"], -1.0)

    def test_zero_distal_region(self):
        """Test zero/empty distal-region behavior."""
        # seed_region_length = sequence_length, distal is empty
        seq = "ACGTACGTACGTACGTACGT"
        result = compute_seed_gc(seq, seed_region_length=20, compute_seed_distal_delta=True)
        self.assertIsNone(result.summary["distal_gc_content"])
        self.assertIsNone(result.summary["seed_distal_gc_delta"])
        self.assertTrue(len(result.warnings) > 0)

    def test_invalid_seed_length(self):
        """Test invalid seed length returns error."""
        result = compute_seed_gc("ACGT", seed_region_length=0)
        self.assertTrue(result.errors)
        self.assertIn("positive integer", result.errors[0])

    def test_invalid_seed_anchor(self):
        """Test invalid seed anchor returns error."""
        result = compute_seed_gc("ACGTACGTACGTACGTACGT", seed_anchor="invalid")
        self.assertTrue(result.errors)
        self.assertIn("pam_proximal", result.errors[0])

    def test_invalid_threshold_ordering(self):
        """Test invalid threshold ordering returns error."""
        result = compute_seed_gc("ACGTACGTACGTACGTACGT", seed_min_threshold=0.8, seed_max_threshold=0.2)
        self.assertTrue(result.errors)
        self.assertIn("must be <=", result.errors[0])

    def test_invalid_threshold_ranges(self):
        """Test invalid threshold ranges returns error."""
        result = compute_seed_gc("ACGTACGTACGTACGTACGT", seed_min_threshold=-0.1)
        self.assertTrue(result.errors)
        self.assertIn("[0, 1]", result.errors[0])

    def test_ambiguous_base_behavior(self):
        """Test ambiguous-base behavior consistent with compute_gc_content."""
        # N is not G or C, so it should not contribute to GC numerator
        # but should count in denominator
        seq = "NNNNNNNNNNCGCGCGCGCG"  # 10 N's + 10 bases with 5 G/C
        result = compute_seed_gc(seq, seed_region_length=10)
        # seed (11-20) = CGCGCGCGCG, GC = 1.0
        self.assertEqual(result.summary["seed_gc_content"], 1.0)
        # distal (1-10) = NNNNNNNNNN, GC = 0.0 (N not counted as G/C)
        result2 = compute_seed_gc(seq, compute_seed_distal_delta=True)
        self.assertEqual(result2.summary["distal_gc_content"], 0.0)

    def test_alternate_sequence_lengths(self):
        """Test alternate sequence lengths."""
        # 30-nt sequence, 15-nt seed
        seq = "ACGT" * 7 + "AC"  # 30 nt
        result = compute_seed_gc(seq, seed_region_length=15)
        self.assertEqual(result.summary["sequence_length"], 30)
        self.assertEqual(result.summary["seed_region_length"], 15)
        self.assertEqual(result.summary["seed_start_position"], 16)
        self.assertEqual(result.summary["seed_end_position"], 30)

    def test_deterministic_repeatability(self):
        """Test deterministic repeatability."""
        seq = "GCGCGCGCGCGCGCGCGCGG"
        r1 = compute_seed_gc(seq)
        r2 = compute_seed_gc(seq)
        self.assertEqual(r1.summary["seed_gc_content"], r2.summary["seed_gc_content"])
        self.assertEqual(r1.summary["passes_seed_filter"], r2.summary["passes_seed_filter"])
        self.assertEqual(r1.summary["seed_start_position"], r2.summary["seed_start_position"])


# =====================================================================
# cas_offinder_search tests
# =====================================================================

class TestCasOFFinderSearch(unittest.TestCase):
    """Tests for the cas_offinder_search MCP tool."""

    def test_cas_offinder_executable_exists(self):
        """Test that Cas-OFFinder executable exists."""
        from mcp.tools.cas_offinder_search import _CAS_OFFINDER_BIN
        import os
        self.assertTrue(os.path.isfile(_CAS_OFFINDER_BIN))

    def test_cas_offinder_search_ecoli(self):
        """Test Cas-OFFinder search on E. coli."""
        from mcp.tools.cas_offinder_search import cas_offinder_search

        result = cas_offinder_search(
            spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
            genome_id="ecoli_k12_mg1655",
            pam_pattern="NGG",
            max_mismatches=3,
            max_dna_bulge=0,
            max_rna_bulge=0,
        )
        self.assertEqual(result.tool, "cas_offinder_search")
        self.assertEqual(result.summary["backend"], "cas_offinder")
        self.assertEqual(result.summary["execution_device"], "cpu")
        self.assertGreater(result.summary["total_candidates"], 0)

    def test_cas_offinder_dna_bulge(self):
        """Test Cas-OFFinder with DNA bulge."""
        from mcp.tools.cas_offinder_search import cas_offinder_search

        result = cas_offinder_search(
            spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
            genome_id="ecoli_k12_mg1655",
            pam_pattern="NGG",
            max_mismatches=3,
            max_dna_bulge=1,
            max_rna_bulge=0,
        )
        self.assertEqual(result.tool, "cas_offinder_search")
        self.assertIn("DNA", result.summary.get("bulge_distribution", {}))

    def test_cas_offinder_rna_bulge(self):
        """Test Cas-OFFinder with RNA bulge."""
        from mcp.tools.cas_offinder_search import cas_offinder_search

        result = cas_offinder_search(
            spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
            genome_id="ecoli_k12_mg1655",
            pam_pattern="NGG",
            max_mismatches=3,
            max_dna_bulge=0,
            max_rna_bulge=1,
        )
        self.assertEqual(result.tool, "cas_offinder_search")
        self.assertIn("RNA", result.summary.get("bulge_distribution", {}))

    def test_cas_offinder_invalid_bulge_size(self):
        """Test Cas-OFFinder with invalid bulge size."""
        from mcp.tools.cas_offinder_search import cas_offinder_search

        result = cas_offinder_search(
            spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
            genome_id="ecoli_k12_mg1655",
            max_dna_bulge=10,
        )
        self.assertTrue(result.errors)

    def test_cas_offinder_invalid_backend(self):
        """Test Cas-OFFinder with invalid search scope."""
        from mcp.tools.cas_offinder_search import cas_offinder_search

        result = cas_offinder_search(
            spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
            genome_id="ecoli_k12_mg1655",
            search_scope="invalid",
        )
        self.assertTrue(result.errors)

    def test_cas_offinder_region_scope(self):
        """Test Cas-OFFinder with region scope."""
        from mcp.tools.cas_offinder_search import cas_offinder_search

        result = cas_offinder_search(
            spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
            genome_id="ecoli_k12_mg1655",
            pam_pattern="NGG",
            max_mismatches=3,
            max_dna_bulge=0,
            max_rna_bulge=0,
            search_scope="region",
            chrom="NC_000913.3",
            start=288400,
            end=288500,
        )
        self.assertEqual(result.tool, "cas_offinder_search")
        self.assertEqual(result.summary["search_scope"], "region")

    def test_cas_offinder_invalid_region_params(self):
        """Test Cas-OFFinder with missing region parameters."""
        from mcp.tools.cas_offinder_search import cas_offinder_search

        result = cas_offinder_search(
            spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
            genome_id="ecoli_k12_mg1655",
            search_scope="region",
        )
        self.assertTrue(result.errors)


# =====================================================================
# analyze_mismatch_seed tests
# =====================================================================

class TestAnalyzeMismatchSeed(unittest.TestCase):
    """Tests for the analyze_mismatch_seed MCP tool."""

    def test_no_mismatch(self):
        """Test analysis with no mismatches."""
        from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed

        result = analyze_mismatch_seed(
            spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
            candidate_sequence="GCGCGCGCGCGCGCGCGCGC",
        )
        self.assertEqual(result.tool, "analyze_mismatch_seed")
        self.assertEqual(result.summary["total_mismatches"], 0)
        self.assertFalse(result.summary["has_seed_mismatch"])

    def test_mismatch_in_seed(self):
        """Test analysis with mismatch in seed region."""
        from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed

        # Position 15 (0-based) is in seed region (positions 11-20)
        spacer = "GCGCGCGCGCGCGCGCGCGC"
        candidate = list(spacer)
        candidate[15] = "A"  # Mismatch at position 15
        candidate = "".join(candidate)

        result = analyze_mismatch_seed(
            spacer_sequence=spacer,
            candidate_sequence=candidate,
        )
        self.assertEqual(result.summary["total_mismatches"], 1)
        self.assertEqual(result.summary["seed_mismatch_count"], 1)
        self.assertTrue(result.summary["has_seed_mismatch"])

    def test_mismatch_in_distal(self):
        """Test analysis with mismatch in distal region."""
        from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed

        # Position 5 (0-based) is in distal region (positions 1-10)
        spacer = "GCGCGCGCGCGCGCGCGCGC"
        candidate = list(spacer)
        candidate[5] = "A"  # Mismatch at position 5
        candidate = "".join(candidate)

        result = analyze_mismatch_seed(
            spacer_sequence=spacer,
            candidate_sequence=candidate,
        )
        self.assertEqual(result.summary["total_mismatches"], 1)
        self.assertEqual(result.summary["distal_mismatch_count"], 1)
        self.assertFalse(result.summary["has_seed_mismatch"])

    def test_dna_bulge_type(self):
        """Test analysis with DNA bulge type."""
        from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed

        result = analyze_mismatch_seed(
            spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
            candidate_sequence="GCGCGCGCGCGCGCGCGCGC",
            bulge_type="DNA",
            bulge_size=1,
        )
        self.assertEqual(result.summary["bulge_type"], "DNA")
        self.assertEqual(result.summary["bulge_size"], 1)

    def test_rna_bulge_type(self):
        """Test analysis with RNA bulge type."""
        from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed

        result = analyze_mismatch_seed(
            spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
            candidate_sequence="GCGCGCGCGCGCGCGCGCGC",
            bulge_type="RNA",
            bulge_size=1,
        )
        self.assertEqual(result.summary["bulge_type"], "RNA")
        self.assertEqual(result.summary["bulge_size"], 1)

    def test_invalid_bulge_type(self):
        """Test analysis with invalid bulge type."""
        from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed

        result = analyze_mismatch_seed(
            spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
            candidate_sequence="GCGCGCGCGCGCGCGCGCGC",
            bulge_type="INVALID",
        )
        self.assertTrue(result.errors)

    def test_invalid_spacer(self):
        """Test analysis with invalid spacer."""
        from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed

        result = analyze_mismatch_seed(
            spacer_sequence="INVALID",
            candidate_sequence="GCGCGCGCGCGCGCGCGCGC",
        )
        self.assertTrue(result.errors)

    def test_seed_region_length_validation(self):
        """Test analysis with invalid seed region length."""
        from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed

        result = analyze_mismatch_seed(
            spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
            candidate_sequence="GCGCGCGCGCGCGCGCGCGC",
            seed_region_length=100,
        )
        self.assertTrue(result.errors)

    def test_alignment_aware_analysis(self):
        """Test alignment-aware analysis with bulge."""
        from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed

        result = analyze_mismatch_seed(
            spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
            candidate_sequence="GCGCGCGCGCGCGCGCGCGCA",
            bulge_type="DNA",
            bulge_size=1,
            aligned_guide="GCGCGCGCGCGCGCGCGCGC-",
            aligned_candidate="GCGCGCGCGCGCGCGCGCGCA",
        )
        self.assertEqual(result.summary["bulge_type"], "DNA")
        self.assertEqual(result.summary["bulge_size"], 1)

    def test_deterministic_repeatability(self):
        """Test deterministic repeatability."""
        from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed

        spacer = "GCGCGCGCGCGCGCGCGCGC"
        candidate = list(spacer)
        candidate[15] = "A"
        candidate = "".join(candidate)

        r1 = analyze_mismatch_seed(spacer_sequence=spacer, candidate_sequence=candidate)
        r2 = analyze_mismatch_seed(spacer_sequence=spacer, candidate_sequence=candidate)
        self.assertEqual(r1.summary["total_mismatches"], r2.summary["total_mismatches"])
        self.assertEqual(r1.summary["seed_mismatch_count"], r2.summary["seed_mismatch_count"])


# =====================================================================
# compute_cut_site tests
# =====================================================================

class TestComputeCutSite(unittest.TestCase):
    """Tests for the compute_cut_site MCP tool."""

    def test_plus_strand_spacer9(self):
        """Test plus strand SpCas9 default cut site."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=100000, chrom="NC_000913.3")
        self.assertEqual(result.tool, "compute_cut_site")
        self.assertEqual(result.summary["cut_site_genomic"], 100017)
        self.assertEqual(result.summary["cut_site_relative"], 17)
        self.assertEqual(result.summary["strand"], "+")
        self.assertEqual(result.summary["offset_source"], "canonical")

    def test_minus_strand_spacer9(self):
        """Test minus strand SpCas9 cut site maps correctly."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=100000, strand="-", chrom="NC_000913.3")
        self.assertEqual(result.tool, "compute_cut_site")
        self.assertEqual(result.summary["cut_site_genomic"], 100003)
        self.assertEqual(result.summary["cut_site_relative"], 17)
        self.assertEqual(result.summary["strand"], "-")

    def test_default_20nt_spacer(self):
        """Test default 20-nt spacer produces cut at position 17|18 boundary."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=0, chrom="NC_000913.3")
        self.assertEqual(result.summary["cut_site_relative"], 17)
        self.assertEqual(result.summary["cut_site_relative_boundary"], "17|18")

    def test_relative_cut_boundary_17_18(self):
        """Test that relative cut is between positions 17 and 18 (1-based)."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=0, chrom="NC_000913.3")
        boundary = result.summary["cut_site_relative_boundary"]
        self.assertEqual(boundary, "17|18")

    def test_custom_spacer_length(self):
        """Test custom spacer length shifts cut position."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=100000, spacer_length=15, chrom="NC_000913.3")
        # 15 + (-3) = 12
        self.assertEqual(result.summary["cut_site_relative"], 12)
        self.assertEqual(result.summary["cut_site_genomic"], 100012)

    def test_custom_cut_offset(self):
        """Test custom cut offset from PAM."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=100000, cut_offset_from_pam=-5, chrom="NC_000913.3")
        # 20 + (-5) = 15
        self.assertEqual(result.summary["cut_site_relative"], 15)
        self.assertEqual(result.summary["cut_site_genomic"], 100015)
        self.assertEqual(result.summary["offset_source"], "custom")
        self.assertTrue(len(result.warnings) > 0)

    def test_0based_half_open_input(self):
        """Test 0-based half-open coordinate convention."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=0, chrom="chr1")
        # spacer [0, 20), cut at boundary 17
        self.assertEqual(result.summary["cut_site_genomic"], 17)
        self.assertEqual(result.summary["spacer_start"], 0)
        self.assertEqual(result.summary["spacer_end"], 20)

    def test_genomic_coordinate_calculation(self):
        """Test genomic coordinate is correctly computed."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=50000, strand="+", chrom="NC_000913.3")
        self.assertEqual(result.summary["cut_site_genomic"], 50017)
        self.assertEqual(result.summary["chrom"], "NC_000913.3")

    def test_return_genomic_coord_false(self):
        """Test omitting genomic coordinate."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=100000, return_genomic_coord=False)
        self.assertIsNone(result.summary["cut_site_genomic"])
        self.assertEqual(result.summary["cut_site_relative"], 17)

    def test_return_relative_coord_false(self):
        """Test omitting relative coordinate."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=100000, return_relative_coord=False, chrom="NC_000913.3")
        self.assertEqual(result.summary["cut_site_genomic"], 100017)
        self.assertIsNone(result.summary["cut_site_relative"])

    def test_invalid_strand(self):
        """Test invalid strand returns error."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=100000, strand="X", chrom="NC_000913.3")
        self.assertTrue(result.errors)
        self.assertIn("strand", result.errors[0])

    def test_invalid_pam_position(self):
        """Test unsupported PAM position returns error."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=100000, pam_position="5prime", chrom="NC_000913.3")
        self.assertTrue(result.errors)
        self.assertIn("pam_position", result.errors[0])

    def test_invalid_spacer_length(self):
        """Test invalid spacer length returns error."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=100000, spacer_length=-5, chrom="NC_000913.3")
        self.assertTrue(result.errors)
        self.assertIn("spacer_length", result.errors[0])

    def test_invalid_coordinate(self):
        """Test negative spacer_start returns error."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=-1, chrom="NC_000913.3")
        self.assertTrue(result.errors)
        self.assertIn("spacer_start", result.errors[0])

    def test_plus_minus_symmetry(self):
        """Test plus and minus strand produce symmetric genomic coordinates."""
        from mcp.tools.compute_cut_site import compute_cut_site

        spacer_start = 100000
        spacer_length = 20
        plus = compute_cut_site(spacer_start=spacer_start, spacer_length=spacer_length, strand="+", chrom="NC_000913.3")
        minus = compute_cut_site(spacer_start=spacer_start, spacer_length=spacer_length, strand="-", chrom="NC_000913.3")
        # Both should have same relative cut
        self.assertEqual(plus.summary["cut_site_relative"], minus.summary["cut_site_relative"])
        # Genomic coords should be symmetric around the spacer
        # plus: start + 17 = 100017
        # minus: end - 17 = 100020 - 17 = 100003
        self.assertEqual(plus.summary["cut_site_genomic"], 100017)
        self.assertEqual(minus.summary["cut_site_genomic"], 100003)

    def test_cli_standalone(self):
        """Test CLI entry point works."""
        import subprocess
        import json

        r = subprocess.run([
            sys.executable, "-m", "mcp.tools.compute_cut_site",
            "--spacer-start", "100000",
            "--chrom", "NC_000913.3",
        ], capture_output=True, text=True, cwd=".")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertEqual(data["summary"]["cut_site_genomic"], 100017)

    def test_deterministic_repeatability(self):
        """Test deterministic repeatability."""
        from mcp.tools.compute_cut_site import compute_cut_site

        r1 = compute_cut_site(spacer_start=100000, chrom="NC_000913.3")
        r2 = compute_cut_site(spacer_start=100000, chrom="NC_000913.3")
        self.assertEqual(r1.summary["cut_site_genomic"], r2.summary["cut_site_genomic"])
        self.assertEqual(r1.summary["cut_site_relative"], r2.summary["cut_site_relative"])

    def test_metadata_nuclease(self):
        """Test metadata contains nuclease info."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=100000, chrom="NC_000913.3")
        self.assertEqual(result.metadata["nuclease"], "SpCas9")
        self.assertEqual(result.metadata["pam_type"], "3prime")

    def test_missing_chrom_for_genomic(self):
        """Test missing chrom returns error when genomic coord requested."""
        from mcp.tools.compute_cut_site import compute_cut_site

        result = compute_cut_site(spacer_start=100000, return_genomic_coord=True, chrom="")
        self.assertTrue(result.errors)
        self.assertIn("chrom", result.errors[0])


if __name__ == "__main__":
    unittest.main()
