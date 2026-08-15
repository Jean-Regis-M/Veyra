# VEYRA Frontend + MIDEND Architecture Plan

## Purpose

This document defines how the frontend/site, public APIs, deterministic backend, and MIDEND AI layer should be designed.

**Core rule:** Raw VEYRA computation and MIDEND AI orchestration are separate interfaces.

---

## 1. High-Level Architecture

```text
                         VEYRA
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
       RAW BACKEND                  MIDEND AI
       deterministic               AI infrastructure
       computation                 + orchestration
              │                         │
        HTTP / MCP / API          HTTP / MCP / API
              │                         │
              ▼                         ▼
        VEYRA tools                 LLM + skill.md
                                  + tool planning
                                  + chaining
                                  + interpretation
                                         │
                                         ▼
                                  VEYRA backend
```

The frontend must support both modes.

---

## 2. Raw Backend

The backend is the deterministic computational engine.

It provides:

- sequence ingestion
- PAM discovery
- candidate generation
- GC and sequence properties
- Tm
- secondary structure / MFE
- positional features
- dinucleotide composition
- seed GC
- cut-site calculation
- BWA off-target search
- Cas-OFFinder mismatch/bulge search
- mismatch/seed analysis
- CFD scoring
- on-target model inference
- candidate ranking
- model/runtime management
- genome/index/cache management

The backend must remain usable **without an LLM**.

### Direct backend access

```text
Client
  │
  ├── HTTPS
  ├── MCP
  └── direct API/programmatic access
        │
        ▼
   VEYRA Backend
```

A researcher or application should be able to call the backend directly and receive deterministic results.

**Do not force raw-backend users through the MIDEND.**

---

## 3. MIDEND

The MIDEND is VEYRA's AI infrastructure.

It does not replace the backend.

It provides:

- local/hosted LLM inference
- `skill.md` behavioral rules
- tool selection
- argument generation
- validation before tool calls
- multi-tool chaining
- execution state
- evidence accumulation
- error handling
- provenance tracking
- final interpretation

The MIDEND model should reason over backend evidence rather than reimplementing biological calculations.

### MIDEND flow

```text
User request
    │
    ▼
MIDEND LLM
    │
    ├── understand goal
    ├── inspect available tools
    ├── choose tool
    ├── generate arguments
    ├── call backend
    ├── inspect result
    ├── decide next tool
    └── stop when evidence is sufficient
    │
    ▼
Final AI response
```

---

## 4. MIDEND Must Not Duplicate Backend Logic

The MIDEND must not implement its own:

- GC calculation
- PAM matching
- CFD calculation
- off-target search
- coordinate calculations
- Tm calculation
- MFE calculation
- model scoring formulas
- ranking mathematics

Instead:

```text
AI needs GC
    ↓
compute_gc_content
    ↓
backend result
    ↓
AI interprets result
```

The backend remains the computational authority.

---

## 5. `skill.md`

The MIDEND LLM will receive a behavioral `skill.md`.

`skill.md` defines:

- when tools must be used
- when tools must not be used
- evidence requirements
- chaining behavior
- error handling
- provenance requirements
- stopping conditions
- distinction between deterministic facts and AI interpretation

### Core rule

> No biological interpretation of a claim that can be resolved by an available VEYRA tool until that tool has been called.

Example:

Bad:

> “This guide probably has good GC.”

Correct:

```text
compute_gc_content
    ↓
actual GC result
    ↓
interpret result
```

The MIDEND should also avoid unnecessary repeated calls when evidence is already available.

---

## 6. MIDEND Contract

The MIDEND uses:

```text
midend.md
```

as the machine-facing backend contract.

It defines:

- available operations
- parameters
- defaults
- valid ranges
- dependencies
- errors
- result structures
- costs
- side effects
- provenance
- logical tool composition

The frontend should not manually recreate backend validation or scientific schemas.

Where possible, frontend clients should derive request forms and metadata from the live API/schema layer.

---

## 7. Two Public Service Surfaces

Deployment should expose two independently usable services.

### A. Backend API

Conceptual namespace:

```text
/api/backend/*
```

Purpose:

> Raw deterministic VEYRA computation.

Examples:

```text
sequence tools
PAM search
off-target search
CFD
ranking
model status
genome operations
```

No AI required.

### B. MIDEND API

Conceptual namespace:

```text
/api/midend/*
```

Purpose:

> AI-assisted orchestration over VEYRA.

The MIDEND can:

- accept natural-language requests
- select backend tools
- chain calls
- return interpreted results
- preserve evidence and provenance

Exact route naming can differ, but the conceptual separation should remain.

---

## 8. MCP Exposure

Both layers may expose MCP.

