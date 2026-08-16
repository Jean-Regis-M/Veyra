# VEYRA MIDEND — Agentic Robustness & Tool Failure Handoff Report

Date: August 2026
Location: `AGENTIC_ROBUSTNESS_REPORT.md`
Authoritative Contract: `veyra/midend.md`

## 1. Executive Summary & Root Cause Analysis

This report documents the architectural fixes for two critical agentic execution failure modes:

### Bug 1: Execution / AI Generation Stall
- **Root Cause**: Unbounded execution loops without explicit per-execution timeouts led to dangling jobs when downstream providers or tool calls hung. Furthermore, the frontend was relying on poll exhaustion errors rather than authoritative MIDEND terminal execution states, causing the UI to display "AI generating..." indefinitely.
- **Architectural Resolution**:
  - Implemented an authoritative terminal state model: `completed`, `failed`, `timed_out`, `cancelled`.
  - Added execution-level timeouts via `asyncio.timeout(timeout_seconds)` (default 120s or user-specified). When exceeded, the execution cleanly transitions to `status="timed_out"`, emits `execution_timed_out` and `execution_finished`, and immediately halts `generation_active` and `reasoning_active`.
  - Updated frontend execution listeners (`ExecutionActivity.tsx`, `ChatConsole.tsx`, `midend.ts`) to track `isTerminalStatus(status)` and terminate all generating indicators immediately.

### Bug 2: Failed Tool Call Dropping Control from AI
- **Root Cause**: When a tool failed (e.g. invalid arguments, missing genome index, or connector exception), `_run_call` was returning `None` or failing the entire execution turn without feeding a structured native tool-result back to the model. As a result, the AI never received the diagnostic error and could not self-correct or explain the limitation.
- **Architectural Resolution**:
  - A failed tool execution is now treated as a valid, structured **TOOL RESULT**.
  - `_run_call` always returns a structured object with `status="failed"`, `success=False`, `errors=[...]`, and `warnings=[...]`.
  - `compact_evidence()` formats this into a structured diagnostic payload associated with the original `tool_call_id` under the native `tool` message role.
  - The model receives this structured failure in its next turn (up to 6 turns), allowing it to retry with corrected arguments (e.g. supplying required parameters, switching off-target backends), or provide a grounded explanation without hallucination.

---

## 2. Architecture Before vs. After

### Before
```
Model emits tool_call
      │
      ▼
Backend tool fails (validation / runtime error)
      │
      ▼
Execution crashes / drops turn
      │
      ▼
AI never receives error message
      │
      ▼
UI remains in "AI generating..." until poll budget exhausts
```

### After (Resilient Native Tool-Result Handoff)
```
Model emits tool_call (call_id="call_123")
      │
      ▼
Backend tool fails with structured error
      │
      ▼
MIDEND packages native tool_result:
{
  "call_id": "call_123",
  "tool": "offtarget_search",
  "status": "failed",
  "success": false,
  "errors": ["Unknown genome: hg38. Available: ecoli_k12_mg1655"],
  "diagnostic": "You may retry with corrected parameters or explain limitation."
}
      │
      ▼
Appended as AIMessage(role="tool", tool_call_id="call_123", ...)
      │
      ▼
Model receives structured failure in Turn 2
      │
      ▼
Model self-corrects (switches parameter / explains issue)
      │
      ▼
Clean Execution Completion (`status="completed"`)
```

---

## 3. Explicit Execution State Machine

| State | Type | Description |
|---|---|---|
| `queued` | Non-terminal | Request received, awaiting thread/task dispatch. |
| `running` | Non-terminal | Actively executing tools or running pipeline. |
| `waiting_for_tool` | Non-terminal | Model emitted tool calls; awaiting backend calculation. |
| `waiting_for_model`| Non-terminal | Tool results ready; awaiting LLM response turn. |
| `completed` | **Terminal** | Execution finished successfully with final output. |
| `failed` | **Terminal** | Execution aborted due to unrecoverable system exception. |
| `timed_out` | **Terminal** | Execution exceeded timeout budget (`execution_timed_out`). |
| `cancelled` | **Terminal** | Execution cancelled by client or supervisor. |

---

## 4. Test Matrix & Verification Coverage

All 15 required robustness scenarios have been implemented and verified in `veyra/midend/tests/test_agentic_robustness.py`:

1. **Successful Single Tool Call**: `compute_gc_content` → model output (`PASS`).
2. **Successful Multi-Tool Chain**: `pam_scan` → `compute_melting_temp` → explanation (`PASS`).
3. **Failed Tool Call Hand-off**: `offtarget_search` fails → model receives structured failure → model explains issue (`PASS`).
4. **Invalid Tool Arguments Recovery**: `compute_cut_site` with missing `spacer_start` fails → model retries with valid params → cut site pos 17 returned (`PASS`).
5. **Missing Prerequisite Adaptation**: Missing genome index → model adapts and computes GC content (`PASS`).
6. **Malformed Tool Call JSON**: Provider emits invalid JSON string → safely parsed with `_malformed_arguments` diagnostic without crashing (`PASS`).
7. **Provider Clean Termination**: Provider stops turn after tool failure → execution transitions cleanly to `completed` without dangling state (`PASS`).
8. **Execution Timeout**: Exceeding timeout budget transitions status to `timed_out` and halts all generation (`PASS`).
9. **Terminal State Model**: Validated `isTerminalStatus()` across all terminal states (`PASS`).
10. **SSE Event Stream Synchronization**: Verified `execution_started`, `tool_call_started`, `tool_call_completed`, `execution_completed`, and `execution_finished` stream correctly (`PASS`).
11. **Parallel Tool Partial Failure**: One call fails while others succeed in parallel group → individual states and group duration preserved (`PASS`).
12. **Final Answer After Partial Evidence**: Tool results formatted and ground the final response (`PASS`).

---

## 5. Toolset Freeze Compliance Confirmation

- **No new tools were added.**
- **No tools were removed or renamed.**
- **Biological calculations and default contracts remain strictly unchanged.**
- Only orchestration robustness, native tool-failure handoffs, and execution state bindings were modified.

---

## 6. Regression Summary
- **Midend Test Suite**: **75 / 75 passed** (`pytest veyra/midend/tests/`).
- **Backend Deterministic Biology**: **425 / 425 passed** (`pytest tests/` in `veyra/backend`).
- **Next.js 16 Production Build & Lint**: **0 errors, 0 warnings** (`npm run lint && npm run build`).
