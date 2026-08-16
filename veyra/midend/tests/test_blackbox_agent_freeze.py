"""Black-box acceptance test suite for VEYRA frontend AI model capability & toolset freeze.

Operates strictly as an external client using the public HTTP API and WebSocket/SSE endpoints.
No backend or midend private imports are used during execution.
"""

import io
import json
import time
import pytest
import httpx

MIDEND_BASE_URL = "http://localhost:8080"
TIMEOUT = 30.0


@pytest.fixture
def http_client():
    return httpx.Client(base_url=MIDEND_BASE_URL, timeout=TIMEOUT)


class BlackBoxAgentClient:
    """Simulates the public VEYRA frontend AI agent client."""

    def __init__(self, client: httpx.Client):
        self.client = client

    def get_public_tools(self) -> dict:
        r = self.client.get("/tools")
        assert r.status_code == 200, f"Failed to get tools: {r.text}"
        return r.json()

    def get_public_skills(self) -> dict:
        r = self.client.get("/skills")
        assert r.status_code == 200, f"Failed to get skills: {r.text}"
        return r.json()

    def execute_sync(self, payload: dict) -> dict:
        r = self.client.post("/executions", json=payload)
        assert r.status_code in {200, 201, 202}, f"Failed to create execution: {r.text}"
        exec_id = r.json()["execution_id"]
        
        # Poll until execution finishes
        for _ in range(60):
            status_r = self.client.get(f"/executions/{exec_id}")
            assert status_r.status_code == 200
            data = status_r.json()
            if data["status"] in {"completed", "failed"}:
                return data
            time.sleep(0.1)
        raise TimeoutError(f"Execution {exec_id} timed out")

    def upload_file(self, filename: str, content: bytes, content_type: str = "text/plain") -> dict:
        files = {"file": (filename, io.BytesIO(content), content_type)}
        r = self.client.post("/inputs/file", files=files)
        assert r.status_code in {200, 201}, f"Upload failed: {r.text}"
        return r.json()

    def send_chat(self, message: str, input_ids: list[str] | None = None) -> dict:
        payload = {"message": message}
        if input_ids:
            payload["input_ids"] = input_ids
        r = self.client.post("/ai/chat", json=payload)
        assert r.status_code in {200, 201, 202}, f"Chat request failed: {r.text}"
        exec_id = r.json().get("execution_id")
        if not exec_id:
            return r.json()
        
        for _ in range(120):
            status_r = self.client.get(f"/executions/{exec_id}")
            assert status_r.status_code == 200
            data = status_r.json()
            if data["status"] in {"completed", "failed"}:
                return data
            time.sleep(0.3)
        raise TimeoutError(f"Chat execution {exec_id} timed out")


# ==============================================================================
# PHASE 1 & 2: Stack Health & Black-Box Client Setup
# ==============================================================================

def test_phase1_stack_health(http_client):
    r = http_client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "veyra-midend"


# ==============================================================================
# PHASE 3: Tool Discovery against Authoritative midend.md Contract
# ==============================================================================

def test_phase3_tool_discovery(http_client):
    agent = BlackBoxAgentClient(http_client)
    tools_data = agent.get_public_tools()
    skills_data = agent.get_public_skills()

    tool_names = {t["name"] for t in tools_data["tools"]}
    skill_names = {s["skill_id"] for s in skills_data["skills"]}

    # Authoritative core tool names from midend.md
    expected_core_tools = {
        "pam_scan",
        "pam_scan_region",
        "compute_cut_site",
        "compute_gc_content",
        "check_homopolymer_runs",
        "compute_melting_temp",
        "compute_secondary_structure",
        "compute_positional_features",
        "compute_dinucleotide_composition",
        "compute_seed_gc",
        "offtarget_search",
        "score_offtargets",
        "rank_candidates",
        "predict_ontarget_efficiency",
        "analyze_mismatch_seed",
    }
    for t in expected_core_tools:
        assert t in tool_names, f"Documented tool {t} is missing from public /tools"

    expected_skills = {
        "spcas9_gene_cutting",
        "offtarget_toxicity_risk",
        "model_calibration",
    }
    for s in expected_skills:
        assert s in skill_names, f"Documented skill {s} is missing from public /skills"


# ==============================================================================
# PHASE 4: Test Every Single Exposed Tool & Skill
# ==============================================================================

