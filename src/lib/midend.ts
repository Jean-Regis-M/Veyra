/**
 * Client for VEYRA's MIDEND service (veyra/midend, FastAPI on :8080) — the
 * AI-orchestration layer that sits between the frontend and the raw backend
 * (src/lib/backend.ts). Contract verified against veyra/midend/integration.md.
 * MIDEND never performs biological calculations itself; it calls backend
 * tools/skills and interprets their real results. This client never invents
 * a tool name, schema, or score — every function either returns MIDEND's
 * real response or a typed failure.
 */

const MIDEND_URL = process.env.NEXT_PUBLIC_VEYRA_MIDEND_URL ?? "http://localhost:8080";

export type MidendResult<T> = { ok: true; data: T } | { ok: false; error: string };

async function withTimeout<T>(fn: (signal: AbortSignal) => Promise<T>, ms: number): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fn(controller.signal);
  } finally {
    clearTimeout(timer);
  }
}

async function call<T>(
  method: "GET" | "POST" | "DELETE",
  path: string,
  body?: Record<string, unknown>,
  timeoutMs = 10000
): Promise<MidendResult<T>> {
  try {
    const res = await withTimeout(
      (signal) =>
        fetch(`${MIDEND_URL}${path}`, {
          method,
          headers: body ? { "content-type": "application/json" } : undefined,
          body: body ? JSON.stringify(body) : undefined,
          signal,
        }),
      timeoutMs
    );
    const json = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = json?.detail?.code ?? json?.error ?? json?.detail ?? `HTTP ${res.status}`;
      return { ok: false, error: String(detail) };
    }
    return { ok: true, data: json as T };
  } catch (e) {
    const message = e instanceof Error && e.name === "AbortError" ? "MIDEND timed out" : "MIDEND unreachable";
    return { ok: false, error: message };
  }
}

export interface MidendHealth {
  status: string;
  service: string;
  connector: string;
  ai_configured: boolean;
  provider_status: string;
}

export async function checkMidendHealth(): Promise<MidendResult<MidendHealth>> {
  return call<MidendHealth>("GET", "/health");
}

export interface SkillMetadata {
  skill_id: string;
  name: string;
  description: string;
  version: string;
  required_inputs: { name: string; type: string; required?: boolean }[];
  allowed_tools: string[];
  workflow: string[];
  validation_rules: string[];
}

export async function listSkills(): Promise<MidendResult<{ skills: SkillMetadata[] }>> {
  return call("GET", "/skills");
}

export interface MidendTool {
  name: string;
  description: string;
  tier: string;
  cost: string;
}

export async function listMidendTools(): Promise<MidendResult<{ total_tools: number; tools: MidendTool[] }>> {
  return call("GET", "/tools");
}

export interface Conversation {
  conversation_id: string;
  created_at: string;
  messages: { role: string; content: string }[];
  execution_ids: string[];
}

export async function createConversation(): Promise<MidendResult<Conversation>> {
  return call("POST", "/conversations");
}

export async function postConversationMessage(
  conversationId: string,
  content: string,
  role: "system" | "user" | "assistant" = "user"
): Promise<MidendResult<Conversation>> {
  return call("POST", `/conversations/${conversationId}/messages`, { content, role });
}

export interface ChatStarted {
  execution_id: string;
  conversation_id: string;
  status: string;
}

export async function sendChatMessage(
  message: string,
  conversationId: string
): Promise<MidendResult<ChatStarted>> {
  return call("POST", "/ai/chat", { message, conversation_id: conversationId });
}

export interface CalibrationDataset {
  input_id: string;
  filename: string;
  format: string;
  input_class: string;
  size_bytes: number;
  row_count: number;
  column_count: number;
  columns: string[];
  sample_count: number;
  calibration_status: string;
  validation_status: string;
}

/** Uploads a CSV/TSV calibration reference file straight to MIDEND's real
 * /calibration/file endpoint (multipart, no bridge route needed — unlike
 * the backend's /ingest, MIDEND accepts uploads directly). Returns the
 * validated dataset's real input_id (calib_...), never a fabricated one. */
