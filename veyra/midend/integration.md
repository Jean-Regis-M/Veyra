# MIDEND frontend integration contract

This document describes the public surface currently implemented by
`veyra/midend/http_api/app.py` and `veyra/midend/mcp_interface.py`. It is an
integration contract for the active, process-local MIDEND instance; it is not a
specification of future orchestration behavior.

Base URL is deployment-specific. JSON responses use UTF-8. IDs are opaque
strings. State, executions, inputs, and conversations are process-local and
are lost when the MIDEND process restarts.

## Global frontend rules

- Never display, store in client state, log, or return an API key. `api_key` is
  accepted only in configuration request bodies; it is never in success
  responses, status, execution metadata, events, or errors.
- Never request, render, or infer hidden chain-of-thought, scratchpads, private
  reasoning tokens, authorization headers, or filesystem paths.
- `reasoning_active` and `generation_active`, tool names, tool arguments,
  structured tool results, timings, warnings, and errors are public metadata.
- Reject invalid files, unknown input IDs, arbitrary filesystem-path arguments,
  unsupported connectors, and invalid provider/model selections before calling
  the corresponding endpoint.
- Do not invent backend tool names, arguments, schemas, or validation rules.
  Obtain live tool definitions from `GET /tools`; the biological semantics are
  defined by `veyra/midend.md` and the backend.
- HTTP and the current MCP capability functions use the same MIDEND state and
  semantics. The current MCP registry is not a separate MCP network server.
- Error status codes and bodies below describe the implemented route behavior;
  FastAPI/Pydantic may additionally return its standard `422` validation body
  for malformed JSON or missing required fields.

## Shared types

`string`, `boolean`, `integer`, `number`, `object`, and `array<T>` have their
usual JSON meanings. Unless a restriction is stated, an object field has no
additional MIDEND schema validation and the frontend must use the live backend
tool schema.

### Provider configuration

| Field | Type | Required/default | Restrictions |
|---|---|---|---|
| `provider_id` | string | required for provider add/select | Add requires non-empty; select must identify a registered provider. |
| `type` | string | optional, `openai_compatible` | Current implementation accepts only `openai_compatible`. |
| `base_url` | string | required | Non-empty; configuration additionally requires valid `http`/`https` URL. |
| `api_key` | string | required for add/config | Non-empty; secret. Never render it back. |
| `models` | array<string> | optional, `[]` | For provider add, non-empty after default-model fallback; model names must be non-empty and include `default_model`. |
| `default_model` | string | required for provider add | Non-empty and present in the effective model list. |
| `persist` | boolean | optional, `false` | `true` is rejected with `secure_persistence_unavailable`; plaintext key persistence is disabled. |

### Validated input metadata and input classes

The MIDEND supports two independent input classes:

1. `analysis_input`:
   - Target gene / sequence / FASTA / FASTQ / GenBank / genomic region.
   - Formats: FASTA (`.fa`, `.fasta`, `.fna`, `.faa`, `.fns`, `.frn`), FASTQ (`.fq`, `.fastq`, `.fqr`), GenBank (`.gb`, `.gbk`, `.gbff`, `.genbank`).
   - Used for normal analysis workflows.

2. `calibration_input`:
   - Optional experimental labeled tabular dataset.
   - Formats: CSV (`.csv`), TSV (`.tsv`, `.tab`).
   - Used for optional statistical model calibration and evidence improvement.
   - **CRITICAL RULE**: `calibration_input` is **OPTIONAL**. Normal VEYRA workflows (PAM scanning, gene cutting, cut-site geometry, sequence features, on-target prediction, off-target search, CFD scoring, candidate ranking) never require calibration data.

`POST /inputs/file` returns metadata for either class:

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

For calibration datasets (via `POST /inputs/file` or `POST /calibration/file`), it returns:

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

The upload limit is 50 MiB. Content must be valid UTF-8, the extension and
detected content must agree. Tabular files (.csv, .tsv) must have non-empty
headers, consistent columns across all data rows, and at least 1 data row.
Invalid inputs return structured validation errors. Validated input IDs, not
paths, are used by AI and execution requests.