### Backend MCP

```text
AI/client
    ↓
backend MCP
    ↓
raw deterministic VEYRA tools
```

For callers wanting direct tool control.

### MIDEND MCP

```text
AI/client
    ↓
MIDEND MCP
    ↓
LLM orchestration
    ↓
backend
```

For callers wanting VEYRA's own AI infrastructure.

Do not collapse the two interfaces into one ambiguous MCP surface.

---

## 9. Frontend Modes

The frontend should make the two modes visually distinct.

### Mode A — AI / MIDEND

```text
Natural-language request
        ↓
AI planning
        ↓
tool execution
        ↓
evidence
        ↓
interpreted result
```

Useful UI:

- chat/request panel
- tool activity timeline
- task status
- evidence collected
- provenance
- tools invoked
- warnings/errors
- final interpretation

The UI must not imply that the LLM directly calculated a deterministic value.

### Mode B — Raw Analysis

```text
Input
  ↓
Select tool / pipeline
  ↓
Configure parameters
  ↓
Run backend
  ↓
Raw deterministic result
```

Useful UI:

- sequence input
- genome selection
- PAM settings
- off-target settings
- model selection
- ranking settings
- result tables
- coordinates
- scores
- provenance

This mode must not require conversational AI.

---

## 10. Frontend Architecture Rules

The frontend must not:

- duplicate scientific formulas
- duplicate validation logic
- assume model availability
- hardcode Rule Set 2/3 availability
- hardcode genome IDs
- hardcode score scales
- invent fallback behavior
- assume every tool exists on every interface
- assume every score is 0–1
- treat missing scores as zero
- invent scientific interpretations

The frontend consumes:

- API schemas
- model metadata
- tool metadata
- result/provenance metadata
- `midend.md`

---

## 11. Result Presentation

Clearly distinguish:

### Deterministic evidence

Examples:

```text
GC%
Tm
MFE
PAM
cut position
off-target count
mismatch positions
CFD
model score
ranking score
```

### AI interpretation

Examples:

```text
why a candidate was selected
trade-off explanation
summary
natural-language interpretation
```

The UI should visually distinguish these categories.

Never present an AI interpretation as experimental or deterministic evidence.

---

## 12. Provenance

Important displayed results should retain provenance where provided:

```text
tool_name
tool_version
backend
model_id
model_version
genome_id
search_backend
ranking_method
runtime
```

AI-generated explanations should retain the deterministic evidence used to generate them.

---

## 13. Tool Chaining Visualization

The MIDEND UI should expose a tool execution timeline.

Example:

```text
1. PAM scan                  ✓
2. GC analysis               ✓
3. Tm analysis               ✓
4. Secondary structure       ✓
5. Cas-OFFinder search       ✓
6. Mismatch/seed analysis   ✓
7. CFD                       ✓
8. Rule Set 3                ✓
9. Candidate ranking         ✓
10. AI interpretation       ✓
```

Clicking a tool should expose:

- arguments
- execution status
- result summary
- warnings
- errors
- provenance
- cost/status where available

Show what the system did, not hidden chain-of-thought.

---

## 14. AI Tool-Calling Guardrails

The MIDEND UI should show concise operational activity:

```text
Planning
    ↓
Calling VEYRA tool
    ↓
Backend result
    ↓
Next action
```

Do not expose private reasoning.

Only expose:

- action descriptions
- tool name
- arguments when appropriate
- result summary
- errors
- evidence

---

## 15. Error Handling

The UI must distinguish:

### Validation error
Invalid user parameters.

### Backend error
The deterministic engine failed.

### Runtime/model unavailable
A requested model/runtime is unavailable.

### Unsupported operation
The selected backend cannot perform the request.

### AI orchestration failure
The MIDEND failed to plan or chain the task.

Never convert these into fake successful output.

---

## 16. Model Support

Do not hardcode one LLM provider.

Use a model abstraction:

```text
MIDEND MODEL PROVIDER

local_llama_cpp
    ↓
local model

api_provider
    ↓
remote API model

future_provider
    ↓
other model
```

The orchestration layer should work regardless of the underlying LLM.

The model is replaceable.

The VEYRA backend is not.

---

## 17. Local llama.cpp

Initial MIDEND development should support a local llama.cpp model:

```text
MIDEND
  │
  ▼
llama.cpp server/runtime
  │
  ▼
local model
```

The LLM should receive:

- `skill.md`
- relevant `midend.md` contract information
- tool definitions
- task context
- previous tool results

Do not give the model the backend source tree as its primary interface.

---

## 18. Model API Abstraction

Keep provider communication separate from tool orchestration.

Conceptually:

```python
class ModelProvider:
    def generate(...)
    def stream(...)
    def tool_call(...)
```

