# Runtime AI provider

AI is optional infrastructure. MIDEND startup never contacts the provider and
does not fail when `MIDEND_AI_API_KEY` is absent. `GET /health` and
`GET /ai/config` expose only safe status metadata.

Configuration precedence is runtime configuration, then environment variables
(including the local `.env`), then the defaults `https://api.llm7.io/v1` and
model `default`. The provider is OpenAI-compatible, so any compatible HTTPS
endpoint can be selected.

Provider configuration exposed through the control plane is process-local.
Plaintext API-key persistence is disabled; the public provider endpoints reject
`persist: true`. Environment configuration can still be supplied by the
deployment through its own secret-management mechanism.

`midend ai test` and `POST /ai/test` are explicit real network checks. No test
request is performed on startup. AI requests without a key return the
structured code `ai_provider_not_configured` and remediation instructions.