### Calibration status states

The MIDEND explicitly distinguishes these calibration states:
- `not_provided`: No calibration dataset was supplied in the request. Normal workflows continue normally.
- `unavailable`: Calibration was requested but the dataset or required feature columns are unavailable.
- `uncalibrated`: Model contains baseline/prototype coefficients without experimental dataset fit.
- `user_supplied`: User provided explicit manual coefficient values without dataset fitting.
- `calibrated`: Deterministic statistical fitting was performed on a validated labeled experimental dataset with computed metrics (R², MSE, MAE, sample counts).
- `externally_validated`: Registered model with published external benchmark dataset and fit metrics.

A model is never marked "validated" merely because a CSV was uploaded. No coefficients are fabricated.

### Execution tool call shapes

`tool_calls` is `array<object>`; each call normally contains:

| Field | Type | Required/default | Restrictions |
|---|---|---|---|
| `call_id` | string | optional, generated | Opaque client correlation ID. |
| `tool` | string | required in practice | Must be a live tool name from `/tools`; `tool_name` is also accepted by the current implementation. |
| `arguments` | object | optional, `{}` | Must match the live backend tool schema. Do not include `path`, `file_path`, `filepath`, or `input_path`; use validated `input_ids`. |

`parallel_groups` is `array<object>`; each group contains optional `group_id`
and `calls: array<object>` using the call shape above. Group duration is wall
clock time, not the sum of calls.

## HTTP API

### Service and input endpoints

#### `GET /health`

No request body or query arguments. Returns:

```json
{
  "status": "ok",
  "service": "veyra-midend",
  "connector": "http",
  "ai_configured": false,
  "provider_status": "not_configured"
}
```

Frontend must not treat this as a provider test; startup performs no AI call.

FastAPI also exposes generated documentation routes with no request arguments:
`GET /openapi.json` returns the generated OpenAPI document, `GET /docs` serves
Swagger UI, `GET /redoc` serves ReDoc, and `GET /docs/oauth2-redirect` serves
the documentation UI redirect helper. These are framework documentation
surfaces, not additional MIDEND operations.

#### `POST /inputs/file`

Request: `multipart/form-data`; the first part with a filename is used. The
filename is required, must be a basename with no `/`, `\\`, `..`, or NUL, and
the part content is bounded by the 50 MiB limit. Accepts analysis files (FASTA,
FASTQ, GenBank) and calibration datasets (CSV, TSV).

Success: HTTP `201`, validated input metadata above.

Errors: HTTP `400` with `{"error":"...","message":"...","field":"file"}`.
Codes include `unsupported_file_type`, `unsupported_calibration_format`,
`malformed_file`, `mismatched_file_format`, `empty_file`, `empty_dataset`,
`inconsistent_columns`, `missing_header`, `invalid_sequence_format`,
`file_too_large`, `path_traversal`, and `unreadable_file`.

#### `POST /calibration/file` (or `POST /inputs/calibration`)

Request: `multipart/form-data`; expects a `.csv` or `.tsv` tabular dataset.
Validates UTF-8, non-empty header, consistent column lengths across all rows,
and at least 1 data row.

Success: HTTP `201`, validated calibration metadata.

Errors: HTTP `400` with structured validation error (`empty_dataset`,
`inconsistent_columns`, `missing_header`, `unsupported_calibration_format`, etc.).

#### `GET /inputs/{input_id}`

Path `input_id: string`, required. Returns the same validated metadata as the
upload. Unknown IDs return HTTP `400` with `error: "unknown_input"`.

#### `GET /calibration/{calibration_id}`

Path `calibration_id: string`, required. Returns metadata for a validated
calibration dataset. Unknown IDs return HTTP `400` with `error: "unknown_calibration_input"`.

#### `GET /calibration/status`

No arguments. Returns registered dataset counts, datasets list, registered
coefficient models, and calibration availability.

#### `POST /calibration/run`

