import asyncio

import httpx

from veyra.midend.http_api.app import app
from veyra.midend.input_validation import MIDENDInputError, validate_input_file


def test_direct_validator_formats_and_errors():
    fasta = validate_input_file("target.fasta", b">one\nACGTACGT\n")
    assert fasta.detected_format == "fasta"
    assert fasta.record_count == 1
    fastq = validate_input_file("reads.fastq", b"@read\nACGT\n+\nIIII\n")
    assert fastq.detected_format == "fastq"
    genbank = validate_input_file("record.gb", b"LOCUS       X 4 bp DNA\nORIGIN\n        1 acgt\n//\n")
    assert genbank.detected_format == "genbank"
    for filename, content, code in [
        ("bad.xyz", b">x\nACGT\n", "unsupported_file_type"),
        ("bad.fasta", b"not fasta\n", "malformed_file"),
        ("bad.fasta", b"@read\nACGT\n+\nIIII\n", "mismatched_file_format"),
        ("empty.fasta", b"", "empty_file"),
        ("../bad.fasta", b">x\nACGT\n", "path_traversal"),
    ]:
        try:
            validate_input_file(filename, content)
        except MIDENDInputError as exc:
            assert exc.error == code
        else:
            raise AssertionError(f"expected {code}")


def test_upload_endpoint_returns_safe_metadata_and_rejects_invalid_files():
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            valid = await client.post("/inputs/file", files={
                "file": ("uploaded.fasta", b">one\nACGT\n", "text/x-fasta")
            })
            assert valid.status_code == 201
            metadata = valid.json()
            assert metadata["validation_status"] == "valid"
            assert "path" not in metadata
            assert (await client.get(f"/inputs/{metadata['input_id']}")).status_code == 200

            invalid = await client.post("/inputs/file", files={
                "file": ("uploaded.fasta", b"not a fasta", "text/plain")
            })
            assert invalid.status_code == 400
            assert invalid.json()["error"] == "malformed_file"

            traversal = await client.post("/inputs/file", files={
                "file": ("../uploaded.fasta", b">one\nACGT\n", "text/x-fasta")
            })
            assert traversal.status_code == 400
            assert traversal.json()["error"] == "path_traversal"

            blocked_execution = await client.post("/executions", json={
                "input_ids": ["missing-input"], "tool_calls": [{"tool": "x", "arguments": {}}]
            })
            assert blocked_execution.status_code == 400
            assert blocked_execution.json()["error"] == "unknown_input"

            blocked_path = await client.post("/executions", json={
                "tool_calls": [{"tool": "ingest_file", "arguments": {"input_path": "/tmp/file.fasta"}}]
            })
            assert blocked_path.status_code == 400
            assert blocked_path.json()["error"] == "unreadable_file"
    asyncio.run(run())


def test_size_limit_is_enforced():
    try:
        validate_input_file("large.fasta", b">x\nACGT\n", max_bytes=3)
    except MIDENDInputError as exc:
        assert exc.error == "file_too_large"
    else:
        raise AssertionError("expected file_too_large")
