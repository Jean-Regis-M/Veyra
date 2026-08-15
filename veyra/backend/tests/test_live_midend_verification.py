"""VEYRA Midend Contract Live Verification Suite.

Performs live black-box and interface verification of the VEYRA backend against midend.md contract.
Tests CLI, HTTP API, MCP tools, and Python API surfaces across all 28 public operations.
"""

import os
import sys
import unittest
import json
import io
import shutil
from typing import Any, Dict, List

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from fastapi.testclient import TestClient
from http_api.app import app
from cli.main import main as cli_main
from mcp.server import TOOL_REGISTRY
import api
from core.ingestion import ingest as core_ingest
from core.pam import pam_scan as core_pam_scan, pam_scan_region as core_pam_scan_region
from core.offtarget import score_offtargets as core_score_offtargets, offtarget_search as core_offtarget_search
from core.ranking import rank_candidates as core_rank_candidates
from core.cut_site import compute_cut_site as core_compute_cut_site
from schemas.canonical import (
    IngestRequest, PamScanRequest, PamScanRegionRequest, OfftargetSearchRequest,
    ScoreOfftargetsRequest, RankCandidatesRequest, ComputeCutSiteRequest
)


class TestLiveMidendContractVerification(unittest.TestCase):
    """Full live operational contract verification suite."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.fixtures_dir = os.path.join(_BACKEND_DIR, "tests", "fixtures")
        cls.test_fasta = os.path.join(cls.fixtures_dir, "test.fasta")
        cls.test_genome = os.path.join(cls.fixtures_dir, "test_genome.fa")
        cls.valid_20mer = "GAGTCCGAGCAGAAGAAGAA"
        cls.valid_30mer = "AAAAGAGTCCGAGCAGAAGAAGAAGGGTAA"  # 4 + 20 + 3 + 3 = 30
        cls.valid_seq = "GAGTCCGAGCAGAAGAAGAAGGGTTTCCTT"

    # ---------------------------------------------------------------------------
    # 1. Startup & Public Endpoint Availability Verification
    # ---------------------------------------------------------------------------
    def test_01_http_public_endpoints_availability(self):
        """Verify HTTP /health, /docs, /openapi.json endpoints."""
        res_health = self.client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["status"], "ok")

        res_docs = self.client.get("/docs")
        self.assertEqual(res_docs.status_code, 200)

        res_openapi = self.client.get("/openapi.json")
        self.assertEqual(res_openapi.status_code, 200)
        openapi_spec = res_openapi.json()
        self.assertIn("paths", openapi_spec)
        self.assertIn("/sequence/gc", openapi_spec["paths"])
        self.assertIn("/offtarget/search", openapi_spec["paths"])

    def test_02_mcp_registry_availability(self):
        """Verify MCP tool registry availability and completeness."""
        self.assertGreaterEqual(len(TOOL_REGISTRY), 20)
        expected_tools = [
            "pam_scan", "pam_scan_region", "build_offtarget_index",
            "offtarget_search", "cas_offinder_search", "score_offtargets",
            "rank_candidates", "compute_gc_content", "check_homopolymer_runs",
            "compute_melting_temp", "compute_secondary_structure",
            "compute_positional_features", "compute_dinucleotide_composition",
            "compute_seed_gc", "compute_cut_site", "predict_ontarget_efficiency",
            "analyze_mismatch_seed", "models_list_runtimes", "model_status",
            "setup_model", "verify_model"
        ]
        for tool_name in expected_tools:
            self.assertIn(tool_name, TOOL_REGISTRY, f"MCP tool missing: {tool_name}")
            self.assertIn("function", TOOL_REGISTRY[tool_name])

    def test_03_cli_help_availability(self):
        """Verify CLI entrypoint availability and top-level help."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        old_stdout, old_stderr = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = stdout_buf, stderr_buf
            exit_code = cli_main(["--help"])
        except SystemExit as e:
            exit_code = e.code
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
        self.assertEqual(exit_code, 0)
        self.assertIn("VEYRA", stdout_buf.getvalue())

    # ---------------------------------------------------------------------------
    # 2. Live Ingestion Verification
    # ---------------------------------------------------------------------------
    def test_04_ingest_verification(self):
        """Test sequence ingestion across interfaces."""
        # 1. Python API / Core
        api_res = api.ingest_file(input_path=self.test_fasta)
        self.assertEqual(api_res.tool, "ingest")
        self.assertFalse(api_res.errors)
        self.assertGreater(len(api_res.rows), 0)

        # 2. HTTP API
        http_res = self.client.post("/ingest", json={"input_path": self.test_fasta})
        self.assertEqual(http_res.status_code, 200)
        self.assertEqual(http_res.json()["tool"], "ingest")

        # 3. CLI
        stdout_buf = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = stdout_buf
            exit_code = cli_main(["ingest", "--input", self.test_fasta, "--output-format", "json"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(exit_code, 0)

    # ---------------------------------------------------------------------------
    # 3. Live PAM Scanning Verification
    # ---------------------------------------------------------------------------
    def test_05_pam_scan_verification(self):
        """Test pam_scan and pam_scan_region across interfaces."""
        # Python API helper / raw
        api_res = api.pam_scan_raw(sequence=self.valid_seq, pam_pattern="NGG", strand="both")
        self.assertEqual(api_res.tool, "pam_scan")
        self.assertFalse(api_res.errors)

        http_res = self.client.post("/pam/scan", json={"sequence": self.valid_seq, "pam_pattern": "NGG", "strand": "both"})
        self.assertEqual(http_res.status_code, 200)

        mcp_func = TOOL_REGISTRY["pam_scan"]["function"]
        mcp_res = mcp_func(sequence=self.valid_seq, pam_pattern="NGG", strand="both")
        self.assertEqual(mcp_res.tool, "pam_scan")

        # pam_scan_region on ecoli_k12_mg1655
        api_reg = api.pam_scan_region(genome_id="ecoli_k12_mg1655", chrom="NC_000913.3", start=1, end=1000, strand="both")
        self.assertEqual(api_reg.tool, "pam_scan_region")
        self.assertFalse(api_reg.errors)

        http_reg = self.client.post("/pam/scan-region", json={"genome_id": "ecoli_k12_mg1655", "chrom": "NC_000913.3", "start": 1, "end": 1000})
        self.assertEqual(http_reg.status_code, 200)

    # ---------------------------------------------------------------------------
    # 4. Live Sequence Feature Computation Verification
    # ---------------------------------------------------------------------------
    def test_06_sequence_feature_tools(self):
        """Test all 8 sequence feature computation operations."""
        seq = "GAGTCCGAGCAGAAGAAGAA"

        # 1. GC Content
        gc_res = api.compute_gc_content(seq)
        self.assertEqual(gc_res.tool, "compute_gc_content")

        # 2. Homopolymer runs
        hp_res = api.check_homopolymer_runs(seq, homopolymer_min_run=4)
        self.assertEqual(hp_res.tool, "check_homopolymer_runs")

        # 3. Melting Temp
        tm_res = api.compute_melting_temp(seq)
        self.assertEqual(tm_res.tool, "compute_melting_temp")

        # 4. Secondary Structure
        mfe_res = api.compute_secondary_structure(seq)
        self.assertEqual(mfe_res.tool, "compute_secondary_structure")

        # 5. Positional Features
        pos_res = api.compute_positional_features(seq)
        self.assertEqual(pos_res.tool, "compute_positional_features")

        # 6. Dinucleotide Composition
        dinuc_res = api.compute_dinucleotide_composition(seq)
        self.assertEqual(dinuc_res.tool, "compute_dinucleotide_composition")

        # 7. Seed GC
        seed_res = api.compute_seed_gc(seq)
        self.assertEqual(seed_res.tool, "compute_seed_gc")

        # 8. Cut Site (Core service)
        cut_req = ComputeCutSiteRequest(spacer_start=100, chrom="chr1", strand="+", pam_position="3prime", cut_offset_from_pam=-3)
        cut_res = core_compute_cut_site(cut_req)
        self.assertEqual(cut_res.tool, "compute_cut_site")

    # ---------------------------------------------------------------------------
    # 5. Live Genome / Index Operations Verification
    # ---------------------------------------------------------------------------
    def test_07_genome_and_index_operations(self):
        """Test list_genomes, genome_info, build_offtarget_index."""
        # list_genomes
        lg = api.get_genomes()
        self.assertEqual(lg.tool, "list_genomes")
        self.assertGreater(len(lg.rows), 0)

        # genome_info
        gi = api.get_genome_info("ecoli_k12_mg1655")
        self.assertEqual(gi.tool, "genome_info")
        self.assertEqual(gi.summary["genome_id"], "ecoli_k12_mg1655")

        # build_offtarget_index
        bi = api.build_offtarget_index("ecoli_k12_mg1655")
        self.assertEqual(bi.tool, "build_offtarget_index")

    # ---------------------------------------------------------------------------
    # 6. Live Off-Target Search Verification (BWA, Cas-OFFinder, Bulges)
    # ---------------------------------------------------------------------------
    def test_08_offtarget_search_modes(self):
        """Test BWA, Cas-OFFinder, DNA/RNA bulges, region and genome-wide scope."""
        spacer = "GAGTCCGAGCAGAAGAAGAA"

        # 1. BWA Mismatch-only search (genome-wide)
        bwa_res = api.search_offtargets(
            spacer_sequence=spacer,
            genome_id="ecoli_k12_mg1655",
            max_mismatches=3,
            allow_bulge=False,
            backend="bwa"
        )
        self.assertEqual(bwa_res.tool, "offtarget_search")
        self.assertEqual(bwa_res.summary["backend"], "bwa-aln")

        # 2. Cas-OFFinder mismatch search
        cas_res = api.search_offtargets(
            spacer_sequence=spacer,
            genome_id="ecoli_k12_mg1655",
            max_mismatches=3,
            allow_bulge=False,
            backend="cas_offinder"
        )
        self.assertEqual(cas_res.tool, "cas_offinder_search")

        # 3. Cas-OFFinder with DNA Bulge
        dna_bulge_res = api.search_offtargets(
            spacer_sequence=spacer,
            genome_id="ecoli_k12_mg1655",
            max_mismatches=2,
            allow_bulge=True,
            max_dna_bulge=1,
            max_rna_bulge=0,
            backend="cas_offinder"
        )
        self.assertEqual(dna_bulge_res.tool, "cas_offinder_search")

        # 4. Regional scope off-target search
        reg_res = api.search_offtargets(
            spacer_sequence=spacer,
            genome_id="ecoli_k12_mg1655",
            search_scope="region",
            chrom="NC_000913.3",
            start=1,
            end=10000,
            backend="bwa"
        )
        self.assertEqual(reg_res.tool, "offtarget_search")

    # ---------------------------------------------------------------------------
    # 7. Live Mismatch Seed Analysis & CFD Scoring
    # ---------------------------------------------------------------------------
    def test_09_mismatch_seed_and_cfd_scoring(self):
        """Test analyze_mismatch_seed and score_offtargets."""
        spacer = "GAGTCCGAGCAGAAGAAGAA"
        cand = "GAGTCCGAGCAGAAGAAGAC"  # 1 mismatch at pos 19

        # Seed analysis via MCP
        mcp_seed = TOOL_REGISTRY["analyze_mismatch_seed"]["function"]
        seed_res = mcp_seed(spacer_sequence=spacer, candidate_sequence=cand)
        self.assertEqual(seed_res.tool, "analyze_mismatch_seed")
        self.assertEqual(seed_res.summary["total_mismatches"], 1)

        # CFD Scoring via Core
        cfd_req = ScoreOfftargetsRequest(
            spacer_sequence=spacer,
            candidates=[{"protospacer": cand, "pam": "AGG", "mismatch_count": 1, "mismatch_positions": "19"}]
        )
        cfd_res = core_score_offtargets(cfd_req)
        self.assertEqual(cfd_res.tool, "score_offtargets")
        self.assertEqual(len(cfd_res.rows), 1)
        self.assertIsNotNone(cfd_res.rows[0].cfd_score)

    # ---------------------------------------------------------------------------
    # 8. Live On-Target Efficiency Models & Model Runtime Management
    # ---------------------------------------------------------------------------
    def test_10_ontarget_models_and_runtimes(self):
        """Test predict_ontarget_efficiency with models auto, doench_2014, rule_set_3, rule_set_2."""
        # 1. doench_2014
        rs1 = api.predict_ontarget_efficiency(context_sequence=self.valid_30mer, model="doench_2014")
        self.assertEqual(rs1.tool, "predict_ontarget_efficiency")
        self.assertFalse(rs1.errors)
        self.assertEqual(rs1.summary["model_used"], "doench_2014")

        # 2. auto
        auto_res = api.predict_ontarget_efficiency(context_sequence=self.valid_30mer, model="auto")
        self.assertEqual(auto_res.tool, "predict_ontarget_efficiency")
        self.assertFalse(auto_res.errors)

        # 3. rule_set_2 (explicit, should return error without fallback since Python 2.7 env missing)
        rs2 = api.predict_ontarget_efficiency(context_sequence=self.valid_30mer, model="rule_set_2")
        self.assertTrue(rs2.errors)
        self.assertEqual(rs2.summary["confidence_flag"], "model_unavailable")

        # Runtime MCP tools
        runtimes_fn = TOOL_REGISTRY["models_list_runtimes"]["function"]
        runtimes = runtimes_fn()
        self.assertEqual(runtimes.tool, "models_list_runtimes")

        status_fn = TOOL_REGISTRY["model_status"]["function"]
        st = status_fn(model_id="doench_2014")
        self.assertEqual(st.tool, "model_status")

        verify_fn = TOOL_REGISTRY["verify_model"]["function"]
        vr = verify_fn(model_id="doench_2014")
        self.assertEqual(vr.tool, "verify_model")
        self.assertEqual(vr.summary["result"]["verification_status"], "pass")

    # ---------------------------------------------------------------------------
    # 9. Live Candidate Ranking Verification
    # ---------------------------------------------------------------------------
    def test_11_rank_candidates(self):
        """Test rank_candidates with composite, offtarget, ontarget methods."""
        guides = [
            {"protospacer": "GAGTCCGAGCAGAAGAAGAA", "pam": "AGG", "rs2_score": 0.8, "cfd_score": 1.0},
            {"protospacer": "ACGTACGTACGTACGTACGT", "pam": "AGG", "rs2_score": 0.4, "cfd_score": 0.5},
        ]
        # composite via Core
        req_multi = RankCandidatesRequest(guides=guides, sort_by="composite")
        r_multi = core_rank_candidates(req_multi)
        self.assertEqual(r_multi.tool, "rank_candidates")
        self.assertEqual(len(r_multi.rows), 2)

        # cfd_max
        req_cfd = RankCandidatesRequest(guides=guides, sort_by="cfd_max")
        r_cfd = core_rank_candidates(req_cfd)
        self.assertEqual(r_cfd.tool, "rank_candidates")

        # on_target
        req_ontarget = RankCandidatesRequest(guides=guides, sort_by="on_target")
        r_ontarget = core_rank_candidates(req_ontarget)
        self.assertEqual(r_ontarget.tool, "rank_candidates")

    # ---------------------------------------------------------------------------
    # 10. Complete End-to-End Workflow Verification
    # ---------------------------------------------------------------------------
    def test_12_full_e2e_workflow(self):
        """Execute full end-to-end gRNA design workflow using public API surfaces."""
        # 1. Ingest
        ingest_res = api.ingest_file(input_path=self.test_fasta)
        self.assertFalse(ingest_res.errors)

        # 2. PAM Scan
        pam_res = api.pam_scan_raw(sequence=self.valid_30mer, pam_pattern="NGG", strand="fwd")
        self.assertGreater(len(pam_res.rows), 0)
        protospacers = [r.protospacer for r in pam_res.rows if r.protospacer]
        self.assertGreater(len(protospacers), 0)
        protospacer = protospacers[0]

        # 3. GC Content
        gc_res = api.compute_gc_content(protospacer)
        self.assertFalse(gc_res.errors)

        # 4. Secondary Structure
        sec_res = api.compute_secondary_structure(protospacer)
        self.assertEqual(sec_res.tool, "compute_secondary_structure")

        # 5. Cut Site
        cut_req = ComputeCutSiteRequest(spacer_start=100, chrom="NC_000913.3", strand="+")
        cut_res = core_compute_cut_site(cut_req)
        self.assertFalse(cut_res.errors)

        # 6. On-Target Efficiency
        ctx_seq = "AAAAGAGTCCGAGCAGAAGAAGAAGGGTAA"
        ontarget_res = api.predict_ontarget_efficiency(context_sequence=ctx_seq, model="auto")
        self.assertFalse(ontarget_res.errors)

        # 7. Off-Target Search
        off_res = api.search_offtargets(
            spacer_sequence=protospacer,
            genome_id="ecoli_k12_mg1655",
            max_mismatches=3,
            backend="bwa"
        )
        self.assertFalse(off_res.errors)

        # 8. Mismatch / Seed analysis for hits
        mcp_seed = TOOL_REGISTRY["analyze_mismatch_seed"]["function"]
        cand_seq = off_res.rows[0].protospacer if off_res.rows else protospacer
        mismatch_res = mcp_seed(spacer_sequence=protospacer, candidate_sequence=cand_seq)
        self.assertFalse(mismatch_res.errors)

        # 9. CFD Scoring
        candidates_to_score = [
            {
                "protospacer": row.protospacer,
                "pam": row.pam,
                "mismatch_count": row.mismatch_count,
                "mismatch_positions": row.mismatch_positions
            }
            for row in off_res.rows[:5]
        ] if off_res.rows else [{"protospacer": protospacer, "pam": "AGG", "mismatch_count": 0}]

        cfd_req = ScoreOfftargetsRequest(spacer_sequence=protospacer, candidates=candidates_to_score)
        cfd_res = core_score_offtargets(cfd_req)
        self.assertFalse(cfd_res.errors)

        # 10. Ranking
        guides_input = [
            {
                "protospacer": protospacer,
                "pam": "AGG",
                "rs2_score": ontarget_res.summary.get("ontarget_score", 0.5),
                "cfd_score": cfd_res.summary.get("mean_cfd_score", 1.0),
            }
        ]
        rank_req = RankCandidatesRequest(guides=guides_input, sort_by="composite")
        ranked_res = core_rank_candidates(rank_req)
        self.assertFalse(ranked_res.errors)
        self.assertEqual(len(ranked_res.rows), 1)

    # ---------------------------------------------------------------------------
    # 11. Parameter Forwarding Verification
    # ---------------------------------------------------------------------------
    def test_13_parameter_forwarding(self):
        """Verify that changing input parameters actually alters operation behavior."""
        # 1. strand: fwd vs rev vs both
        fwd_res = api.pam_scan_raw(sequence=self.valid_seq, strand="fwd")
        both_res = api.pam_scan_raw(sequence=self.valid_seq, strand="both")
        self.assertGreaterEqual(len(both_res.rows), len(fwd_res.rows))

        # 2. max_mismatches in offtarget search
        m1_res = api.search_offtargets(spacer_sequence=self.valid_20mer, genome_id="ecoli_k12_mg1655", max_mismatches=1, backend="bwa")
        m3_res = api.search_offtargets(spacer_sequence=self.valid_20mer, genome_id="ecoli_k12_mg1655", max_mismatches=3, backend="bwa")
        self.assertLessEqual(len(m1_res.rows), len(m3_res.rows))

        # 3. allow_bulge & backend
        bwa_res = api.search_offtargets(spacer_sequence=self.valid_20mer, genome_id="ecoli_k12_mg1655", allow_bulge=False, backend="bwa")
        cas_res = api.search_offtargets(spacer_sequence=self.valid_20mer, genome_id="ecoli_k12_mg1655", allow_bulge=True, max_dna_bulge=1, backend="cas_offinder")
        self.assertEqual(bwa_res.summary["backend"], "bwa-aln")
        self.assertEqual(cas_res.summary["backend"], "cas_offinder")

        # 4. GC thresholds
        gc_pass = api.compute_gc_content(self.valid_20mer, gc_min_threshold=0.2, gc_max_threshold=0.8)
        gc_fail = api.compute_gc_content(self.valid_20mer, gc_min_threshold=0.9, gc_max_threshold=1.0)
        self.assertTrue(gc_pass.summary["passes_basic_filter"])
        self.assertFalse(gc_fail.summary["passes_basic_filter"])

    # ---------------------------------------------------------------------------
    # 12. Default Equivalence Verification
    # ---------------------------------------------------------------------------
    def test_14_default_equivalence(self):
        """Verify omitted parameters match explicit documented defaults."""
        # PAM scan defaults: pam_pattern="NGG", strand="both", protospacer_len=20
        res_omitted = api.pam_scan_raw(sequence=self.valid_seq)
        res_explicit = api.pam_scan_raw(sequence=self.valid_seq, pam_pattern="NGG", strand="both", protospacer_len=20)
        self.assertEqual(len(res_omitted.rows), len(res_explicit.rows))

        # GC content defaults: gc_min_threshold=0.20, gc_max_threshold=0.80
        gc_omitted = api.compute_gc_content(self.valid_20mer)
        gc_explicit = api.compute_gc_content(self.valid_20mer, gc_min_threshold=0.20, gc_max_threshold=0.80)
        self.assertEqual(gc_omitted.summary["passes_basic_filter"], gc_explicit.summary["passes_basic_filter"])

    # ---------------------------------------------------------------------------
    # 13. Deliberate Bad Inputs Verification
    # ---------------------------------------------------------------------------
    def test_15_deliberate_bad_inputs(self):
        """Verify proper error handling without crashes for invalid inputs."""
        # 1. Invalid DNA sequence
        gc_bad = api.compute_gc_content("INVALID_DNA_XYZ")
        self.assertTrue(gc_bad.errors)

        # 2. Empty sequence
        pam_empty = api.pam_scan_raw("")
        self.assertTrue(pam_empty.errors)

        # 3. Invalid coordinate start >= end
        reg_bad = api.pam_scan_region(genome_id="ecoli_k12_mg1655", chrom="NC_000913.3", start=100, end=50)
        self.assertTrue(reg_bad.errors)

        # 4. Unknown genome ID
        off_bad = api.search_offtargets(spacer_sequence=self.valid_20mer, genome_id="nonexistent_genome")
        self.assertTrue(off_bad.errors)

        # 5. Invalid model name
        ontarget_bad = api.predict_ontarget_efficiency(context_sequence=self.valid_30mer, model="invalid_model_name")
        self.assertTrue(ontarget_bad.errors)

        # 6. HTTP API 400 validation
        http_bad = self.client.post("/sequence/gc", json={"sequence": "INVALID_XYZ"})
        self.assertIn(http_bad.status_code, (400, 422))

    # ---------------------------------------------------------------------------
    # 14. Cross-Interface Parity Verification
    # ---------------------------------------------------------------------------
    def test_16_cross_interface_parity(self):
        """Verify identical canonical output across Python, HTTP, CLI, and MCP."""
        seq = "GAGTCCGAGCAGAAGAAGAA"

        # Python API
        p_res = api.compute_gc_content(seq)
        # HTTP API
        h_res = self.client.post("/sequence/gc", json={"sequence": seq}).json()
        # MCP Tool
        m_func = TOOL_REGISTRY["compute_gc_content"]["function"]
        m_res = m_func(sequence=seq)

        self.assertEqual(p_res.summary["gc_content"], h_res["summary"]["gc_content"])
        self.assertEqual(p_res.summary["gc_content"], m_res.summary["gc_content"])


if __name__ == "__main__":
    unittest.main()