Starts an explicit deterministic calibration workflow on a registered CSV/TSV dataset.
Request body: `{ "calibration_input_id": "calib_123", ... }`.
Returns HTTP `202` with `{ "execution_id": "exec_...", "skill": "model_calibration", "status": "started" }`.

## AI provider and chat endpoints

#### `GET /ai/config`

No arguments. Returns the legacy safe configuration view:

```json
{
  "provider": "openai_compatible",
  "base_url": "https://api.llm7.io/v1",
  "model": "default",
  "configured": false,
  "source": "default",
  "api_key_configured": false
}
```

`api_key_configured` is boolean only; no key-derived value is returned.

#### `POST /ai/config`

Request JSON: `base_url: string` required non-empty, `api_key: string` required
non-empty secret, `model: string` required non-empty, `persist: boolean`
optional default `false`. The URL must be HTTP/HTTPS and the model non-empty.
`persist: true` is rejected.

Success: HTTP `200` with `{configured, provider, base_url, model}` and no key.
Invalid configuration returns HTTP `422` with
`detail.code: "invalid_ai_provider_config"`. Persistence requests return
`detail.code: "secure_persistence_unavailable"`.

#### `GET /ai/status`

No arguments. Returns provider/model state:

```json
{
  "provider": "openai_compatible",
  "provider_id": "openai_compatible",
  "model": "default",
  "base_url": "https://api.llm7.io/v1",
  "configured": false,
  "available": true,
  "generation_active": false,
  "reasoning_active": false,
  "current_execution_id": null,
  "current_request_id": null
}
```

#### `GET /ai/providers`

No arguments. Returns `{ "providers": [...] }`. Each provider has
`provider_id`, `display_name`, `type`, `configured`, `available`, `models`,
and `default_model`; credentials are absent.

#### `POST /ai/providers`

Request uses the Provider configuration table. `type` must be
`openai_compatible`; `default_model` must be included in `models` (if models
is empty, the implementation uses `[default_model]`). `persist` must remain
false.

Success: HTTP `200` with `{provider_id, configured, available, models,
default_model}`. Invalid provider/model/configuration returns HTTP `422` with
`detail.code: "invalid_ai_provider"`; persistence is rejected with
`secure_persistence_unavailable`.

#### `GET /ai/active`

No arguments. Returns `{provider_id, provider, model}`.

#### `POST /ai/active`

Request JSON: `provider_id: string` required; `model: string|null` optional,
defaulting to that provider's default model. Frontend must select a registered
provider and one of its advertised models. Success returns `{provider_id,
provider, model}`. Invalid selections return HTTP `422` with
`detail.code: "invalid_ai_selection"`.

#### `POST /ai/test`

No request arguments. This is an explicit real provider call. Success returns
`{success: true, provider, model, latency_ms: number, request_id: string|null,
error: null}`. Missing credentials returns HTTP `409` with
`detail.code: "ai_provider_not_configured"`; provider failures return HTTP
`502` with `detail.code: "ai_provider_error"`. No call occurs at startup.

#### `POST /ai/chat`

Request JSON:

| Field | Type | Required/default | Restrictions |
|---|---|---|---|
| `message` | string | required | Minimum length 1. |
| `conversation_id` | string/null | optional, null | If supplied, must exist. |
| `provider_id` | string/null | optional, null | If supplied, must be registered. |
| `model` | string/null | optional, null | Must be available for selected provider. |
| `backend_connector` | string/null | optional, null | Frontend must use `http` or `mcp`; current execution semantics use it for future tool calls. |
| `temperature` | number | optional, `0.0` | No additional MIDEND min/max is enforced. |
| `max_tokens` | integer/null | optional, null | No additional MIDEND min/max is enforced. |
| `stream` | boolean | optional, `false` | Current provider emits one complete response chunk, not token streaming. |
| `input_ids` | array<string> | optional, `[]` | Every ID must be a validated input. |