export async function uploadCalibrationFile(file: File): Promise<MidendResult<CalibrationDataset>> {
  try {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${MIDEND_URL}/calibration/file`, { method: "POST", body: form });
    const json = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = json?.message ?? json?.error ?? `HTTP ${res.status}`;
      return { ok: false, error: String(detail) };
    }
    return { ok: true, data: json as CalibrationDataset };
  } catch {
    return { ok: false, error: "MIDEND unreachable" };
  }
}

export interface SkillStarted {
  execution_id: string;
  skill: string;
  status: string;
}

export async function runSkill(
  skillId: string,
  payload: Record<string, unknown>
): Promise<MidendResult<SkillStarted>> {
  return call("POST", `/skills/${skillId}`, payload);
}

export interface ExecutionStatus {
  execution_id: string;
  status: "queued" | "running" | "completed" | "failed";
  assistant_output: string | null;
  deterministic_evidence: unknown;
  tool_calls: { tool: string; success: boolean; result: unknown }[];
  errors: string[];
  warnings: string[];
  reasoning_active: boolean;
  generation_active: boolean;
}

export async function getExecution(executionId: string): Promise<MidendResult<ExecutionStatus>> {
  return call("GET", `/executions/${executionId}`);
}

/** Polls an execution until it leaves queued/running, or the attempt cap is hit. */
export async function pollExecution(
  executionId: string,
  { intervalMs = 900, maxAttempts = 60 }: { intervalMs?: number; maxAttempts?: number } = {}
): Promise<MidendResult<ExecutionStatus>> {
  for (let i = 0; i < maxAttempts; i++) {
    const result = await getExecution(executionId);
    if (!result.ok) return result;
    if (result.data.status === "completed" || result.data.status === "failed") return result;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return { ok: false, error: "Execution still running after the poll budget — check /executions/" + executionId };
}

/** The "Session Handbook" — orients a fresh MIDEND conversation with VEYRA's
 * identity, the real live skills/tool count, and the operating rules from
 * integration.md, so the model doesn't have to rediscover them each session.
 * Built entirely from live data (skills) plus the real published contract
 * rules — nothing here is invented. */
export function buildSessionHandbook(skills: SkillMetadata[], toolCount: number): string {
  const lines: string[] = [
    "# VEYRA MIDEND Session Handbook",
    "",
    "## Identity",
    "You are the VEYRA MIDEND assistant — an AI orchestration layer over a deterministic",
    "genomic/CRISPR analysis backend. You never perform biological calculations yourself;",
    "you call VEYRA backend tools and skills and interpret their real, returned results.",
    "",
    "## Available skills",
  ];
  for (const s of skills) {
    lines.push(`- **${s.skill_id}** (v${s.version}) — ${s.description}`);
    lines.push(`  Allowed tools: ${s.allowed_tools.join(", ")}`);
  }
  lines.push(
    "",
    "## MIDEND operating rules",
    `- ${toolCount} live backend tools are registered right now. Get the exact list from GET /tools —`,
    "  never invent a tool name, argument, or schema.",
    "- Prefer an existing skill over ad-hoc tool chaining when one matches the task.",
    "- Skills delegate every biological calculation to the live backend; they never",
    "  reimplement GC/CFD/Tm/on-target math themselves.",
    "",
    "## Tool-use policy",
    "- Every deterministic number must come from an actual tool-call result, never invented.",
    "- Missing or unavailable evidence stays null — never substituted with zero or a guess.",
    "- Do not use filesystem paths as tool arguments; use validated input IDs only.",
    "",
    "## Evidence rules",
    "- Always distinguish deterministic backend evidence from your own interpretation.",
    "- A skill result is a computational prediction only — never present it as",
    "  experimentally confirmed cleavage or a clinical/diagnostic fact.",
    "- calibration_input is always optional; normal workflows never require it.",
    "",
    "## Output rules",
    "- Never render hidden chain-of-thought, reasoning tokens, or provider internals.",
    "- State uncertainty explicitly whenever evidence is partial or unavailable.",
    "- This is a research prototype — never imply regulatory or clinical validity."
  );
  return lines.join("\n");
}
