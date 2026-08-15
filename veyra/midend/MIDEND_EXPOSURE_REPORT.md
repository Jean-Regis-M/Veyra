# MIDEND Exposure Report

## AI provider status and management

Added `/ai/status`, `/ai/providers`, `/ai/active`, `/ai/test`, and asynchronous
`/ai/chat`. Providers are generic OpenAI-compatible records with runtime
provider/model selection and no credential fields in public objects.

## Backend and tools

Added `/backend/status`, `/backend/active`, and live `/tools` discovery. The
existing HTTP/MCP connector factory is retained; connector selection affects
future executions only.

## Executions, timing, and results

Added process-local execution tracking for sequential and parallel tool calls,
individual wall-clock timings, group timings, structured rows/summary/errors/
warnings/metadata, AI request metadata, deterministic evidence, final output,
and execution history. SSE is exposed at
`/executions/{execution_id}/stream` with lifecycle event IDs.

## Reasoning visibility and security

Only safe generation/reasoning state is exposed. No private chain-of-thought,
scratchpad, reasoning tokens, API keys, authorization headers, or secret-shaped
metadata are returned. New exposure endpoints keep provider keys process-local;
plaintext persistence is rejected by the public provider-management API.

## Conversations and prompts

Added conversation CRUD, message append, execution linkage, and a structured
`PromptBuilder` with a `/prompts/preview` endpoint. System, developer,
conversation, tool evidence, and user sections remain distinct.

## File input validation

Added `POST /inputs/file` and a dedicated validator for the backend-supported
FASTA, FASTQ, and GenBank formats. It enforces filename/content agreement,
UTF-8 and nucleotide structure, a 50 MiB limit, safe filenames, and structured
errors before any AI or backend execution. Valid uploads receive a process-local
input ID and safe parsed metadata; execution and chat requests can reference
only those IDs.

## Tests and smoke tests

The focused MIDEND suite passes with mocked provider behavior and covers safe
startup/configuration, redaction, runtime configuration, and measured provider
responses. The MIDEND suite passes 9 tests. The backend suite reports 421
passed and 6 skipped, with one pre-existing cwd-sensitive standalone CLI test
failure; the same CLI command succeeds from `veyra/backend`. Environment-backed
smoke checks passed for AI status, 21-tool discovery, HTTP connector execution,
MCP connector execution, and the explicit provider test with safe request ID and
latency metadata. No API key was printed or returned.

## Known limitations

State is in-memory and process-local, streaming currently emits lifecycle
events rather than provider token streaming, and authentication/rate limiting
for the public API must be supplied by the deployment boundary.
