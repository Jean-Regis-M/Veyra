# VEYRA MIDEND — Context & Tool Discovery Pipeline Audit (Step 0)

Date: August 2026
Location: `veyra/midend/CONTEXT_AUDIT.md`

## 1. Executive Summary

This audit establishes the baseline for how tools, schemas, conversation history, input artifacts, and deterministic computational evidence are passed to AI models in the VEYRA MIDEND orchestration runtime.

Currently:
- 17 native tools/skills are defined in `veyra/midend/ai/tool_definitions.py`.
- In every AI turn, the entire set of 17 full tool JSON schemas is passed directly to the provider in `tools: [...]`.
- File attachments inject raw sequence slices (up to 600 bp) into the user prompt string.
- Conversation history is appended linearly without bounded windowing or structured state summary.
- Tool outputs are formatted into JSON strings and injected as `tool` role messages.

---

## 2. Component Pipeline Map

### 2.1 Where Tools are Registered
- **Backend Tools**: Implemented in `veyra/backend/core/` and exposed via FastAPI (`veyra/backend/http_api/app.py`) and MCP connectors (`veyra/midend/connectors/`).
- **Skills**: Implemented in `veyra/midend/skills/` (`spcas9_gene_cutting.py`, `offtarget_toxicity.py`, `model_calibration.py`) and registered in `veyra/midend/skills/registry.py`.
- **Native AI Tool Registry**: Statically declared in `veyra/midend/ai/tool_definitions.py` (`NATIVE_TOOLS_DEFINITIONS`) and retrieved via `get_native_tools()`.

### 2.2 Where Tool Schemas are Generated
- Full JSON Schema objects are generated statically in `veyra/midend/ai/tool_definitions.py` with OpenAPI/JSON-Schema types, enums, descriptions, and default values.
- Authoritative default dictionary (`AUTHORITATIVE_DEFAULTS`) and unit map (`PARAMETER_UNITS`) reside in `veyra/midend/ai/tool_definitions.py`.

### 2.3 Where Prompts are Assembled
- **Assembly Logic**: `PromptBuilder.build()` in `veyra/midend/control_plane.py` (lines 335-349).
- **System Instructions**: Hardcoded in `ControlPlane._run_ai` (lines 735-746) specifying the assistant identity, tool use rules, and available tool names.
- **Developer Context / System Evidence**: Statically prefixed to message list if provided.

### 2.4 Where Conversation History is Assembled
- `ConversationStore` in `veyra/midend/control_plane.py` (lines 307-333) maintains an in-memory list of `{"role": ..., "content": ...}` messages.
- `PromptBuilder.build()` linearly dumps all messages from `conversation["messages"]` into `messages`.

### 2.5 Where Tool Results are Injected
- During the multi-turn loop in `ControlPlane._run_ai` (lines 757-807):
  - Model tool call → `ControlPlane._run_call()` executes deterministic backend tool / skill.
  - Formatted via `format_tool_result_for_ai(fn_name, call_res)` in `veyra/midend/control_plane.py` (lines 70-129).
  - Injected as `AIMessage(role="tool", tool_call_id=..., name=..., content=tool_content)`.
- Pre-existing deterministic evidence is also injected as `AIMessage(role="system", content="TOOL-PRODUCED EVIDENCE:...")` in `PromptBuilder.build()`.

### 2.6 Where Skills are Injected
- Skills (`spcas9_gene_cutting`, `offtarget_toxicity_risk`, `model_calibration`) are listed alongside atomic tools in `NATIVE_TOOLS_DEFINITIONS`.
- In `ControlPlane._run_call()` (lines 604-623), if the requested tool name matches a registered skill, it routes execution to `skill.execute()`.

### 2.7 Where Provider-Native Tools are Passed
- In `ControlPlane._run_ai` (line 764):
  `OpenAICompatibleProvider(record.config).generate(messages, execution.model, tools=native_tools)`
- `OpenAICompatibleProvider.generate()` in `veyra/midend/ai/openai_compatible.py` packages `tools` into the HTTP request body `{"tools": tools, "tool_choice": "auto"}`.

### 2.8 Where Context is Rebuilt Each Request
- In `ControlPlane._run_ai()`:
  - Validated input metadata from `execution.validated_inputs` is iterated to generate `input_summaries` (reading sequence preview bytes and appending to `effective_user_message`).
  - `PromptBuilder.build()` reconstructs `messages`.
  - `get_native_tools()` returns all 17 tool definitions.
  - Each subsequent turn in the while loop appends assistant messages and tool responses until termination.

---

## 3. Opportunities for Token & Context Optimization

1. **Layered Tool Discovery**:
   - Instead of transmitting all 17 full tool schemas (which consume ~2,500+ tokens) in every initial call, provide a compact tool directory and dynamically select active full schemas based on the active skill, user task intent, and attached input class.
2. **Authoritative Cached Tool Catalog**:
   - Cache tool metadata, categories, cost tiers, and prerequisites in-memory to drive dynamic schema provisioning.
3. **Evidence Compaction**:
   - Large results (e.g. 50+ PAM sites, 1,000 off-target hits) must be summarized with key statistics and top representative rows for the LLM while retaining the full dataset under the execution/call ID for frontend rendering.
4. **Input Context Referencing**:
   - Refer to files by `input_id` and metadata rather than embedding multi-line raw sequence chunks in the prompt string.
5. **Session / Conversation Compaction**:
   - Retain recent dialogue turns verbatim, but summarize older conversation history while retaining pointers to authoritative execution IDs and input IDs.

---

## 4. Verification Baseline
- 37/37 Midend pytest integration tests passing.
- 425/425 Backend deterministic tests passing.
