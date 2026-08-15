# VEYRA MIDEND

The MIDEND starts without AI credentials. Deterministic HTTP/MCP backend
connectors remain available and `/health` reports `ai_configured: false` until
an API key is configured.

## Environment

Copy `.env.example` to `.env` and set `MIDEND_AI_BASE_URL`,
`MIDEND_AI_API_KEY`, and `MIDEND_AI_MODEL`. Environment configuration is read
at process start; runtime configuration takes precedence over it.

## CLI

From the repository root, use `python -m veyra.midend ai status` and
`python -m veyra.midend ai configure --base-url ... --model ...`. The latter
prompts for the key without echoing it. `--no-persist` keeps it process-local;
the public control plane never persists API keys in plaintext. `midend ai test` is the only CLI
operation that makes a provider network request.

## FastAPI

Run `uvicorn veyra.midend.http_api.app:app --port 8080`.

* `GET /ai/config` returns provider, URL, model, configured state, source, and
  only a boolean key status.
* `POST /ai/config` accepts `base_url`, `api_key`, and `model`; keys remain
  process-local.
* `POST /ai/test` explicitly tests the configured provider.
* `POST /ai/chat` returns `ai_provider_not_configured` (without a traceback)
  when no key is present.

API keys are never returned, logged, placed in telemetry, or included in
provider errors. The provider is generic OpenAI-compatible infrastructure and
does not contain LLM7-specific request logic.
