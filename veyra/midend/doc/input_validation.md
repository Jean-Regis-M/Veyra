# MIDEND file input validation

MIDEND accepts file uploads through `POST /inputs/file` and `POST /calibration/file` using
`multipart/form-data`. It validates the filename extension, optional MIME hint,
UTF-8 text content, detected format, record structure, nucleotide or tabular content,
headers, and column consistency before an input is stored or referenced by AI/execution requests.

## Supported input classes

### 1. Analysis input (`analysis_input`)
Used for primary CRISPR/genomic analysis workflows.

| Format | Extensions | Backend use |
|---|---|---|
| FASTA | `.fa`, `.fasta`, `.fna`, `.faa`, `.fns`, `.frn` | `ingest_file` |
| FASTQ | `.fq`, `.fastq`, `.fqr` | `ingest_file` |
| GenBank | `.gb`, `.gbk`, `.gbff`, `.genbank` | `ingest_file` |

### 2. Calibration input (`calibration_input`)
Optional experimental datasets used for statistical calibration.

| Format | Extensions | Operations |
|---|---|---|
| CSV | `.csv` | `model_calibration`, `offtarget_toxicity_risk` |
| TSV | `.tsv`, `.tab` | `model_calibration`, `offtarget_toxicity_risk` |

**Calibration input is OPTIONAL.** Normal VEYRA workflows operate completely normally without any calibration data.

The default maximum upload size is 50 MiB. The validator rejects empty files,
unknown extensions, path traversal, binary/non-UTF-8 content, extension/content
mismatches, malformed records, empty datasets, inconsistent columns, and invalid nucleotide data.
Files are held in a process-local input registry; clients receive only an
`input_id` and safe metadata, never a filesystem path.

Valid analysis response example:

```json
{
  "input_id": "input_123",
  "filename": "target.fasta",
  "format": "fasta",
  "detected_format": "fasta",
  "input_class": "analysis_input",
  "size_bytes": 42,
  "record_count": 3,
  "sequence_count": 3,
  "validation_status": "valid",
  "backend_operation": "ingest_file"
}
```

Valid calibration response example:

```json
{
  "input_id": "calib_123",
  "filename": "dataset.csv",
  "format": "csv",
  "detected_format": "csv",
  "input_class": "calibration_input",
  "size_bytes": 1024,
  "record_count": 100,
  "row_count": 100,
  "sample_count": 100,
  "column_count": 5,
  "columns": ["guide", "target", "sh", "delta_g_binding", "ca"],
  "validation_status": "valid",
  "calibration_status": "uncalibrated",
  "backend_operation": "calibration"
}
```

Invalid uploads return HTTP 400 with `error`, `message`, and `field`, using
codes such as `unsupported_file_type`, `unsupported_calibration_format`,
`mismatched_file_format`, `malformed_file`, `empty_file`, `empty_dataset`,
`inconsistent_columns`, `missing_header`, `invalid_sequence_format`,
`file_too_large`, `path_traversal`, and `unreadable_file`.

`POST /ai/chat` and `POST /executions` may reference only validated `input_ids`.
They reject arbitrary filesystem-path arguments before scheduling any AI or
backend work. AI receives structured validated-input metadata, not raw paths.
