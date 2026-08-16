# VEYRA — Actual System Architecture

This supersedes `docs/architecture.md`, which describes only the earlier client-only version of VEYRA. Full detail and evidence: `docs/PROJECT_HANDOFF.md`.

## System overview

```mermaid
flowchart TB
    subgraph Frontend["Frontend — Next.js 16 / React 19 (port 3000)"]
        Landing["/  Landing page"]
        Analyze["/analyze  Sequence paste + file upload"]
        Chat["/chat (alias /midend)  AI conversational analysis"]
        Raw["/raw  Direct backend console"]
        Docs["/docs  Static user guide"]
        GenomicEngine["src/lib/genomic-engine\nclient-side HEURISTIC engine"]
        Helix["HelixModel.tsx\nReact Three Fiber 3D DNA"]
        ApiIngest["/api/ingest\nfile-upload bridge route"]
        ApiReason["/api/reason\nsimple one-shot AI explain"]
    end

    subgraph Midend["MIDEND — FastAPI/Python (port 8080)"]
        ControlPlane["control_plane.py\nconversations, executions, PromptBuilder"]
        Skills["3 skills:\nspcas9_gene_cutting\nofftarget_toxicity_risk\nmodel_calibration"]
        Connector["connectors/\nHTTP or MCP to backend"]
        AIProvider["ai/openai_compatible.py"]
    end

    subgraph Backend["Backend — FastAPI/Python (port 8000)"]
        HttpApi["http_api/app.py — 27 routes"]
        Core["core/*.py — request adapters"]
        Tools["mcp/tools/*.py — 18 REAL algorithms\nPAM, CFD, Doench 2014/RS2/RS3, Tm, GC, ..."]
        Parsers["parsers/ — FASTA/FASTQ/GenBank\n(Biopython)"]
        References["references/ — real CRISPOR\nCFD pickle resources"]
    end

    LLM[("External LLM provider\nOpenAI-compatible\nMIDEND_AI_* env vars")]

    Analyze -->|paste| GenomicEngine
    Analyze -->|upload| ApiIngest --> HttpApi
    Analyze -->|"when backend online"| HttpApi
    Analyze --> ApiReason --> LLM
    Analyze --> Helix
    Landing --> Helix

    Chat -->|"start session, send message,\nattach file"| ControlPlane
    ControlPlane --> Skills --> Connector --> HttpApi
    ControlPlane --> AIProvider --> LLM
    Chat -->|poll GET /executions/id| ControlPlane

    Raw -->|"1:1 passthrough"| HttpApi

    HttpApi --> Core --> Tools
    Tools --> Parsers
    Tools --> References
```

## Layer responsibilities (enforced structurally, not just by convention)

| Layer | Owns | Never does |
|---|---|---|
| Backend | Every deterministic number (PAM, GC, Tm, CFD, on-target models) | Talk to an LLM, know about conversations |
| MIDEND | Conversation/session state, tool orchestration, prompt construction | Compute any biology itself — confirmed by search, zero scoring math in `veyra/midend/` |
| Frontend | UI, session initiation, a fast client-only heuristic fallback | Persist data server-side (no database anywhere) |

## Data flow — `/analyze` (paste/upload path)

```mermaid
flowchart LR
    A[User pastes or uploads sequence] --> B{Backend online?}
    B -->|"always, instantly"| C["src/lib/genomic-engine\nHEURISTIC: PAM scan, GC,\ncustom off-target penalty"]
    B -->|yes| D["Backend: real on-target\n(Doench models) + CFD\noff-target + Tm + homopolymer"]
    C --> E[Ranked candidate list]
    D --> E
    E --> F["/api/reason\nAI explains the numbers\n(never invents new ones)"]
    E --> G["HelixModel.tsx\nGC% -> HSL tint"]
    F --> H[UI: Engine numbers + AI text, tagged separately]
    G --> H
```

## Data flow — `/chat` (primary AI-orchestrated path)

```mermaid
sequenceDiagram
    participant U as User (browser)
    participant F as ChatConsole.tsx
    participant M as MIDEND control_plane.py
    participant B as Backend http_api

    U->>F: Start session
    F->>M: POST /conversations
    M-->>F: conversation_id

    U->>F: Attach FASTA file (optional)
    F->>M: POST /inputs/file (multipart)
    M-->>F: input_id (validated, typed)

    U->>F: "Find candidate SpCas9 cutting sites..."
    F->>M: POST /ai/chat {message, conversation_id}
    M-->>F: execution_id (status: started)

    M->>M: PromptBuilder assembles system+history+message
    M->>B: real tool calls (pam_scan, compute_gc_content, compute_cut_site, ...)
    B-->>M: real ToolResult JSON per call
    M->>M: inject tool evidence into prompt
    M->>LLM: chat completion request
    LLM-->>M: interpreted response text

    loop poll every ~900ms
        F->>M: GET /executions/execution_id
        M-->>F: status: queued|running|completed
    end
    M-->>F: assistant_output + tool_calls + deterministic_evidence
    F->>U: renders AI text + Engine evidence, tagged separately
```

## Deployment topology (current — hackathon/local only)

```mermaid
flowchart LR
    Browser -->|localhost:3000| NextDev[Next.js dev server]
    NextDev -->|localhost:8000| BackendProc[uvicorn — backend, run from veyra/backend/]
    NextDev -->|localhost:8080| MidendProc[uvicorn — midend, run from veyra/]
    MidendProc -->|localhost:8000| BackendProc
    MidendProc -->|HTTPS| ExternalLLM[External OpenAI-compatible provider]
```

No reverse proxy, no container orchestration, no process supervisor. All three processes must be started manually and have repeatedly dropped between work sessions (an operational, not code, issue).