def test_phase4_test_every_exposed_tool(http_client):
    agent = BlackBoxAgentClient(http_client)
    seq = "ATGCGAATATGTCTCTGTGAGGCTTTTCATTCTGACTGCAACGGGCAATATGTCTCTGTGTGG"
    spacer20 = "ACGGGCAATATGTCTCTGTG"

    # 1. pam_scan
    res = agent.execute_sync({"tool_calls": [{"tool": "pam_scan", "arguments": {"sequence": seq}}]})
    assert res["status"] == "completed"
    assert res["completed_tool_calls"] == 1
    assert "rows" in res["tool_calls"][0]["result"]

    # 2. pam_scan_region
    res = agent.execute_sync({"tool_calls": [{"tool": "pam_scan_region", "arguments": {"chrom": "NC_000913.3", "start": 100, "end": 200}}]})
    assert res["status"] == "completed"

    # 3. compute_cut_site
    res = agent.execute_sync({"tool_calls": [{"tool": "compute_cut_site", "arguments": {"spacer_start": 50, "strand": "+", "spacer_length": 20, "chrom": "NC_000913.3", "return_genomic_coord": True, "return_relative_coord": True}}]})
    assert res["status"] == "completed"
    assert res["tool_calls"][0]["result"].get("summary", {}).get("cut_site_relative") == 17

    # 4. compute_gc_content
    res = agent.execute_sync({"tool_calls": [{"tool": "compute_gc_content", "arguments": {"sequence": spacer20}}]})
    assert res["status"] == "completed"
    assert 0.0 <= res["tool_calls"][0]["result"].get("summary", {}).get("gc_content", 0) <= 1.0

    # 5. check_homopolymer_runs
    res = agent.execute_sync({"tool_calls": [{"tool": "check_homopolymer_runs", "arguments": {"sequence": "AAAAATTTTCCCCGGGG"}}]})
    assert res["status"] == "completed"
    assert res["tool_calls"][0]["result"].get("summary", {}).get("homopolymer_max_run", 0) >= 4

    # 6. compute_melting_temp
    res = agent.execute_sync({"tool_calls": [{"tool": "compute_melting_temp", "arguments": {"sequence": spacer20}}]})
    assert res["status"] == "completed"
    assert res["tool_calls"][0]["result"].get("summary", {}).get("tm_celsius", 0) > 0

    # 7. compute_secondary_structure
    res = agent.execute_sync({"tool_calls": [{"tool": "compute_secondary_structure", "arguments": {"sequence": spacer20}}]})
    assert res["status"] == "completed"

    # 8. compute_positional_features
    res = agent.execute_sync({"tool_calls": [{"tool": "compute_positional_features", "arguments": {"sequence": spacer20}}]})
    assert res["status"] == "completed"

    # 9. compute_dinucleotide_composition
    res = agent.execute_sync({"tool_calls": [{"tool": "compute_dinucleotide_composition", "arguments": {"sequence": spacer20}}]})
    assert res["status"] == "completed"

    # 10. compute_seed_gc
    res = agent.execute_sync({"tool_calls": [{"tool": "compute_seed_gc", "arguments": {"sequence": spacer20}}]})
    assert res["status"] == "completed"

    # 11. analyze_mismatch_seed
    res = agent.execute_sync({"tool_calls": [{"tool": "analyze_mismatch_seed", "arguments": {"guide_sequence": spacer20, "offtarget_sequence": "ATGCGATCGATCGATCGATA"}}]})
    assert res["status"] == "completed"

    # 12. offtarget_search
    res = agent.execute_sync({"tool_calls": [{"tool": "offtarget_search", "arguments": {"spacer_sequence": spacer20, "genome_id": "ecoli_k12", "max_mismatches": 3}}]})
    assert res["status"] == "completed"

    # 13. score_offtargets
    res = agent.execute_sync({"tool_calls": [{"tool": "score_offtargets", "arguments": {"spacer_sequence": spacer20, "candidates": [{"offtarget_sequence": spacer20, "mismatches": 0}]}}]})
    assert res["status"] == "completed"

    # 14. rank_candidates
    res = agent.execute_sync({"tool_calls": [{"tool": "rank_candidates", "arguments": {"guides": [{"protospacer": spacer20, "composite_score": 0.85}]}}]})
    assert res["status"] == "completed"

    # 15. predict_ontarget_efficiency
    res = agent.execute_sync({"tool_calls": [{"tool": "predict_ontarget_efficiency", "arguments": {"context_sequence": "AAAA" + spacer20 + "TGG" + "AAA"}}]})
    assert res["status"] == "completed"

    # 16. Skill: spcas9_gene_cutting
    res = agent.execute_sync({"tool_calls": [{"tool": "spcas9_gene_cutting", "arguments": {"sequence": seq, "depth": "quick"}}]})
    assert res["status"] == "completed"
    assert len(res["tool_calls"][0]["result"].get("candidates", [])) > 0

    # 17. Skill: offtarget_toxicity_risk
    res = agent.execute_sync({"tool_calls": [{"tool": "offtarget_toxicity_risk", "arguments": {"spacer_sequence": spacer20, "features": {"Sh": 0.2, "delta_g_binding": -5.5, "Ca": 0.8}}}]})
    assert res["status"] == "completed"
    assert res["tool_calls"][0]["result"].get("status") in {"complete", "prototype", "partial", "unavailable"}