Possible providers:

```text
LlamaCppProvider
RemoteAPIProvider
FutureProvider
```

The provider handles model communication.

The orchestrator handles planning and chaining.

---

## 19. Execution State

The MIDEND should maintain state similar to:

```yaml
task:
  user_goal: ...

context:
  sequence: ...
  genome_id: ...

evidence:
  pam_sites: ...
  sequence_features: ...
  off_targets: ...
  mismatch_analysis: ...
  cfd: ...
  on_target: ...
  ranking: ...

execution:
  completed_tools: []
  pending_tools: []
  failed_tools: []

final:
  answer: ...
  provenance: []
```

This enables evidence reuse.

If GC was already computed, the MIDEND should not recompute it unless inputs or parameters changed.

---

## 20. Security Boundary

The backend remains authoritative for:

- validation
- parameter enforcement
- filesystem restrictions
- runtime provisioning
- external tool execution
- model availability

The MIDEND must not bypass these controls.

The LLM must never construct arbitrary:

- shell commands
- package installation commands
- executable paths
- arbitrary download URLs
- filesystem operations

The MIDEND requests existing safe backend operations.

---

## 21. Frontend Navigation

Recommended high-level structure:

```text
VEYRA
│
├── Home
├── AI / MIDEND
│   ├── Chat
│   ├── Tool Activity
│   └── Evidence
│
├── Raw Analysis
│   ├── Sequence
│   ├── PAM
│   ├── Off-target
│   ├── Scoring
│   └── Ranking
│
├── Genomes
├── Models
├── API
├── MCP
└── Documentation
```

Exact UI can differ, but raw backend and MIDEND must remain conceptually distinct.

---

## 22. API Documentation

The site should expose documentation for two independent surfaces.

### Backend API docs

> Direct deterministic VEYRA computation.

Include:

- HTTP API
- MCP
- schemas
- examples
- results

### MIDEND API docs

> AI orchestration and interpretation over VEYRA.

Include:

- model configuration
- natural-language requests
- tool planning
- execution state
- evidence
- streaming
- MCP
- API examples

Do not mix the two into one ambiguous API.

---

## 23. Branding / Product Positioning

Recommended positioning:

> **VEYRA — deterministic genomic intelligence with an optional AI reasoning layer.**

Avoid positioning the backend itself as an LLM product.

Backend:

> Computes genomic evidence.

MIDEND:

> Reasons over genomic evidence.

---

## 24. What the Frontend Developer Must NOT Do

Do not:

- make MIDEND mandatory
- hide raw backend access
- create a UI-only scoring system
- duplicate backend parameter validation
- assume all models are installed
- assume Rule Set 2 is always available
- assume every output is a probability
- invent scientific terminology
- present LLM interpretation as deterministic fact
- hardwire a specific LLM provider
- couple the UI directly to internal Python modules

---

## 25. Development Order

### Phase A — Shared client layer

```text
Frontend
   ↓
API abstraction
   ├── Backend client
   └── MIDEND client
```

### Phase B — Raw backend views

Build deterministic analysis views first.

### Phase C — MIDEND UI

Build conversational/orchestration UI.

### Phase D — Evidence visualization

Build tool activity and evidence views.

### Phase E — API/MCP documentation

Expose both contracts clearly.

### Phase F — llama.cpp integration

Connect the local model to the MIDEND.

### Phase G — Remote providers

Add API-hosted model providers later.

---

## 26. Definition of Done

The architecture is correct when:

### Raw mode

```text
User / application
   ↓
Backend HTTP/MCP/API
   ↓
VEYRA deterministic computation
```

works without AI.

### AI mode

```text
User / application
   ↓
MIDEND HTTP/MCP/API
   ↓
LLM
   ↓
VEYRA backend
   ↓
deterministic evidence
   ↓
AI interpretation
```

works independently.

Also:

- MIDEND can be replaced without rewriting the backend.
- Backend can be used without MIDEND.
- Frontend does not duplicate scientific/backend logic.
- Displayed scientific evidence is traceable to backend results.

---

## 27. Canonical Principle

```text
                USER / APPLICATION
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
        RAW BACKEND            MIDEND
             │                   │
             │              LLM + skill.md
             │                   │
             │             tool planning
             │                   │
             └─────────┬─────────┘
                       ▼
                  VEYRA BACKEND
                       │
                       ▼
             DETERMINISTIC EVIDENCE
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
        Raw results        AI interpretation
```

**The backend is always the computational authority.**

**The MIDEND is an optional AI infrastructure layer on top of it.**

**Users must be able to bypass the MIDEND and call raw VEYRA APIs/MCP directly.**