Success: HTTP `200` with `{execution_id, conversation_id, status: "started"}`.
The frontend reads the final answer from the execution and events. Unknown
conversation/input or invalid selection returns HTTP `400`/`422` as described
above; no AI call is made for an invalid input reference.

## Backend and tool endpoints

## Skills

Skills are process-local orchestration profiles. They delegate all biological
calculations to the live backend tools and use the same execution/event state
as ordinary executions.

### `GET /skills`

No arguments. Returns `{skills: array<SkillMetadata>}`. The current registry
contains `spcas9_gene_cutting`, `offtarget_toxicity_risk`, and `model_calibration`.

### `GET /skills/{skill_id}`

Path `skill_id: string`, required. Returns metadata containing `skill_id`,
`name`, `description`, `version`, `required_inputs`, `optional_inputs`,
`allowed_tools`, `workflow`, `output_schema`, and `validation_rules`.
Unknown skills return HTTP `404`.

### `model_calibration` skill

`POST /skills/model_calibration` runs explicit calibration on a labeled CSV/TSV
dataset. It normalizes rows, maps experimental columns, obtains backend sequence
features where available, performs deterministic least-squares fitting of
statistical model parameters ($\alpha, \beta, \gamma, \epsilon$), computes
rigorous metrics ($R^2$, MSE, MAE, Pearson $r$), and returns a structured
calibration report and AI review summary. The raw dataset rows are never given
to the AI reasoning layer unnecessarily.

### `GET /skills/{skill_id}/status`

Returns skill-specific model status without starting execution. For
`offtarget_toxicity_risk`, this includes the formula version, audited binding
transform, exact availability/reason for `Sh`, `delta_g_binding`, and `Ca`, and
registered coefficient/calibration metadata. It contains no claim that the
model is validated.

### `POST /skills/{skill_id}`

Starts an asynchronous skill execution and returns HTTP `202`:
`{execution_id, skill, status: "started"}`. Follow the normal execution
status and SSE endpoints using the returned ID.

Current request fields:

| Field | Type | Required/default | Restrictions |
|---|---|---|---|
| `sequence` | string/null | one input mode required | Non-empty IUPAC DNA when supplied. |
| `input_id` | string/null | one input mode required | Must be a validated FASTA/FASTQ/GenBank input ID. |
| `genome_id` | string/null | required with region mode | Must be registered for region/full analysis. |
| `chrom` | string/null | required with region mode | Non-empty chromosome/contig identifier. |
| `start` | integer/null | required with region mode | ≥ 1; 1-based half-open coordinate. |
| `end` | integer/null | required with region mode | Greater than `start`; exclusive. |
| `strand` | string | optional, `both` | `both`, `fwd`, or `rev`. |
| `depth` | string | optional, `quick` | `quick` or `full`; full requires `genome_id`. |
| `model` | string | optional, `auto` | `auto`, `both`, `rule_set_3`, `rule_set_2`, or `doench_2014`. |
| `max_candidates` | integer | optional, `100` | 1–1000. |
| `max_mismatches` | integer | optional, `4` | 0–10; used by full off-target search. |
| `max_results` | integer | optional, `1000` | 1–100000; used by full off-target search. |
| `offtarget_backend` | string | optional, `bwa` | Backend contract allows `bwa` or `cas_offinder`; availability is reported by the tool. |
| `connector` | string/null | optional, active connector | `http` or `mcp`. |

Exactly one of `sequence`, `input_id`, or complete region fields is required.
The frontend must reject malformed input before calling, but the MIDEND remains
the authoritative validator. Invalid requests return HTTP `422` with a
structured skill error. No backend or AI call starts for invalid skill input.

The execution’s `skill_result` contains:

```json
{
  "skill": "spcas9_gene_cutting",
  "status": "complete|partial|failed",
  "candidates": [{
    "candidate_id": "candidate_1",
    "chrom": null,
    "strand": "-",
    "pam": "AGG",
    "pam_start": 7,
    "pam_end": 10,
    "protospacer": "...",
    "cut_site": {"relative": 17, "genomic": null},
    "features": {},
    "ontarget": {"score": null, "model": null},
    "specificity": {"offtarget_count": null, "worst_cfd": null},
    "rank": null,
    "cutting_site_string": "sequence | cut=relative=17 | - | PAM=AGG | guide=...",
    "provenance": [],
    "warnings": []
  }],
  "warnings": [],
  "errors": []
}
```