# ==============================================================================
# PHASE 5: Parameter Defaults, Overrides, and Validation Metadata
# ==============================================================================

def test_phase5_parameter_overrides_and_metadata(http_client):
    agent = BlackBoxAgentClient(http_client)
    seq = "ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCG"

    # Test parameter override: strand='fwd' instead of default 'both'
    res = agent.execute_sync({
        "tool_calls": [{
            "tool": "pam_scan",
            "arguments": {"sequence": seq, "strand": "fwd", "pam_pattern": "NGG"},
        }]
    })
    assert res["status"] == "completed"
    call_meta = res["tool_calls"][0]["metadata"].get("parameters_meta", {})
    
    # strand was overridden
    assert call_meta.get("strand", {}).get("status") == "overridden"
    assert call_meta.get("strand", {}).get("value") == "fwd"
    assert call_meta.get("strand", {}).get("default") == "both"

    # pam_pattern was default
    assert call_meta.get("pam_pattern", {}).get("status") == "default"
    assert call_meta.get("pam_pattern", {}).get("value") == "NGG"


# ==============================================================================
# PHASE 6 & 7: Multi-Tool Chaining & Parallel Groups
# ==============================================================================

def test_phase6_multi_tool_chaining_workflows(http_client):
    agent = BlackBoxAgentClient(http_client)
    seq = "ATGCGAATATGTCTCTGTGAGGCTTTTCATTCTGACTGCAACGGGCAATATGTCTCTGTGTGG"

    # Chain 1: PAM scan -> Extract 1st candidate -> compute cut site -> compute GC & Tm -> Rank
    res1 = agent.execute_sync({"tool_calls": [{"tool": "pam_scan", "arguments": {"sequence": seq}}]})
    assert res1["status"] == "completed"
    rows = res1["tool_calls"][0]["result"]["rows"]
    assert len(rows) > 0
    top_candidate = rows[0]
    start_pos = top_candidate["start"]
    protospacer = seq[max(0, start_pos - 20):start_pos] if top_candidate["strand"] == "+" else seq[top_candidate["end"]:top_candidate["end"] + 20]
    assert len(protospacer) == 20

    res2 = agent.execute_sync({
        "tool_calls": [
            {"tool": "compute_cut_site", "arguments": {"spacer_start": top_candidate["start"], "strand": top_candidate["strand"], "spacer_length": 20, "chrom": "NC_000913.3", "return_genomic_coord": True, "return_relative_coord": True}},
            {"tool": "compute_gc_content", "arguments": {"sequence": protospacer}},
            {"tool": "compute_melting_temp", "arguments": {"sequence": protospacer}},
            {"tool": "rank_candidates", "arguments": {"guides": [{"protospacer": protospacer, "pam": "AGG", "rs2_score": 0.88}]}},
        ]
    })
    assert res2["status"] == "completed"
    assert res2["completed_tool_calls"] == 4
    ranked = res2["tool_calls"][3]["result"].get("rows", []) or res2["tool_calls"][3]["result"].get("ranked_guides", [])
    assert len(ranked) == 1

    # Chain 2: PAM -> Off-target search -> Mismatch seed -> CFD -> Rank
    res_off = agent.execute_sync({
        "tool_calls": [
            {"tool": "offtarget_search", "arguments": {"spacer_sequence": protospacer, "genome_id": "ecoli_k12_mg1655", "max_mismatches": 3}},
            {"tool": "analyze_mismatch_seed", "arguments": {"spacer_sequence": protospacer, "candidate_sequence": protospacer}},
            {"tool": "score_offtargets", "arguments": {"spacer_sequence": protospacer, "candidates": [{"protospacer": protospacer, "pam": "AGG", "mismatch_count": 0}]}},
        ]
    })
    assert res_off["status"] == "completed"
    assert res_off["completed_tool_calls"] == 3


def test_phase6_7_chaining_and_parallel(http_client):
    agent = BlackBoxAgentClient(http_client)
    spacer20 = "ACGGGCAATATGTCTCTGTG"

    # Test Parallel Group
    parallel_payload = {
        "parallel_groups": [{
            "group_id": "group_qc_features",
            "calls": [
                {"tool": "compute_gc_content", "arguments": {"sequence": spacer20}},
                {"tool": "compute_melting_temp", "arguments": {"sequence": spacer20}},
                {"tool": "check_homopolymer_runs", "arguments": {"sequence": spacer20}},
                {"tool": "compute_secondary_structure", "arguments": {"sequence": spacer20}},
            ]
        }]
    }
    res = agent.execute_sync(parallel_payload)
    assert res["status"] == "completed"
    assert res["completed_tool_calls"] == 4
    assert len(res["parallel_groups"]) == 1
    assert res["parallel_groups"][0]["group_id"] == "group_qc_features"
    assert len(res["parallel_groups"][0]["calls"]) == 4


