"""Interface-level tests for VEYRA unified interface.

Tests that CLI, Python API, HTTP API, and MCP produce equivalent results
for the same operations.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


class TestPamScanInterfaceParity(unittest.TestCase):
    """Test that PAM scan produces equivalent results across all interfaces."""

    SEQUENCE = "ATCGATCGAGGATCGATCGATCG"
    PAM_PATTERN = "NGG"

    def test_python_api_pam_scan(self):
        """Test Python API PAM scan."""
        from api import pam_scan_raw

        result = pam_scan_raw(self.SEQUENCE, pam_pattern=self.PAM_PATTERN)
        self.assertEqual(result.tool, "pam_scan")
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0].start, 9)
        self.assertEqual(result.rows[0].pam, "AGG")
        self.assertEqual(result.summary["total_sites"], 1)

    def test_core_service_pam_scan(self):
        """Test core service PAM scan."""
        from core.pam import pam_scan
        from schemas.canonical import PamScanRequest

        request = PamScanRequest(
            sequence=self.SEQUENCE,
            pam_pattern=self.PAM_PATTERN,
        )
        result = pam_scan(request)
        self.assertEqual(result.tool, "pam_scan")
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0].start, 9)

    def test_cli_pam_scan(self):
        """Test CLI PAM scan."""
        from cli.main import main

        exit_code = main([
            "pam", "scan",
            "--sequence", self.SEQUENCE,
            "--pam-pattern", self.PAM_PATTERN,
            "--output-format", "json",
        ])
        self.assertEqual(exit_code, 0)

    def test_http_api_pam_scan(self):
        """Test HTTP API PAM scan."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/pam/scan", json={
            "sequence": self.SEQUENCE,
            "pam_pattern": self.PAM_PATTERN,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tool"], "pam_scan")
        self.assertEqual(len(data["rows"]), 1)
        self.assertEqual(data["rows"][0]["start"], 9)

    def test_mcp_pam_scan(self):
        """Test MCP PAM scan."""
        from mcp.tools.pam_scan import pam_scan

        result = pam_scan(self.SEQUENCE, pam_pattern=self.PAM_PATTERN)
        self.assertEqual(result.tool, "pam_scan")
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0].start, 9)

    def test_all_interfaces_produce_same_result(self):
        """Verify all interfaces produce equivalent results."""
        from api import pam_scan_raw
        from core.pam import pam_scan
        from schemas.canonical import PamScanRequest
        from mcp.tools.pam_scan import pam_scan as mcp_pam_scan
        from http_api.app import app
        from fastapi.testclient import TestClient

        # Python API
        api_result = pam_scan_raw(self.SEQUENCE, pam_pattern=self.PAM_PATTERN)

        # Core service
        core_result = pam_scan(PamScanRequest(
            sequence=self.SEQUENCE,
            pam_pattern=self.PAM_PATTERN,
        ))

        # MCP
        mcp_result = mcp_pam_scan(self.SEQUENCE, pam_pattern=self.PAM_PATTERN)

        # HTTP API
        client = TestClient(app)
        http_response = client.post("/pam/scan", json={
            "sequence": self.SEQUENCE,
            "pam_pattern": self.PAM_PATTERN,
        })
        http_data = http_response.json()

        # All should have the same PAM site
        self.assertEqual(api_result.rows[0].start, core_result.rows[0].start)
        self.assertEqual(api_result.rows[0].start, mcp_result.rows[0].start)
        self.assertEqual(api_result.rows[0].start, http_data["rows"][0]["start"])

        self.assertEqual(api_result.rows[0].pam, core_result.rows[0].pam)
        self.assertEqual(api_result.rows[0].pam, mcp_result.rows[0].pam)
        self.assertEqual(api_result.rows[0].pam, http_data["rows"][0]["pam"])


class TestGenomeInterfaceParity(unittest.TestCase):
    """Test that genome operations produce equivalent results across interfaces."""

    def test_python_api_genome_list(self):
        """Test Python API genome list."""
        from api import get_genomes

        result = get_genomes()
        self.assertEqual(result.tool, "list_genomes")
        self.assertIn("total_genomes", result.summary)

    def test_core_service_genome_list(self):
        """Test core service genome list."""
        from core.genome import list_genomes

        result = list_genomes()
        self.assertEqual(result.tool, "list_genomes")
        self.assertIn("total_genomes", result.summary)

    def test_cli_genome_list(self):
        """Test CLI genome list."""
        from cli.main import main

        exit_code = main(["genome", "list", "--output-format", "json"])
        self.assertEqual(exit_code, 0)

    def test_http_api_genome_list(self):
        """Test HTTP API genome list."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/genomes")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_genomes", data["summary"])


class TestToolsInterfaceParity(unittest.TestCase):
    """Test that tool listing produces equivalent results across interfaces."""

    def test_python_api_tools(self):
        """Test Python API tools list via MCP server."""
        from mcp.server import TOOL_REGISTRY

        self.assertEqual(len(TOOL_REGISTRY), 21)
        self.assertIn("pam_scan", TOOL_REGISTRY)
        self.assertIn("offtarget_search", TOOL_REGISTRY)
        self.assertIn("compute_gc_content", TOOL_REGISTRY)
        self.assertIn("check_homopolymer_runs", TOOL_REGISTRY)
        self.assertIn("compute_melting_temp", TOOL_REGISTRY)
        self.assertIn("compute_secondary_structure", TOOL_REGISTRY)
        self.assertIn("compute_positional_features", TOOL_REGISTRY)
        self.assertIn("compute_dinucleotide_composition", TOOL_REGISTRY)
        self.assertIn("compute_seed_gc", TOOL_REGISTRY)
        self.assertIn("cas_offinder_search", TOOL_REGISTRY)
        self.assertIn("analyze_mismatch_seed", TOOL_REGISTRY)
        self.assertIn("models_list_runtimes", TOOL_REGISTRY)
        self.assertIn("model_status", TOOL_REGISTRY)
        self.assertIn("setup_model", TOOL_REGISTRY)
        self.assertIn("verify_model", TOOL_REGISTRY)

    def test_cli_tools_list(self):
        """Test CLI tools list."""
        from cli.main import main

        exit_code = main(["tools", "list", "--output-format", "json"])
        self.assertEqual(exit_code, 0)

    def test_http_api_tools_list(self):
        """Test HTTP API tools list."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/tools")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_tools"], 21)


class TestCLIOutputFormats(unittest.TestCase):
    """Test CLI output format options."""

    def test_json_output(self):
        """Test JSON output format."""
        from cli.main import main
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            exit_code = main([
                "pam", "scan",
                "--sequence", "ATCGATCGAGG",
                "--output-format", "json",
            ])
        self.assertEqual(exit_code, 0)
        output = f.getvalue()
        data = json.loads(output)
        self.assertIn("tool", data)

    def test_tsv_output(self):
        """Test TSV output format."""
        from cli.main import main
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            exit_code = main([
                "pam", "scan",
                "--sequence", "ATCGATCGAGG",
                "--output-format", "tsv",
            ])
        self.assertEqual(exit_code, 0)
        output = f.getvalue()
        self.assertIn("chrom", output)

    def test_text_output(self):
        """Test text output format."""
        from cli.main import main
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            exit_code = main([
                "pam", "scan",
                "--sequence", "ATCGATCGAGG",
                "--output-format", "text",
            ])
        self.assertEqual(exit_code, 0)
        output = f.getvalue()
        self.assertIn("Tool:", output)