`cutting_site_string` is display-only; the structured object is authoritative.
Scores and coordinates are absent/null when their backend evidence is
unavailable. `partial` never means that missing evidence was treated as zero.
Skill events include `skill_started`, `candidate_discovered`,
`candidate_evaluated`, `ranking_completed`, `skill_completed`, and
`skill_failed`, in addition to ordinary tool-call events.

### `offtarget_toxicity_risk` request

`POST /skills/offtarget_toxicity_risk` uses the existing skill execution body
with these skill-specific fields:

| Field | Type | Required/default | Restrictions |
|---|---|---|---|
| `spacer_sequence` | string | required | 15–30 concrete A/C/G/T bases. |
| `genome_id` | string/null | optional | Existing off-target evidence may be collected; it is not converted to `Sh`. |
| `features` | object | optional, `{}` | Explicit optional `Sh`, `delta_g_binding`, and `Ca`; no inferred substitutes. |
| `coefficients` | object/null | optional, null | Requires finite `alpha`, `beta`, `gamma`; optional finite positive `epsilon`. |
| `coefficient_model_id` | string | optional, `offtarget_toxicity_prototype` | Uses registered coefficient metadata. |
| `max_mismatches` | integer | optional, `4` | 0–10 for optional off-target search. |

The audited formula is `B=abs(delta_g_binding)/(abs(delta_g_binding)+epsilon)`,
`z=alpha*Sh+beta*B+gamma*Ca`, and `T=100*stable_logistic(z)`. `Sh` is a
mismatch penalty, `B` is bounded binding stability, and `Ca` is accessibility.
Expected fitted signs are alpha negative, beta positive, and gamma positive,
but signs are learned calibration parameters and are not hard-coded.

The result exposes feature availability, individual contributions, linear and
logistic scores, toxicity risk, formula/coefficient/calibration metadata,
warnings, errors, and provenance. Missing `Sh`, binding DeltaG, or Ca yields
`unavailable`/`partial` and a null score. Explicit features plus user
coefficients yield `prototype`, `validated: false`. Only calibrated metadata
with an identified dataset and fit metrics can produce `validated: true`.

The frontend must never map CFD or mismatch count to Sh, guide MFE to binding
DeltaG, or attention to Ca. Positive DeltaG, non-finite values, non-positive
epsilon, invalid coefficients, and invalid guide sequences must be rejected.

#### `GET /backend/status`

No arguments. Returns `{active_connector, available_connectors,
backend_url, mcp_available, tool_count}`. Current connectors are `http` and
`mcp`; `backend_url` is present for HTTP and null for MCP.

#### `POST /backend/active`

Request JSON: `{connector: string}`. Allowed values: `http`, `mcp`. Success
returns backend status. Invalid connector returns HTTP `422`; changing while a
matching execution is running returns HTTP `409`. Selection affects future
executions only.

#### `GET /tools`

No arguments. Returns `{total_tools, connector, tools}`. Each live tool entry
contains the backend-provided fields `name`, `description`,
`argument_schema`, `availability`, `connector_source`, `tier`, and `cost`.
The frontend must use this live list and must not invent tool arguments.

#### `POST /executions`

Request JSON is `ExecutionBody`:

| Field | Type | Required/default | Restrictions |
|---|---|---|---|
| `tool_calls` | array<object> | optional, `[]` | Use live tool schemas; calls execute sequentially. |
| `parallel_groups` | array<object> | optional, `[]` | Each group has `calls`; calls in a group execute concurrently. |
| `ai_request` | object/null | optional, null | If present, the current implementation expects a `message` field for AI generation. |
| `connector` | string/null | optional, active connector | Must be `http` or `mcp`. |
| `provider_id` | string/null | optional, active provider | Must be registered if supplied. |
| `model` | string/null | optional, active model | Must be available for the selected provider. |
| `input_ids` | array<string> | optional, `[]` | Every ID must exist in the validated input registry. |

