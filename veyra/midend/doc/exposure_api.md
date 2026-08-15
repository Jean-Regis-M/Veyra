# MIDEND exposure API

The FastAPI app is available as `veyra.midend.http_api.app:app`. State is
process-local and is intended for an active MIDEND instance.

Input management endpoints:
- `POST /inputs/file`: uploads and validates analysis input (FASTA, FASTQ, GenBank) or calibration input (CSV, TSV).
- `POST /calibration/file` (or `POST /inputs/calibration`): uploads and validates calibration CSV/TSV datasets.
- `GET /inputs/{id}`: returns validated input metadata.
- `GET /calibration/{id}`: returns validated calibration dataset metadata.
- `GET /calibration/status`: returns registered datasets, coefficient models, and calibration status.
- `POST /calibration/run`: explicitly runs deterministic model calibration workflow on a registered CSV/TSV dataset.

AI control endpoints are `GET /ai/status`, `GET/POST /ai/providers`,
`GET/POST /ai/active`, `POST /ai/test`, and `POST /ai/chat`. Provider responses
contain IDs, models, availability, and timing only; credentials are never
returned. Provider tests are the only automatic-looking operation that makes a
provider network call, and they are explicitly requested.

Backend control endpoints are `GET /backend/status`, `POST /backend/active`,
and `GET /tools`. The active connector applies to future executions; running
executions retain their connector.

`POST /executions` accepts sequential `tool_calls` or `parallel_groups` and
returns an execution ID. `GET /executions/{id}` exposes aggregate state,
structured evidence, final assistant output, and safe status metadata.
`/tools`, `/ai`, and `/stream` subresources expose individual calls, AI request
metadata, and SSE events. Tool timing is wall-clock timing; parallel group
duration is not the sum of member calls.

`POST /ai/chat` creates a conversation if needed and returns an execution ID;
clients consume its event stream and final execution state.