class TestHTTPAPIErrorHandling(unittest.TestCase):
    """Test HTTP API error handling."""

    def test_invalid_pam_pattern(self):
        """Test invalid PAM pattern returns 400."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/pam/scan", json={
            "sequence": "ATCG",
            "pam_pattern": "INVALID",
        })
        self.assertEqual(response.status_code, 400)

    def test_empty_sequence(self):
        """Test empty sequence returns 400."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/pam/scan", json={
            "sequence": "",
            "pam_pattern": "NGG",
        })
        self.assertEqual(response.status_code, 400)

    def test_health_endpoint(self):
        """Test health endpoint."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


class TestCanonicalSchemas(unittest.TestCase):
    """Test canonical schema functionality."""

    def test_result_row_to_dict(self):
        """Test ResultRow serialization."""
        from schemas.canonical import ResultRow

        row = ResultRow(
            chrom="chr1",
            start=100,
            end=103,
            strand="+",
            pam="AGG",
        )
        d = row.to_dict()
        self.assertEqual(d["chrom"], "chr1")
        self.assertEqual(d["start"], 100)
        self.assertEqual(d["pam"], "AGG")

    def test_veyra_result_json(self):
        """Test VeyraResult JSON serialization."""
        from schemas.canonical import VeyraResult, ResultRow

        result = VeyraResult(
            tool="test",
            rows=[ResultRow(chrom="chr1", start=1, end=4)],
            summary={"total": 1},
        )
        json_str = result.to_json()
        data = json.loads(json_str)
        self.assertEqual(data["tool"], "test")
        self.assertEqual(len(data["rows"]), 1)

    def test_veyra_result_tsv(self):
        """Test VeyraResult TSV serialization."""
        from schemas.canonical import VeyraResult, ResultRow

        result = VeyraResult(
            tool="test",
            rows=[ResultRow(chrom="chr1", start=1, end=4)],
        )
        tsv = result.to_tsv()
        self.assertIn("chrom", tsv)
        self.assertIn("chr1", tsv)

    def test_veyra_result_text(self):
        """Test VeyraResult text serialization."""
        from schemas.canonical import VeyraResult, ResultRow

        result = VeyraResult(
            tool="test",
            rows=[ResultRow(chrom="chr1", start=1, end=4)],
            summary={"total": 1},
        )
        text = result.to_text()
        self.assertIn("Tool: test", text)
        self.assertIn("total: 1", text)


class TestGCContentInterfaceParity(unittest.TestCase):
    """Test that GC content produces equivalent results across all interfaces."""

    SEQUENCE = "GCGCGCGCGCAAAAAAAAAA"  # 10 GC + 10 AT = 0.5

    def test_python_api_gc_content(self):
        """Test Python API GC content."""
        from api import compute_gc_content

        result = compute_gc_content(self.SEQUENCE)
        self.assertEqual(result.tool, "compute_gc_content")
        self.assertEqual(result.summary["gc_content"], 0.5)
        self.assertTrue(result.summary["passes_basic_filter"])

    def test_core_service_gc_content(self):
        """Test core service GC content."""
        from core.gc import compute_gc_content
        from schemas.canonical import ComputeGCContentRequest

        request = ComputeGCContentRequest(sequence=self.SEQUENCE)
        result = compute_gc_content(request)
        self.assertEqual(result.tool, "compute_gc_content")
        self.assertEqual(result.summary["gc_content"], 0.5)

    def test_cli_gc_content(self):
        """Test CLI GC content."""
        from cli.main import main

        exit_code = main([
            "sequence", "gc",
            "--sequence", self.SEQUENCE,
            "--output-format", "json",
        ])
        self.assertEqual(exit_code, 0)

    def test_http_api_gc_content(self):
        """Test HTTP API GC content."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/sequence/gc", json={
            "sequence": self.SEQUENCE,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tool"], "compute_gc_content")
        self.assertEqual(data["summary"]["gc_content"], 0.5)

    def test_mcp_gc_content(self):
        """Test MCP GC content."""
        from mcp.tools.compute_gc_content import compute_gc_content

        result = compute_gc_content(self.SEQUENCE)
        self.assertEqual(result.tool, "compute_gc_content")
        self.assertEqual(result.summary["gc_content"], 0.5)

    def test_all_interfaces_produce_same_gc(self):
        """Verify all interfaces produce equivalent GC results."""
        from api import compute_gc_content
        from core.gc import compute_gc_content as core_gc
        from schemas.canonical import ComputeGCContentRequest
        from mcp.tools.compute_gc_content import compute_gc_content as mcp_gc
        from http_api.app import app
        from fastapi.testclient import TestClient

        # Python API
        api_result = compute_gc_content(self.SEQUENCE)

        # Core service
        core_result = core_gc(ComputeGCContentRequest(sequence=self.SEQUENCE))

        # MCP
        mcp_result = mcp_gc(self.SEQUENCE)

        # HTTP API
        client = TestClient(app)
        http_response = client.post("/sequence/gc", json={"sequence": self.SEQUENCE})
        http_data = http_response.json()

        # All should have the same GC content
        self.assertEqual(api_result.summary["gc_content"], core_result.summary["gc_content"])
        self.assertEqual(api_result.summary["gc_content"], mcp_result.summary["gc_content"])
        self.assertEqual(api_result.summary["gc_content"], http_data["summary"]["gc_content"])


class TestHomopolymerInterfaceParity(unittest.TestCase):
    """Test that homopolymer analysis produces equivalent results across all interfaces."""

    SEQUENCE = "ACGTTTTACGTGGGGACGT"

    def test_python_api_homopolymer(self):
        """Test Python API homopolymer."""
        from api import check_homopolymer_runs

        result = check_homopolymer_runs(self.SEQUENCE)
        self.assertEqual(result.tool, "check_homopolymer_runs")
        self.assertTrue(result.summary["polyT_flag"])
        self.assertTrue(result.summary["polyG_flag"])

    def test_core_service_homopolymer(self):
        """Test core service homopolymer."""
        from core.homopolymer import check_homopolymer_runs
        from schemas.canonical import CheckHomopolymerRunsRequest

        request = CheckHomopolymerRunsRequest(sequence=self.SEQUENCE)
        result = check_homopolymer_runs(request)
        self.assertEqual(result.tool, "check_homopolymer_runs")
        self.assertTrue(result.summary["polyT_flag"])

    def test_cli_homopolymer(self):
        """Test CLI homopolymer."""
        from cli.main import main

        exit_code = main([
            "sequence", "homopolymer",
            "--sequence", self.SEQUENCE,
            "--output-format", "json",
        ])
        self.assertEqual(exit_code, 0)

    def test_http_api_homopolymer(self):
        """Test HTTP API homopolymer."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/sequence/homopolymer", json={
            "sequence": self.SEQUENCE,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tool"], "check_homopolymer_runs")
        self.assertTrue(data["summary"]["polyT_flag"])

    def test_mcp_homopolymer(self):
        """Test MCP homopolymer."""
        from mcp.tools.check_homopolymer_runs import check_homopolymer_runs

        result = check_homopolymer_runs(self.SEQUENCE)
        self.assertEqual(result.tool, "check_homopolymer_runs")
        self.assertTrue(result.summary["polyT_flag"])

    def test_all_interfaces_produce_same_homopolymer(self):
        """Verify all interfaces produce equivalent homopolymer results."""
        from api import check_homopolymer_runs
        from core.homopolymer import check_homopolymer_runs as core_homo
        from schemas.canonical import CheckHomopolymerRunsRequest
        from mcp.tools.check_homopolymer_runs import check_homopolymer_runs as mcp_homo
        from http_api.app import app
        from fastapi.testclient import TestClient

        # Python API
        api_result = check_homopolymer_runs(self.SEQUENCE)

        # Core service
        core_result = core_homo(CheckHomopolymerRunsRequest(sequence=self.SEQUENCE))

        # MCP
        mcp_result = mcp_homo(self.SEQUENCE)

        # HTTP API
        client = TestClient(app)
        http_response = client.post("/sequence/homopolymer", json={"sequence": self.SEQUENCE})
        http_data = http_response.json()

        # All should agree on polyT and polyG flags
        self.assertEqual(api_result.summary["polyT_flag"], core_result.summary["polyT_flag"])
        self.assertEqual(api_result.summary["polyT_flag"], mcp_result.summary["polyT_flag"])
        self.assertEqual(api_result.summary["polyT_flag"], http_data["summary"]["polyT_flag"])

        self.assertEqual(api_result.summary["polyG_flag"], core_result.summary["polyG_flag"])
        self.assertEqual(api_result.summary["polyG_flag"], mcp_result.summary["polyG_flag"])
        self.assertEqual(api_result.summary["polyG_flag"], http_data["summary"]["polyG_flag"])


class TestMeltingTempInterfaceParity(unittest.TestCase):
    """Test that melting temperature produces equivalent results across all interfaces."""

    SEQUENCE = "GCGCGCGCGCGCGCGCGCGC"

    def test_python_api_tm(self):
        """Test Python API melting temp."""
        from api import compute_melting_temp

        result = compute_melting_temp(self.SEQUENCE)
        self.assertEqual(result.tool, "compute_melting_temp")
        self.assertIsNotNone(result.summary["tm_celsius"])

    def test_core_service_tm(self):
        """Test core service melting temp."""
        from core.tm import compute_melting_temp
        from schemas.canonical import ComputeMeltingTempRequest

        request = ComputeMeltingTempRequest(sequence=self.SEQUENCE)
        result = compute_melting_temp(request)
        self.assertEqual(result.tool, "compute_melting_temp")
        self.assertIsNotNone(result.summary["tm_celsius"])

    def test_cli_tm(self):
        """Test CLI melting temp."""
        from cli.main import main

        exit_code = main([
            "sequence", "tm",
            "--sequence", self.SEQUENCE,
            "--output-format", "json",
        ])
        self.assertEqual(exit_code, 0)

    def test_http_api_tm(self):
        """Test HTTP API melting temp."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/sequence/tm", json={
            "sequence": self.SEQUENCE,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tool"], "compute_melting_temp")
        self.assertIsNotNone(data["summary"]["tm_celsius"])

    def test_mcp_tm(self):
        """Test MCP melting temp."""
        from mcp.tools.compute_melting_temp import compute_melting_temp

        result = compute_melting_temp(self.SEQUENCE)
        self.assertEqual(result.tool, "compute_melting_temp")
        self.assertIsNotNone(result.summary["tm_celsius"])

    def test_all_interfaces_produce_same_tm(self):
        """Verify all interfaces produce equivalent Tm results."""
        from api import compute_melting_temp
        from core.tm import compute_melting_temp as core_tm
        from schemas.canonical import ComputeMeltingTempRequest
        from mcp.tools.compute_melting_temp import compute_melting_temp as mcp_tm
        from http_api.app import app
        from fastapi.testclient import TestClient

        # Python API
        api_result = compute_melting_temp(self.SEQUENCE)

        # Core service
        core_result = core_tm(ComputeMeltingTempRequest(sequence=self.SEQUENCE))

        # MCP
        mcp_result = mcp_tm(self.SEQUENCE)

        # HTTP API
        client = TestClient(app)
        http_response = client.post("/sequence/tm", json={"sequence": self.SEQUENCE})
        http_data = http_response.json()

        # All should have the same Tm value
        self.assertEqual(api_result.summary["tm_celsius"], core_result.summary["tm_celsius"])
        self.assertEqual(api_result.summary["tm_celsius"], mcp_result.summary["tm_celsius"])
        self.assertEqual(api_result.summary["tm_celsius"], http_data["summary"]["tm_celsius"])


class TestSecondaryStructureInterfaceParity(unittest.TestCase):
    """Test that secondary structure produces equivalent results across all interfaces."""

    SEQUENCE = "GCGCGCGCGCGCGCGCGCGC"

    def test_python_api_secondary_structure(self):
        """Test Python API secondary structure."""
        from api import compute_secondary_structure

        result = compute_secondary_structure(self.SEQUENCE)
        self.assertEqual(result.tool, "compute_secondary_structure")
        # May have errors if ViennaRNA unavailable — that's expected

    def test_core_service_secondary_structure(self):
        """Test core service secondary structure."""
        from core.ss import compute_secondary_structure
        from schemas.canonical import ComputeSecondaryStructureRequest

        request = ComputeSecondaryStructureRequest(sequence=self.SEQUENCE)
        result = compute_secondary_structure(request)
        self.assertEqual(result.tool, "compute_secondary_structure")

    def test_cli_secondary_structure(self):
        """Test CLI secondary structure."""
        from cli.main import main
        from mcp.tools.compute_secondary_structure import _RNA_AVAILABLE

        exit_code = main([
            "sequence", "secondary-structure",
            "--sequence", self.SEQUENCE,
            "--output-format", "json",
        ])
        # Exit code 1 is expected when ViennaRNA is unavailable (error reported)
        if _RNA_AVAILABLE:
            self.assertEqual(exit_code, 0)
        else:
            self.assertEqual(exit_code, 1)

    def test_http_api_secondary_structure(self):
        """Test HTTP API secondary structure."""
        from http_api.app import app
        from fastapi.testclient import TestClient
        from mcp.tools.compute_secondary_structure import _RNA_AVAILABLE

        client = TestClient(app)
        response = client.post("/sequence/secondary-structure", json={
            "sequence": self.SEQUENCE,
        })
        if _RNA_AVAILABLE:
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["tool"], "compute_secondary_structure")
        else:
            # 400 is expected when ViennaRNA is unavailable
            self.assertEqual(response.status_code, 400)

    def test_mcp_secondary_structure(self):
        """Test MCP secondary structure."""
        from mcp.tools.compute_secondary_structure import compute_secondary_structure

        result = compute_secondary_structure(self.SEQUENCE)
        self.assertEqual(result.tool, "compute_secondary_structure")

    def test_all_interfaces_produce_same_secondary_structure(self):
        """Verify all interfaces produce equivalent secondary structure results."""
        from api import compute_secondary_structure
        from core.ss import compute_secondary_structure as core_ss
        from schemas.canonical import ComputeSecondaryStructureRequest
        from mcp.tools.compute_secondary_structure import (
            compute_secondary_structure as mcp_ss,
            _RNA_AVAILABLE,
        )
        from http_api.app import app
        from fastapi.testclient import TestClient

        # Python API
        api_result = compute_secondary_structure(self.SEQUENCE)

        # Core service
        core_result = core_ss(ComputeSecondaryStructureRequest(sequence=self.SEQUENCE))

        # MCP
        mcp_result = mcp_ss(self.SEQUENCE)

        # All should have the same tool name
        self.assertEqual(api_result.tool, core_result.tool)
        self.assertEqual(api_result.tool, mcp_result.tool)

        # If ViennaRNA is available, MFE values should match
        if _RNA_AVAILABLE and not api_result.errors:
            self.assertEqual(api_result.summary["mfe_kcal_mol"], core_result.summary["mfe_kcal_mol"])
            self.assertEqual(api_result.summary["mfe_kcal_mol"], mcp_result.summary["mfe_kcal_mol"])

            # HTTP API
            client = TestClient(app)
            http_response = client.post("/sequence/secondary-structure", json={"sequence": self.SEQUENCE})
            self.assertEqual(http_response.status_code, 200)
            http_data = http_response.json()
            self.assertEqual(api_result.tool, http_data["tool"])
            self.assertEqual(api_result.summary["mfe_kcal_mol"], http_data["summary"]["mfe_kcal_mol"])
        else:
            # When ViennaRNA is unavailable, all should return errors
            self.assertTrue(api_result.errors)
            self.assertTrue(core_result.errors)
            self.assertTrue(mcp_result.errors)


class TestPositionalFeaturesInterfaceParity(unittest.TestCase):
    """Test that positional features produces equivalent results across all interfaces."""

    SEQUENCE = "GCGCGCGCGCGCGCGCGCGG"

    def test_python_api_positional_features(self):
        """Test Python API positional features."""
        from api import compute_positional_features

        result = compute_positional_features(self.SEQUENCE)
        self.assertEqual(result.tool, "compute_positional_features")
        self.assertEqual(result.summary["spacer_length"], 20)
        self.assertIn("onehot", result.summary)

    def test_core_service_positional_features(self):
        """Test core service positional features."""
        from core.positional_features import compute_positional_features
        from schemas.canonical import ComputePositionalFeaturesRequest

        request = ComputePositionalFeaturesRequest(sequence=self.SEQUENCE)
        result = compute_positional_features(request)
        self.assertEqual(result.tool, "compute_positional_features")
        self.assertEqual(result.summary["spacer_length"], 20)

    def test_cli_positional_features(self):
        """Test CLI positional features."""
        from cli.main import main

        exit_code = main([
            "sequence", "positional-features",
            "--sequence", self.SEQUENCE,
            "--output-format", "json",
        ])
        self.assertEqual(exit_code, 0)

    def test_http_api_positional_features(self):
        """Test HTTP API positional features."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/sequence/positional-features", json={
            "sequence": self.SEQUENCE,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tool"], "compute_positional_features")
        self.assertEqual(data["summary"]["spacer_length"], 20)

    def test_mcp_positional_features(self):
        """Test MCP positional features."""
        from mcp.tools.compute_positional_features import compute_positional_features

        result = compute_positional_features(self.SEQUENCE)
        self.assertEqual(result.tool, "compute_positional_features")
        self.assertEqual(result.summary["spacer_length"], 20)

    def test_all_interfaces_produce_same_positional_features(self):
        """Verify all interfaces produce equivalent positional features."""
        from api import compute_positional_features
        from core.positional_features import compute_positional_features as core_pf
        from schemas.canonical import ComputePositionalFeaturesRequest
        from mcp.tools.compute_positional_features import compute_positional_features as mcp_pf
        from http_api.app import app
        from fastapi.testclient import TestClient

        # Python API
        api_result = compute_positional_features(self.SEQUENCE)

        # Core service
        core_result = core_pf(ComputePositionalFeaturesRequest(sequence=self.SEQUENCE))

        # MCP
        mcp_result = mcp_pf(self.SEQUENCE)

        # All should have the same tool name
        self.assertEqual(api_result.tool, core_result.tool)
        self.assertEqual(api_result.tool, mcp_result.tool)

        # Feature values should match
        self.assertEqual(api_result.summary["spacer"], core_result.summary["spacer"])
        self.assertEqual(api_result.summary["spacer"], mcp_result.summary["spacer"])
        self.assertEqual(api_result.summary["position20_base"], core_result.summary["position20_base"])
        self.assertEqual(api_result.summary["position20_base"], mcp_result.summary["position20_base"])
        self.assertEqual(api_result.summary["position20_bias_flag"], core_result.summary["position20_bias_flag"])
        self.assertEqual(api_result.summary["position20_bias_flag"], mcp_result.summary["position20_bias_flag"])

        # One-hot should match
        self.assertEqual(len(api_result.summary["onehot"]), len(core_result.summary["onehot"]))
        self.assertEqual(len(api_result.summary["onehot"]), len(mcp_result.summary["onehot"]))
        for o_api, o_core, o_mcp in zip(
            api_result.summary["onehot"], core_result.summary["onehot"], mcp_result.summary["onehot"]
        ):
            self.assertEqual(o_api["encoding"], o_core["encoding"])
            self.assertEqual(o_api["encoding"], o_mcp["encoding"])

        # HTTP API
        client = TestClient(app)
        http_response = client.post("/sequence/positional-features", json={"sequence": self.SEQUENCE})
        self.assertEqual(http_response.status_code, 200)
        http_data = http_response.json()
        self.assertEqual(api_result.tool, http_data["tool"])
        self.assertEqual(api_result.summary["spacer"], http_data["summary"]["spacer"])
        self.assertEqual(api_result.summary["position20_base"], http_data["summary"]["position20_base"])
        self.assertEqual(len(api_result.summary["onehot"]), len(http_data["summary"]["onehot"]))


class TestDinucleotideCompositionInterfaceParity(unittest.TestCase):
    """Test that dinucleotide composition produces equivalent results across all interfaces."""

    SEQUENCE = "GCGCGCGCGCGCGCGCGCGG"

    def test_python_api_dinucleotide_composition(self):
        """Test Python API dinucleotide composition."""
        from api import compute_dinucleotide_composition

        result = compute_dinucleotide_composition(self.SEQUENCE)
        self.assertEqual(result.tool, "compute_dinucleotide_composition")
        self.assertEqual(result.summary["spacer_length"], 20)
        self.assertEqual(result.summary["total_windows"], 19)

    def test_core_service_dinucleotide_composition(self):
        """Test core service dinucleotide composition."""
        from core.dinucleotide import compute_dinucleotide_composition
        from schemas.canonical import ComputeDinucleotideCompositionRequest

        request = ComputeDinucleotideCompositionRequest(sequence=self.SEQUENCE)
        result = compute_dinucleotide_composition(request)
        self.assertEqual(result.tool, "compute_dinucleotide_composition")
        self.assertEqual(result.summary["spacer_length"], 20)

    def test_cli_dinucleotide_composition(self):
        """Test CLI dinucleotide composition."""
        from cli.main import main

        exit_code = main([
            "sequence", "dinucleotide-composition",
            "--sequence", self.SEQUENCE,
            "--output-format", "json",
        ])
        self.assertEqual(exit_code, 0)

    def test_http_api_dinucleotide_composition(self):
        """Test HTTP API dinucleotide composition."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/sequence/dinucleotide-composition", json={
            "sequence": self.SEQUENCE,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tool"], "compute_dinucleotide_composition")
        self.assertEqual(data["summary"]["spacer_length"], 20)

    def test_mcp_dinucleotide_composition(self):
        """Test MCP dinucleotide composition."""
        from mcp.tools.compute_dinucleotide_composition import compute_dinucleotide_composition

        result = compute_dinucleotide_composition(self.SEQUENCE)
        self.assertEqual(result.tool, "compute_dinucleotide_composition")
        self.assertEqual(result.summary["spacer_length"], 20)

    def test_all_interfaces_produce_same_dinucleotide_composition(self):
        """Verify all interfaces produce equivalent dinucleotide composition."""
        from api import compute_dinucleotide_composition
        from core.dinucleotide import compute_dinucleotide_composition as core_dinuc
        from schemas.canonical import ComputeDinucleotideCompositionRequest
        from mcp.tools.compute_dinucleotide_composition import compute_dinucleotide_composition as mcp_dinuc
        from http_api.app import app
        from fastapi.testclient import TestClient

        # Python API
        api_result = compute_dinucleotide_composition(self.SEQUENCE)

        # Core service
        core_result = core_dinuc(ComputeDinucleotideCompositionRequest(sequence=self.SEQUENCE))

        # MCP
        mcp_result = mcp_dinuc(self.SEQUENCE)

        # All should have the same tool name
        self.assertEqual(api_result.tool, core_result.tool)
        self.assertEqual(api_result.tool, mcp_result.tool)

        # Feature values should match
        self.assertEqual(api_result.summary["counts"], core_result.summary["counts"])
        self.assertEqual(api_result.summary["counts"], mcp_result.summary["counts"])
        self.assertEqual(api_result.summary["total_windows"], core_result.summary["total_windows"])
        self.assertEqual(api_result.summary["total_windows"], mcp_result.summary["total_windows"])

        # HTTP API
        client = TestClient(app)
        http_response = client.post("/sequence/dinucleotide-composition", json={"sequence": self.SEQUENCE})
        self.assertEqual(http_response.status_code, 200)
        http_data = http_response.json()
        self.assertEqual(api_result.tool, http_data["tool"])
        self.assertEqual(api_result.summary["counts"], http_data["summary"]["counts"])
        self.assertEqual(api_result.summary["total_windows"], http_data["summary"]["total_windows"])


class TestSeedGCInterfaceParity(unittest.TestCase):
    """Test that seed GC produces equivalent results across all interfaces."""

    SEQUENCE = "GCGCGCGCGCGCGCGCGCGG"

    def test_python_api_seed_gc(self):
        """Test Python API seed GC."""
        from api import compute_seed_gc

        result = compute_seed_gc(self.SEQUENCE)
        self.assertEqual(result.tool, "compute_seed_gc")
        self.assertEqual(result.summary["seed_region_length"], 10)
        self.assertEqual(result.summary["seed_start_position"], 11)
        self.assertEqual(result.summary["seed_end_position"], 20)

    def test_core_service_seed_gc(self):
        """Test core service seed GC."""
        from core.seed_gc import compute_seed_gc
        from schemas.canonical import ComputeSeedGCRequest

        request = ComputeSeedGCRequest(sequence=self.SEQUENCE)
        result = compute_seed_gc(request)
        self.assertEqual(result.tool, "compute_seed_gc")
        self.assertEqual(result.summary["seed_region_length"], 10)

    def test_cli_seed_gc(self):
        """Test CLI seed GC."""
        from cli.main import main

        exit_code = main([
            "sequence", "seed-gc",
            "--sequence", self.SEQUENCE,
            "--output-format", "json",
        ])
        self.assertEqual(exit_code, 0)

    def test_http_api_seed_gc(self):
        """Test HTTP API seed GC."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/sequence/seed-gc", json={
            "sequence": self.SEQUENCE,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tool"], "compute_seed_gc")
        self.assertEqual(data["summary"]["seed_region_length"], 10)

    def test_mcp_seed_gc(self):
        """Test MCP seed GC."""
        from mcp.tools.compute_seed_gc import compute_seed_gc

        result = compute_seed_gc(self.SEQUENCE)
        self.assertEqual(result.tool, "compute_seed_gc")
        self.assertEqual(result.summary["seed_region_length"], 10)

    def test_all_interfaces_produce_same_seed_gc(self):
        """Verify all interfaces produce equivalent seed GC results."""
        from api import compute_seed_gc
        from core.seed_gc import compute_seed_gc as core_seed_gc
        from schemas.canonical import ComputeSeedGCRequest
        from mcp.tools.compute_seed_gc import compute_seed_gc as mcp_seed_gc
        from http_api.app import app
        from fastapi.testclient import TestClient

        # Python API
        api_result = compute_seed_gc(self.SEQUENCE)

        # Core service
        core_result = core_seed_gc(ComputeSeedGCRequest(sequence=self.SEQUENCE))

        # MCP
        mcp_result = mcp_seed_gc(self.SEQUENCE)

        # All should have the same tool name
        self.assertEqual(api_result.tool, core_result.tool)
        self.assertEqual(api_result.tool, mcp_result.tool)

        # Feature values should match
        self.assertEqual(api_result.summary["seed_gc_content"], core_result.summary["seed_gc_content"])
        self.assertEqual(api_result.summary["seed_gc_content"], mcp_result.summary["seed_gc_content"])
        self.assertEqual(api_result.summary["passes_seed_filter"], core_result.summary["passes_seed_filter"])
        self.assertEqual(api_result.summary["passes_seed_filter"], mcp_result.summary["passes_seed_filter"])
        self.assertEqual(api_result.summary["seed_start_position"], core_result.summary["seed_start_position"])
        self.assertEqual(api_result.summary["seed_start_position"], mcp_result.summary["seed_start_position"])

        # HTTP API
        client = TestClient(app)
        http_response = client.post("/sequence/seed-gc", json={"sequence": self.SEQUENCE})
        self.assertEqual(http_response.status_code, 200)
        http_data = http_response.json()
        self.assertEqual(api_result.tool, http_data["tool"])
        self.assertEqual(api_result.summary["seed_gc_content"], http_data["summary"]["seed_gc_content"])
        self.assertEqual(api_result.summary["passes_seed_filter"], http_data["summary"]["passes_seed_filter"])


class TestAnalyzeMismatchSeedInterfaceParity(unittest.TestCase):
    """Test that analyze_mismatch_seed produces equivalent results across interfaces."""

    SPACER = "GCGCGCGCGCGCGCGCGCGC"
    CANDIDATE = "GCGCGCGCGCGCGCGCGCGC"

    def test_python_api_analyze_seed(self):
        """Test Python API analyze_mismatch_seed."""
        from api import analyze_mismatch_seed

        result = analyze_mismatch_seed(
            spacer_sequence=self.SPACER,
            candidate_sequence=self.CANDIDATE,
        )
        self.assertEqual(result.tool, "analyze_mismatch_seed")
        self.assertEqual(result.summary["total_mismatches"], 0)

    def test_mcp_analyze_seed(self):
        """Test MCP analyze_mismatch_seed."""
        from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed

        result = analyze_mismatch_seed(
            spacer_sequence=self.SPACER,
            candidate_sequence=self.CANDIDATE,
        )
        self.assertEqual(result.tool, "analyze_mismatch_seed")
        self.assertEqual(result.summary["total_mismatches"], 0)

    def test_http_api_analyze_seed(self):
        """Test HTTP API analyze_mismatch_seed."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/offtarget/analyze-seed", json={
            "spacer_sequence": self.SPACER,
            "candidate_sequence": self.CANDIDATE,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tool"], "analyze_mismatch_seed")
        self.assertEqual(data["summary"]["total_mismatches"], 0)

    def test_all_interfaces_produce_same_result(self):
        """Verify all interfaces produce equivalent analyze_mismatch_seed results."""
        from api import analyze_mismatch_seed
        from mcp.tools.analyze_mismatch_seed import analyze_mismatch_seed as mcp_analyze
        from http_api.app import app
        from fastapi.testclient import TestClient

        # Create a candidate with a mismatch
        candidate = "GCGCGCGCGCGCGCGCGCCA"

        # Python API
        api_result = analyze_mismatch_seed(
            spacer_sequence=self.SPACER,
            candidate_sequence=candidate,
        )

        # MCP
        mcp_result = mcp_analyze(
            spacer_sequence=self.SPACER,
            candidate_sequence=candidate,
        )

        # All should have the same tool name
        self.assertEqual(api_result.tool, mcp_result.tool)

        # Feature values should match
        self.assertEqual(api_result.summary["total_mismatches"], mcp_result.summary["total_mismatches"])
        self.assertEqual(api_result.summary["seed_mismatch_count"], mcp_result.summary["seed_mismatch_count"])

        # HTTP API
        client = TestClient(app)
        http_response = client.post("/offtarget/analyze-seed", json={
            "spacer_sequence": self.SPACER,
            "candidate_sequence": candidate,
        })
        self.assertEqual(http_response.status_code, 200)
        http_data = http_response.json()
        self.assertEqual(api_result.tool, http_data["tool"])
        self.assertEqual(api_result.summary["total_mismatches"], http_data["summary"]["total_mismatches"])


class TestCasOFFinderInterfaceParity(unittest.TestCase):
    """Test that cas_offinder_search produces equivalent results across interfaces."""

    SPACER = "GCGCGCGCGCGCGCGCGCGC"

    def test_python_api_cas_offinder(self):
        """Test Python API cas_offinder_search via offtarget_search."""
        from api import search_offtargets

        result = search_offtargets(
            spacer_sequence=self.SPACER,
            genome_id="ecoli_k12_mg1655",
            pam_pattern="NGG",
            max_mismatches=3,
            allow_bulge=True,
            max_dna_bulge=0,
            max_rna_bulge=0,
            backend="cas_offinder",
        )
        self.assertEqual(result.tool, "cas_offinder_search")
        self.assertEqual(result.summary["backend"], "cas_offinder")

    def test_mcp_cas_offinder(self):
        """Test MCP cas_offinder_search."""
        from mcp.tools.cas_offinder_search import cas_offinder_search

        result = cas_offinder_search(
            spacer_sequence=self.SPACER,
            genome_id="ecoli_k12_mg1655",
            pam_pattern="NGG",
            max_mismatches=3,
            max_dna_bulge=0,
            max_rna_bulge=0,
        )
        self.assertEqual(result.tool, "cas_offinder_search")
        self.assertEqual(result.summary["backend"], "cas_offinder")

    def test_http_api_cas_offinder(self):
        """Test HTTP API cas_offinder_search via offtarget/search."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/offtarget/search", json={
            "spacer_sequence": self.SPACER,
            "genome_id": "ecoli_k12_mg1655",
            "pam_pattern": "NGG",
            "max_mismatches": 3,
            "allow_bulge": True,
            "max_dna_bulge": 0,
            "max_rna_bulge": 0,
            "backend": "cas_offinder",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tool"], "cas_offinder_search")
        self.assertEqual(data["summary"]["backend"], "cas_offinder")

    def test_bwa_backend_still_works(self):
        """Test that BWA backend still works for mismatch-only search."""
        from api import search_offtargets

        result = search_offtargets(
            spacer_sequence=self.SPACER,
            genome_id="ecoli_k12_mg1655",
            pam_pattern="NGG",
            max_mismatches=3,
            allow_bulge=False,
            backend="bwa",
        )
        self.assertEqual(result.tool, "offtarget_search")
        self.assertEqual(result.summary["backend"], "bwa-aln")


if __name__ == "__main__":
    unittest.main()


class TestOnTargetEfficiencyInterfaceParity(unittest.TestCase):
    """Test that predict_ontarget_efficiency produces equivalent results across interfaces."""

    CONTEXT_30MER = "AAAAGGCGCGCGCGCGCGCGCGGGTTTAAA"  # 4+20+3+3 = 30

    def test_python_api_ontarget_rule_set_2(self):
        """Test Python API predict_ontarget_efficiency with rule_set_2.
        
        Explicit Rule Set 2 request: model is incompatible (sklearn version conflict),
        returns error - explicit models NEVER fall back.
        """
        from api import predict_ontarget_efficiency

        result = predict_ontarget_efficiency(
            context_sequence=self.CONTEXT_30MER,
            model="rule_set_2",
        )
        self.assertEqual(result.tool, "predict_ontarget_efficiency")
        self.assertTrue(result.errors)
        self.assertEqual(result.summary["confidence_flag"], "model_unavailable")
        self.assertEqual(result.summary["requested_model"], "rule_set_2")
        self.assertEqual(result.summary["selection"]["selection_status"], "failed")

    def test_python_api_ontarget_rule_set_3(self):
        """Test explicit Rule Set 3 selection when its runtime is available."""
        from api import predict_ontarget_efficiency

        result = predict_ontarget_efficiency(
            context_sequence=self.CONTEXT_30MER,
            model="rule_set_3",
        )
        self.assertEqual(result.tool, "predict_ontarget_efficiency")
        if result.errors:
            self.assertEqual(result.summary["confidence_flag"], "model_unavailable")
        else:
            self.assertEqual(result.summary["model_used"], "rule_set_3")
            self.assertIn("ontarget_score_rule_set_3", result.summary)

    def test_python_api_ontarget_rule_set_2(self):
        """Test explicit Rule Set 2 selection when its runtime is available.
        
        Rule Set 2 requires Python 2.7 with scikit-learn 0.17.1 (Azimuth 2.0).
        In the current environment without Python 2.7, this should return an error.
        """
        from api import predict_ontarget_efficiency

        result = predict_ontarget_efficiency(
            context_sequence=self.CONTEXT_30MER,
            model="rule_set_2",
        )
        self.assertEqual(result.tool, "predict_ontarget_efficiency")
        # Rule Set 2 should fail with model_unavailable in current environment
        self.assertTrue(result.errors)
        self.assertEqual(result.summary["confidence_flag"], "model_unavailable")
        self.assertEqual(result.summary["requested_model"], "rule_set_2")
        self.assertIn("Python 2.7", result.errors[0] or "")
        self.assertIn("scikit-learn 0.17.1", result.errors[0] or "")

    def test_rule_set_2_runtime_discovery(self):
        """Test Rule Set 2 runtime discovery functions."""
        from core.model_runtime import detect_python_runtimes, detect_conda_environments, find_compatible_python27_runtime
        
        # Test Python runtime detection
        python_runtimes = detect_python_runtimes()
        self.assertIn("python3", python_runtimes)
        self.assertIn("python27", python_runtimes)
        
        # Test Conda environment detection
        conda_envs = detect_conda_environments()
        self.assertIsInstance(conda_envs, list)
        
        # Test compatible Python 2.7 runtime
        compatible_rt = find_compatible_python27_runtime()
        # In current environment, should be None (no Python 2.7 available)
        if compatible_rt:
            self.assertIn("python_executable", compatible_rt)
            self.assertIn("2.7", compatible_rt.get("python_version", ""))

    def test_rule_set_2_adapter(self):
        """Test Rule Set 2 adapter functions."""
        from core.rule_set_2_adapter import get_rule_set_2_runtime_info, create_rule_set_2_runner_script
        
        # Test runtime info
        runtime_info = get_rule_set_2_runtime_info()
        self.assertIsInstance(runtime_info, object)
        self.assertTrue(hasattr(runtime_info, "runtime_path"))
        self.assertTrue(hasattr(runtime_info, "python_executable"))
        
        # Test runner script creation
        runner_script = create_rule_set_2_runner_script()
        self.assertIsInstance(runner_script, str)
        self.assertIn("import json", runner_script)
        self.assertIn("import sys", runner_script)
        self.assertIn("azimuth.model_comparison", runner_script)

    def test_rule_set_2_model_registry(self):
        """Test Rule Set 2 model registry information."""
        from core.model_registry import get_model_info
        
        info = get_model_info("rule_set_2")
        self.assertIsNotNone(info)
        self.assertEqual(info.model_id, "rule_set_2")
        self.assertEqual(info.version, "2.0")
        self.assertIn("Azimuth 2.0", info.source)
        self.assertIn("scikit-learn", info.dependencies)
        self.assertIn("0.17.1", info.dependencies.get("scikit-learn", ""))
        self.assertIn("Python 2.7", info.error_message or "")

    def test_rule_set_2_auto_selection_fallback(self):
        """Test that auto-selection falls back correctly when Rule Set 2 is unavailable."""
        from api import predict_ontarget_efficiency
        from core.model_registry import get_auto_model_priority

        result = predict_ontarget_efficiency(
            context_sequence=self.CONTEXT_30MER,
            model="auto",
        )
        self.assertEqual(result.tool, "predict_ontarget_efficiency")
        self.assertFalse(result.errors)
        # Should select top available verified model
        top_model = get_auto_model_priority()[0]
        self.assertEqual(result.summary["model_used"], top_model)
        self.assertEqual(result.summary["selection_status"], "selected")

    def test_python_api_ontarget_auto(self):
        """Test Python API predict_ontarget_efficiency with auto.
        
        Auto selects the highest-priority verified model.
        """
        from api import predict_ontarget_efficiency

        result = predict_ontarget_efficiency(
            context_sequence=self.CONTEXT_30MER,
            model="auto",
        )
        self.assertEqual(result.tool, "predict_ontarget_efficiency")
        self.assertFalse(result.errors)
        self.assertIn(result.summary["model_used"], ("rule_set_3", "doench_2014"))
        self.assertEqual(result.summary["selection_status"], "selected")
        self.assertIn("ontarget_score", result.summary)
        self.assertIn(result.summary["confidence_flag"], ("ok", "fallback"))

    def test_python_api_ontarget_both(self):
        """Test Python API predict_ontarget_efficiency with both (alias for auto)."""
        from api import predict_ontarget_efficiency

        result = predict_ontarget_efficiency(
            context_sequence=self.CONTEXT_30MER,
            model="both",
        )
        self.assertEqual(result.tool, "predict_ontarget_efficiency")
        self.assertFalse(result.errors)
        self.assertIn(result.summary["model_used"], ("rule_set_3", "doench_2014"))
        self.assertEqual(result.summary["selection_status"], "selected")

    def test_python_api_ontarget_invalid_model(self):
        """Test Python API predict_ontarget_efficiency with invalid model."""
        from api import predict_ontarget_efficiency

        result = predict_ontarget_efficiency(
            context_sequence=self.CONTEXT_30MER,
            model="invalid_model",
        )
        self.assertTrue(result.errors)

    def test_python_api_ontarget_context_length_mismatch(self):
        """Test Python API predict_ontarget_efficiency with wrong context length."""
        from api import predict_ontarget_efficiency

        result = predict_ontarget_efficiency(
            context_sequence="AAAAGGCGCGCGCGCGCGCGCGGG",  # 24 nt, not 30
            model="auto",
        )
        self.assertTrue(result.errors)
        self.assertEqual(result.summary["confidence_flag"], "context_length_mismatch")

    def test_python_api_ontarget_normalize_score(self):
        """Test Python API predict_ontarget_efficiency with normalize_score."""
        from api import predict_ontarget_efficiency

        result = predict_ontarget_efficiency(
            context_sequence=self.CONTEXT_30MER,
            model="auto",
            normalize_score=True,
        )
        if result.summary["model_used"] == "rule_set_3":
            self.assertFalse(result.summary["normalized"])
            self.assertTrue(result.warnings)
        else:
            self.assertTrue(result.summary["normalized"])

    def test_python_api_ontarget_round_decimals(self):
        """Test Python API predict_ontarget_efficiency with custom rounding."""
        from api import predict_ontarget_efficiency

        result = predict_ontarget_efficiency(
            context_sequence=self.CONTEXT_30MER,
            model="auto",
            round_decimals=5,
        )
        self.assertEqual(result.summary["round_decimals"], 5)

    def test_core_service_ontarget(self):
        """Test core service predict_ontarget_efficiency with auto."""
        from core.ontarget import predict_ontarget_efficiency
        from schemas.canonical import ComputeOnTargetEfficiencyRequest

        request = ComputeOnTargetEfficiencyRequest(
            context_sequence=self.CONTEXT_30MER,
            model="auto",
        )
        result = predict_ontarget_efficiency(request)
        self.assertEqual(result.tool, "predict_ontarget_efficiency")
        self.assertFalse(result.errors)
        self.assertIn(result.summary["model_used"], ("rule_set_3", "doench_2014"))
        self.assertIn("ontarget_score", result.summary)

    def test_cli_ontarget(self):
        """Test CLI predict_ontarget_efficiency with auto."""
        from cli.main import main

        exit_code = main([
            "score", "on-target",
            "--context-sequence", self.CONTEXT_30MER,
            "--model", "auto",
            "--output-format", "json",
        ])
        self.assertEqual(exit_code, 0)

    def test_http_api_ontarget(self):
        """Test HTTP API predict_ontarget_efficiency with auto."""
        from http_api.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/score/ontarget", json={
            "context_sequence": self.CONTEXT_30MER,
            "model": "auto",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tool"], "predict_ontarget_efficiency")
        self.assertIn(data["summary"]["model_used"], ("rule_set_3", "doench_2014"))
        self.assertIn("ontarget_score", data["summary"])

    def test_mcp_ontarget(self):
        """Test MCP predict_ontarget_efficiency with auto."""
        from mcp.tools.predict_ontarget_efficiency import predict_ontarget_efficiency_tool

        result = predict_ontarget_efficiency_tool(
            context_sequence=self.CONTEXT_30MER,
            model="auto",
        )
        self.assertEqual(result.tool, "predict_ontarget_efficiency")
        self.assertIn(result.summary["model_used"], ("rule_set_3", "doench_2014"))
        self.assertIn("ontarget_score", result.summary)

    def test_all_interfaces_produce_same_ontarget(self):
        """Verify all interfaces produce equivalent on-target results with auto."""
        from api import predict_ontarget_efficiency
        from core.ontarget import predict_ontarget_efficiency as core_ontarget
        from schemas.canonical import ComputeOnTargetEfficiencyRequest
        from mcp.tools.predict_ontarget_efficiency import predict_ontarget_efficiency_tool as mcp_ontarget
        from http_api.app import app
        from fastapi.testclient import TestClient

        # Python API
        api_result = predict_ontarget_efficiency(
            context_sequence=self.CONTEXT_30MER,
            model="auto",
        )

        # Core service
        core_result = core_ontarget(ComputeOnTargetEfficiencyRequest(
            context_sequence=self.CONTEXT_30MER,
            model="auto",
        ))

        # MCP
        mcp_result = mcp_ontarget(
            context_sequence=self.CONTEXT_30MER,
            model="auto",
        )

        # HTTP API
        client = TestClient(app)
        http_response = client.post("/score/ontarget", json={
            "context_sequence": self.CONTEXT_30MER,
            "model": "auto",
        })
        http_data = http_response.json()

        # All should have the same score
        self.assertEqual(api_result.summary["ontarget_score"],
                        core_result.summary["ontarget_score"])
        self.assertEqual(api_result.summary["ontarget_score"],
                        mcp_result.summary["ontarget_score"])
        self.assertEqual(api_result.summary["ontarget_score"],
                        http_data["summary"]["ontarget_score"])

        # All should have the same model_used
        self.assertEqual(api_result.summary["model_used"], 
                        core_result.summary["model_used"])
        self.assertEqual(api_result.summary["model_used"], 
                        mcp_result.summary["model_used"])
        self.assertEqual(api_result.summary["model_used"], 
                        http_data["summary"]["model_used"])

        # All should have the same fallback chain
        self.assertEqual(api_result.summary["fallback_chain"],
                        core_result.summary["fallback_chain"])
        self.assertEqual(api_result.summary["fallback_chain"],
                        mcp_result.summary["fallback_chain"])
        self.assertEqual(api_result.summary["fallback_chain"],
                        http_data["summary"]["fallback_chain"])


class TestModelRuntimeProvisioning(unittest.TestCase):
    """Test model runtime provisioning system."""

    def test_get_model_spec(self):
        """Test getting model specification."""
        from core.model_runtime import get_model_spec

        spec = get_model_spec("rule_set_2")
        self.assertIsNotNone(spec)
        self.assertEqual(spec["model_id"], "rule_set_2")
        self.assertIn("dependency_spec", spec)
        self.assertIn("verification_case", spec)

        spec = get_model_spec("doench_2014")
        self.assertIsNotNone(spec)
        self.assertEqual(spec["model_id"], "doench_2014")

        spec = get_model_spec("unknown_model")
        self.assertIsNone(spec)

    def test_get_model_status(self):
        """Test getting model runtime status."""
        from core.model_runtime import get_model_status

        status = get_model_status("doench_2014")
        self.assertIn("state", status)
        self.assertIn("runtime_path", status)
        self.assertIn("runtime_action", status)

    def test_list_model_runtimes(self):
        """Test listing all model runtimes."""
        from core.model_runtime import list_model_runtimes

        runtimes = list_model_runtimes()
        self.assertEqual(len(runtimes), 3)
        model_ids = [r["model_id"] for r in runtimes]
        self.assertIn("rule_set_3", model_ids)
        self.assertIn("rule_set_2", model_ids)
        self.assertIn("doench_2014", model_ids)

    def test_doench_2014_always_verified(self):
        """Test that Doench 2014 is always verified (pure Python, no runtime needed)."""
        from core.model_runtime import get_model_status, RuntimeState
        from core.model_registry import get_model_info

        info = get_model_info("doench_2014")
        self.assertTrue(info.verified)
        self.assertEqual(info.availability, "verified")

    def test_provision_doench_2014(self):
        """Test provisioning Doench 2014 (no-op)."""
        from core.model_runtime import provision_model

        result = provision_model("doench_2014")
        self.assertEqual(result["action"], "no_provisioning_needed")

    def test_verify_model(self):
        """Test model verification."""
        from core.model_runtime import verify_model

        result = verify_model("doench_2014")
        self.assertEqual(result["verification_status"], "pass")

    def test_verify_unknown_model(self):
        """Test verification of unknown model."""
        from core.model_runtime import verify_model

        result = verify_model("invalid_model")
        self.assertIn("error", result)

    def test_provision_unknown_model(self):
        """Test provisioning unknown model."""
        from core.model_runtime import provision_model

        result = provision_model("invalid_model")
        self.assertIn("error", result)

    def test_runtime_state_constants(self):
        """Test RuntimeState constants."""
        from core.model_runtime import RuntimeState

        self.assertEqual(RuntimeState.NOT_PROVISIONED, "not_provisioned")
        self.assertEqual(RuntimeState.PROVISIONED, "provisioned")
        self.assertEqual(RuntimeState.VERIFIED, "verified")
        self.assertEqual(RuntimeState.INCOMPATIBLE, "incompatible")

    def test_cli_models_setup_doench_2014(self):
        """Test CLI models setup for Doench 2014."""
        from cli.main import main

        exit_code = main([
            "models", "setup", "doench_2014",
            "--output-format", "json",
        ])
        self.assertEqual(exit_code, 0)

    def test_cli_models_verify_doench_2014(self):
        """Test CLI models verify for Doench 2014."""
        from cli.main import main

        exit_code = main([
            "models", "verify", "doench_2014",
            "--output-format", "json",
        ])
        self.assertEqual(exit_code, 0)

    def test_cli_models_setup_unknown(self):
        """Test CLI models setup with unknown model."""
        from cli.main import main

        exit_code = main([
            "models", "setup", "invalid_model",
            "--output-format", "json",
        ])
        self.assertEqual(exit_code, 1)

    def test_cli_models_setup_all(self):
        """Test CLI models setup --all (expects non-zero since rule_set_2/3 fail)."""
        from cli.main import main

        exit_code = main([
            "models", "setup", "--all",
            "--output-format", "json",
        ])
        # Should fail because rule_set_2 and rule_set_3 cannot be provisioned
        # in this environment (dependency conflicts), only doench_2014 succeeds
        self.assertEqual(exit_code, 1)


class TestModelRuntimeHTTPAPI(unittest.TestCase):
    """Test model runtime management HTTP API endpoints."""

    def _get_client(self):
        from http_api.app import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_http_get_models(self):
        """Test GET /models endpoint."""
        client = self._get_client()
        response = client.get("/models")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("models", data)
        model_ids = [m["model_id"] for m in data["models"]]
        self.assertIn("rule_set_2", model_ids)
        self.assertIn("rule_set_3", model_ids)
        self.assertIn("doench_2014", model_ids)

    def test_http_get_model_doench_2014(self):
        """Test GET /models/{model_id} for doench_2014."""
        client = self._get_client()
        response = client.get("/models/doench_2014")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["model_id"], "doench_2014")
        self.assertTrue(data["verified"])

    def test_http_get_model_unknown(self):
        """Test GET /models/{model_id} for unknown model."""
        client = self._get_client()
        response = client.get("/models/invalid_model")
        self.assertEqual(response.status_code, 404)

    def test_http_verify_model(self):
        """Test POST /models/{model_id}/verify."""
        client = self._get_client()
        response = client.post("/models/doench_2014/verify")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    def test_http_model_status(self):
        """Test GET /models/{model_id}/status."""
        client = self._get_client()
        response = client.get("/models/doench_2014/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("state", data)

    def test_http_setup_model(self):
        """Test POST /models/{model_id}/setup."""
        client = self._get_client()
        response = client.post("/models/doench_2014/setup")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])


class TestModelRuntimeMCP(unittest.TestCase):
    """Test model runtime management MCP tools."""

    def test_mcp_models_list_runtimes(self):
        """Test MCP models_list_runtimes tool."""
        from mcp.tools.model_runtime import models_list_runtimes_tool

        result = models_list_runtimes_tool()
        self.assertEqual(result.tool, "models_list_runtimes")
        self.assertIn("runtimes", result.summary)
        self.assertEqual(len(result.summary["runtimes"]), 3)

    def test_mcp_model_status(self):
        """Test MCP model_status tool."""
        from mcp.tools.model_runtime import model_status_tool

        result = model_status_tool("doench_2014")
        self.assertEqual(result.tool, "model_status")
        self.assertEqual(result.summary["model_id"], "doench_2014")
        self.assertIn("status", result.summary)

    def test_mcp_model_status_unknown(self):
        """Test MCP model_status for unknown model."""
        from mcp.tools.model_runtime import model_status_tool

        result = model_status_tool("invalid_model")
        self.assertTrue(result.errors)

    def test_mcp_setup_model(self):
        """Test MCP setup_model tool."""
        from mcp.tools.model_runtime import setup_model_tool

        result = setup_model_tool("doench_2014")
        self.assertEqual(result.tool, "setup_model")
        self.assertEqual(result.summary["model_id"], "doench_2014")

    def test_mcp_verify_model(self):
        """Test MCP verify_model tool."""
        from mcp.tools.model_runtime import verify_model_tool

        result = verify_model_tool("doench_2014")
        self.assertEqual(result.tool, "verify_model")
        self.assertEqual(result.summary["model_id"], "doench_2014")
        self.assertEqual(result.summary["result"]["verification_status"], "pass")

    def test_mcp_verify_unknown_model(self):
        """Test MCP verify_model for unknown model."""
        from mcp.tools.model_runtime import verify_model_tool

        result = verify_model_tool("invalid_model")
        self.assertTrue(result.errors)
