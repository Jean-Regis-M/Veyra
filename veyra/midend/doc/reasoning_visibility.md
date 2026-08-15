# Reasoning visibility

The exposure API publishes state flags only: `reasoning_active`,
`generation_active`, active tool calls, tool names, timing, structured results,
and final assistant output. It never publishes private chain-of-thought,
scratchpad text, hidden reasoning tokens, or authorization data.

SSE events are named lifecycle events such as `ai_request_started`,
`tool_call_started`, `tool_call_completed`, and `execution_completed`.
Provider-specific reasoning fields are not copied into user-facing output.