Success: HTTP `202` with `{execution_id, status: "started", created_at}`;
`created_at` may initially be null because execution scheduling is asynchronous.
Invalid input/path arguments return HTTP `400`; invalid connector/provider
configuration returns HTTP `422`.

#### `GET /executions`

No arguments. Returns `{executions: array<ExecutionStatus>}` for process-local
history.

#### `GET /executions/{execution_id}`

Path `execution_id: string`, required. Returns status fields including
`execution_id`, `status`, `started_at`, `finished_at`, `elapsed_ms`, active and
completed tool/AI counts, `reasoning_active`, `generation_active`, `connector`,
`provider`, `model`, `validated_inputs`, `assistant_output`,
`deterministic_evidence`, `tool_calls`, `errors`, and `warnings`.
Statuses currently observed are `queued`, `running`, `completed`, and `failed`.
Unknown IDs return HTTP `404`.

#### `GET /executions/{execution_id}/tools`

No body. Returns `{execution_id, tools, parallel_groups}`. Each tool call
contains `call_id`, `execution_id`, `tool`, `connector`, `arguments`, `status`,
`started_at`, `finished_at`, `duration_ms`, `success`, structured `result`,
`errors`, `warnings`, and `metadata`. The result preserves `rows`, `summary`,
`errors`, `warnings`, and `metadata` from the backend.

#### `GET /executions/{execution_id}/tools/{call_id}`

Path IDs are required. Returns one tool-call object as above; unknown execution
or call returns HTTP `404`.

#### `GET /executions/{execution_id}/ai`

Returns `{execution_id, requests}`. Each request contains `request_id`,
`provider`, `model`, `started_at`, `finished_at`, `duration_ms`, `status`,
`usage`, and `finish_reason`. It never contains hidden prompts or reasoning
content.

#### `GET /executions/{execution_id}/stream`

No body. Returns SSE (`text/event-stream`). Each event has an `event:` name and
JSON `data` containing `event_id`, `event`, `execution_id`, `timestamp`, plus
safe event data. Current event names include `execution_started`,
`tool_call_started`, `tool_call_completed`, `tool_call_failed`,
`parallel_group_started`, `parallel_group_completed`, `ai_request_started`,
`ai_generation_started`, `ai_generation_completed`, `ai_generation_failed`,
`ai_stream_chunk`, `execution_completed`, `execution_failed`, and
`execution_finished`.

Completed executions replay stored event history and then close. Running
executions receive live events. `ai_stream_chunk` is currently one complete
provider response when `stream: true`; it is not token-level streaming.

## Conversation and prompt endpoints

#### `POST /conversations`

No arguments. Returns HTTP `201` with `conversation_id`, `created_at`,
`updated_at`, nullable `provider`/`model`, `messages: []`, and
`execution_ids: []`.

#### `GET /conversations`

No arguments. Returns `{conversations: array<conversation>}`.

#### `GET /conversations/{conversation_id}`

Returns one conversation. Unknown ID returns HTTP `404`.

#### `POST /conversations/{conversation_id}/messages`

Request JSON is an untyped object with required `content: string` and optional
`role: string` defaulting to `user`. The current implementation does not
enforce a role enum or content length; frontend should use `system`, `user`, or
`assistant` and non-empty content. Returns the updated conversation. Missing
conversation/content returns HTTP `404`.

#### `DELETE /conversations/{conversation_id}`

No body. Clears/removes the conversation and returns
`{deleted: true, conversation_id}`. Unknown ID returns HTTP `404`.

#### `POST /prompts/preview`

Request JSON is an untyped object:

| Field | Type | Required/default |
|---|---|---|
| `system_instructions` | string | optional, `"You are the VEYRA MIDEND assistant."` |
| `developer_context` | string/null | optional, null |
| `history` | array<object> | optional, `[]`; entries should be `{role, content}` |
| `user_message` | string | optional, `""` |
| `tool_results` | array<object>/null | optional, null |

