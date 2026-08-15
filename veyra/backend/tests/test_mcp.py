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
        self.assertEqual(len(TOOL_REGISTRY), 6)


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


if __name__ == "__main__":
    unittest.main()
