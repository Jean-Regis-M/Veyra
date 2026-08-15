# MIDEND file input validation

MIDEND accepts file uploads only through `POST /inputs/file` using
`multipart/form-data`. It validates the filename extension, optional MIME hint,
UTF-8 text content, detected format, record structure, and nucleotide content
before an input is stored or referenced by AI/execution requests.

The formats are derived from the implemented VEYRA ingestion parsers:

| Format | Extensions | Backend use |
|---|---|---|
| FASTA | `.fa`, `.fasta`, `.fna`, `.faa`, `.fns`, `.frn` | `ingest_file` |
| FASTQ | `.fq`, `.fastq`, `.fqr` | `ingest_file` |
| GenBank | `.gb`, `.gbk`, `.gbff`, `.genbank` | `ingest_file` |

GFF/GFF3 and plain DNA `.txt` files are not accepted as file uploads because
the current VEYRA backend has no GFF/plain-text ingestion parser. Raw DNA
strings remain supported by the backend's sequence operation APIs.

The default maximum upload size is 50 MiB. The validator rejects empty files,
unknown extensions, path traversal, binary/non-UTF-8 content, extension/content
mismatches, malformed records, empty records, and invalid nucleotide data.
Files are held in a process-local input registry; clients receive only an
`input_id` and safe metadata, never a filesystem path.

Valid response example:

```json
{
  "input_id": "input_123",
  "filename": "target.fasta",
  "format": "fasta",
  "detected_format": "fasta",
  "size_bytes": 42,
  "record_count": 3,
  "sequence_count": 3,
  "validation_status": "valid",
  "backend_operation": "ingest_file"
}
```

Invalid uploads return HTTP 400 with `error`, `message`, and `field`, using
codes such as `unsupported_file_type`, `mismatched_file_format`,
`malformed_file`, `empty_file`, `invalid_sequence_format`, `file_too_large`,
`path_traversal`, and `unreadable_file`.

`POST /ai/chat` and `POST /executions` may reference only validated `input_ids`.
They reject arbitrary filesystem-path arguments before scheduling any AI or
backend work. AI receives structured validated-input metadata, not raw paths.