Returns `{messages: array<{role: string, content: string}>}` in the structured
order system, developer context, conversation history, tool-produced evidence,
and user message. This preview contains no hidden chain-of-thought.

## Current MIDEND MCP surface

The registry is `veyra/midend/mcp_interface.py:MIDEND_MCP_CAPABILITIES`.
Operations are async and return the same JSON-like objects as their HTTP
counterparts:

| MCP name | Arguments | Purpose / response |
|---|---|---|
| `ai_status` | none | Same safe object as `GET /ai/status`. |
| `list_ai_providers` | none | `{providers: [...]}` like `GET /ai/providers`. |
| `backend_status` | none | Same object as `GET /backend/status`. |
| `list_tools` | none | Same live tool discovery object as `GET /tools`. |
| `execution_status` | `execution_id: string`, required | Same execution status object as `GET /executions/{execution_id}`; unknown ID raises `KeyError`. |
| `list_skills` | none | Same skill list as `GET /skills`. |
| `skill_metadata` | `skill_id: string`, required | Same metadata as `GET /skills/{skill_id}`. |
| `skill_status` | `skill_id: string`, required | Skill-specific formula, feature-availability, and calibration status. |
| `execute_skill` | `skill_id: string`, `request: object`, required | Starts the same skill execution as `POST /skills/{skill_id}` and returns its execution ID. |
| `calibration_status` | none | Calibration registry status and registered coefficient models. |
| `calibration_metadata` | `calibration_id: string`, required | Dataset metadata for validated CSV/TSV calibration input. |
| `list_calibration_datasets` | none | List of all registered calibration datasets. |

There are currently no MCP operations for provider mutation, model selection,
connector selection, file upload, execution creation, tool-call inspection,
SSE events, AI request inspection, conversation management, or prompt preview.
Frontends must use HTTP for those operations until the MCP registry is
explicitly extended.

## Frontend Call Rules

Before each call, enforce these exact rules:

1. Before `POST /inputs/file`, require multipart upload, a safe basename,
   supported extension, size ≤ 50 MiB, and reject known GFF/GFF3/plain-text
   file inputs. Still rely on MIDEND content validation; do not bypass it.
2. Before `POST /ai/config` or `POST /ai/providers`, require non-empty HTTPS/HTTP
   base URL, non-empty model/default model, and non-empty API key; never place
   the key in rendered output. Keep `persist` false.
3. Before `POST /ai/active`, ensure the provider and model came from
   `GET /ai/providers`.
4. Before `POST /backend/active` or an execution connector override, allow only
   `http` or `mcp`; do not switch an active running execution.
5. Before any tool call, obtain `GET /tools`, use the exact live tool name and
   argument schema, reject filesystem path arguments, and use validated
   `input_ids` for uploaded files.
6. Before `POST /ai/chat` or `POST /executions`, verify every conversation ID,
   provider/model selection, and input ID locally where possible; reject empty
   messages and arbitrary paths.
7. Treat execution responses as asynchronous. Poll the execution status or
   consume its SSE stream; render only public assistant output and safe state.
8. Treat `reasoning_active` and `generation_active` as indicators only. Never
   render reasoning content, hidden tokens, scratchpads, or provider internals.
9. Treat `rows`, `summary`, `warnings`, `errors`, timings, and provenance as
   structured data; do not reconstruct results from logs or claim the AI did a
   deterministic backend calculation.
10. Map HTTP and MCP operations to the same UI semantics and do not assume MCP
    supports operations absent from the current registry.
11. Before `POST /skills/{skill_id}` or MCP `execute_skill`, allow exactly one
    input mode, enforce `strand`, `depth`, range, and candidate limits, and
    require `genome_id` for `full` depth.
12. Treat a skill result as computational prediction only. Never render it as
    experimentally confirmed cleavage, and never replace null/unavailable
    evidence with zero or an estimated value.
