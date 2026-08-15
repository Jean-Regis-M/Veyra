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

        self.assertEqual(len(TOOL_REGISTRY), 6)
        self.assertIn("pam_scan", TOOL_REGISTRY)
        self.assertIn("offtarget_search", TOOL_REGISTRY)

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
        self.assertEqual(data["total_tools"], 6)


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


if __name__ == "__main__":
    unittest.main()
