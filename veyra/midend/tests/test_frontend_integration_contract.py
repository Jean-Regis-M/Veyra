"""Test frontend-midend integration contract and VEYRA chat continuity workflows."""

import asyncio
import httpx
import pytest

from veyra.midend.http_api.app import app
from veyra.midend.input_validation import validate_input_file, validate_calibration_file
from veyra.midend.control_plane import control_plane


def test_file_upload_and_attachment_for_chat():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # 1. Valid FASTA upload via /inputs/file
            fasta_content = b">EMX1\nGAGTCCGAGCAGAAGAAGAAGGGCTCCCATCACATCAACCGGTGGCGCATTGCCACGAAGCAGGCCAATGGGGAGGACATCGATGTCACCTCCAATGAC\n"
            up_fasta = await client.post("/inputs/file", files={"file": ("target.fasta", fasta_content, "text/x-fasta")})
            assert up_fasta.status_code == 201
            fasta_meta = up_fasta.json()
            assert fasta_meta["input_class"] == "analysis_input"
            assert fasta_meta["detected_format"] == "fasta"
            input_id = fasta_meta["input_id"]

            # 2. Valid FASTQ upload
            fastq_content = b"@read1\nGAGTCCGAGCAGAAGAAGAA\n+\nIIIIIIIIIIIIIIIIIIII\n"
            up_fastq = await client.post("/inputs/file", files={"file": ("reads.fastq", fastq_content, "text/fastq")})
            assert up_fastq.status_code == 201
            assert up_fastq.json()["detected_format"] == "fastq"

            # 3. Valid GenBank upload
            gb_content = b"LOCUS       SCU49845     100 bp    DNA             PLN       21-JUN-1999\nORIGIN\n        1 gagtccgagc agaagaagaa gggctcccat cacatcaacc ggtggcgcat tgccacgaag\n       61 caggccaatg gggaggacat cgatgtcacc tccaatgac\n//\n"
            up_gb = await client.post("/inputs/file", files={"file": ("locus.gb", gb_content, "text/plain")})
            assert up_gb.status_code == 201
            assert up_gb.json()["detected_format"] == "genbank"

            # 4. Invalid file upload (malformed)
            bad_file = await client.post("/inputs/file", files={"file": ("bad.fasta", b"invalid_non_fasta", "text/plain")})
            assert bad_file.status_code == 400
            assert bad_file.json()["error"] == "malformed_file"

            # 5. Create conversation and send chat message with attached input_id
            conv_res = await client.post("/conversations")
            assert conv_res.status_code == 201
            conv_id = conv_res.json()["conversation_id"]

            chat_res = await client.post("/ai/chat", json={
                "message": "Find the candidate SpCas9 sites and explain their cut positions",
                "conversation_id": conv_id,
                "input_ids": [input_id],
            })
            assert chat_res.status_code == 200
            assert chat_res.json()["status"] == "started"
            exec_id = chat_res.json()["execution_id"]

            # Check execution status includes validated_inputs
            exec_res = await client.get(f"/executions/{exec_id}")
            assert exec_res.status_code == 200
            exec_data = exec_res.json()
            assert len(exec_data["validated_inputs"]) >= 1
            assert exec_data["validated_inputs"][0]["input_id"] == input_id
    asyncio.run(run())


def test_analysis_to_chat_continuity():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # 1. Run SpCas9 analysis skill
            seq = "GAGTCCGAGCAGAAGAAGAAGGGCTCCCATCACATCAACCGGTGGCGCATTGCCACGAAGCAGGCCAATGGGGAGGACATCGATGTCACCTCCAATGAC"
            skill_res = await client.post("/skills/spcas9_gene_cutting", json={"sequence": seq, "depth": "quick"})
            assert skill_res.status_code == 202
            exec_id = skill_res.json()["execution_id"]

            # Wait for completion
            for _ in range(80):
                resp = await client.get(f"/executions/{exec_id}")
                if resp.json().get("status") in {"completed", "failed"}:
                    break
                await asyncio.sleep(0.05)

            exec_status = (await client.get(f"/executions/{exec_id}")).json()
            assert exec_status["status"] == "completed"
            assert len(exec_status["skill_result"]["candidates"]) > 0

            # 2. Continue in VEYRA chat: create conversation, post continuation summary
            conv_res = await client.post("/conversations")
            conv_id = conv_res.json()["conversation_id"]

            context_summary = f"Continued analysis for execution {exec_id} with {len(exec_status['skill_result']['candidates'])} candidates."
            await client.post(f"/conversations/{conv_id}/messages", json={
                "role": "system",
                "content": f"DEVELOPER CONTEXT:\n{context_summary}",
            })

            # User asks follow-up
            followup = await client.post("/ai/chat", json={
                "message": "Which candidate has the highest overall ranking and balanced GC?",
                "conversation_id": conv_id,
            })
            assert followup.status_code == 200
            assert followup.json()["status"] == "started"
    asyncio.run(run())