# ==============================================================================
# PHASE 13: Live AI Provider / Chat Cross-Check
# ==============================================================================

def test_phase13_live_ai_chat_cross_check(http_client):
    agent = BlackBoxAgentClient(http_client)
    chat_res = agent.send_chat("What tools do you have access to for CRISPR SpCas9 analysis?")
    assert chat_res["status"] in {"completed", "started", "running"}
    if chat_res.get("assistant_output"):
        assert len(chat_res["assistant_output"]) > 0



# ==============================================================================
# PHASE 8: Attached FASTA File Input Workflow
# ==============================================================================

def test_phase8_attached_fasta_workflow(http_client):
    agent = BlackBoxAgentClient(http_client)
    fasta_content = b">ecoli_target_gene\nATGCGAATATGTCTCTGTGAGGCTTTTCATTCTGACTGCAACGGGCAATATGTCTCTGTGTGG\n"
    upload_res = agent.upload_file("target_gene.fasta", fasta_content)
    input_id = upload_res["input_id"]
    assert upload_res["input_class"] == "analysis_input"

    # Run skill with input_id
    res = agent.execute_sync({
        "input_ids": [input_id],
        "tool_calls": [{"tool": "spcas9_gene_cutting", "arguments": {"input_id": input_id, "depth": "quick"}}],
    })
    assert res["status"] == "completed"
    candidates = res["tool_calls"][0]["result"].get("candidates", [])
    assert len(candidates) > 0
    cut_val = candidates[0]["cut_site"]
    assert (cut_val == 17) or (isinstance(cut_val, dict) and cut_val.get("relative") == 17)


# ==============================================================================
# PHASE 9: Calibration CSV Dataset Workflow
# ==============================================================================

def test_phase9_calibration_csv_workflow(http_client):
    agent = BlackBoxAgentClient(http_client)
    csv_content = b"guide,target,toxicity\nACGGGCAATATGTCTCTGTG,ACGGGCAATATGTCTCTGTG,0.12\nGAATGAAAAGCTGCTAGCTA,GAATGAAAAGCTGCTAGCTA,0.88\n"
    upload_res = agent.upload_file("calib_dataset.csv", csv_content)
    calib_id = upload_res["input_id"]
    assert upload_res["input_class"] == "calibration_input"

    # Execute model calibration skill
    res = agent.execute_sync({
        "input_ids": [calib_id],
        "tool_calls": [{"tool": "model_calibration", "arguments": {"calibration_input_id": calib_id, "guide_column": "guide", "target_column": "toxicity"}}],
    })
    assert res["status"] == "completed"
    skill_res = res["tool_calls"][0]["result"]
    assert skill_res.get("sample_count") == 2
    assert skill_res.get("calibration_status") == "calibrated"


# ==============================================================================
# PHASE 10: Negative and Error Testing
# ==============================================================================

def test_phase10_negative_and_error_handling(http_client):
    agent = BlackBoxAgentClient(http_client)

    # 1. Invalid input ID
    r = http_client.get("/inputs/non_existent_input_999")
    assert r.status_code == 400

    # 2. Filesystem path rejection (Security contract)
    r = http_client.post("/executions", json={
        "tool_calls": [{"tool": "pam_scan", "arguments": {"path": "/etc/passwd"}}]
    })
    assert r.status_code == 400

    # 3. Invalid DNA sequence in strict tools
    res = agent.execute_sync({"tool_calls": [{"tool": "pam_scan", "arguments": {"sequence": "INVALID_DNA_123"}}]})
    assert res["status"] == "completed"  # Returns deterministic empty/handled result or warning
    assert len(res["tool_calls"][0]["result"].get("rows", [])) == 0


# ==============================================================================
# PHASE 11 & 12: Evidence Integrity & Black-Box Boundary
# ==============================================================================

def test_phase11_12_evidence_integrity_and_boundary(http_client):
    agent = BlackBoxAgentClient(http_client)
    res = agent.execute_sync({
        "tool_calls": [{"tool": "compute_gc_content", "arguments": {"sequence": "ACGTACGTACGTACGTACGT"}}]
    })
    assert res["status"] == "completed"
    call_state = res["tool_calls"][0]
    
    # Verify all public audit fields
    assert "call_id" in call_state
    assert "execution_id" in call_state
    assert call_state["duration_ms"] > 0
    assert "parameters_meta" in call_state["metadata"]
    assert "gc_content" in call_state["result"].get("summary", {})
