"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  buildSessionHandbook,
  CalibrationDataset,
  checkMidendHealth,
  createConversation,
  ExecutionStatus,
  listSkills,
  listMidendTools,
  pollExecution,
  postConversationMessage,
  runSkill,
  sendChatMessage,
  SkillMetadata,
  uploadCalibrationFile,
} from "@/lib/midend";
import { ExecutionActivity } from "@/components/execution";

interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  executionId?: string;
  executionStatus?: ExecutionStatus;
  evidence?: ExecutionStatus["tool_calls"];
  errors?: string[];
  isRunning?: boolean;
}

export default function MidendConsole() {
  const [online, setOnline] = useState<boolean | null>(null);
  const [skills, setSkills] = useState<SkillMetadata[]>([]);
  const [toolCount, setToolCount] = useState(0);
  const [handbook, setHandbook] = useState<string | null>(null);
  const [showHandbook, setShowHandbook] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [calibUploading, setCalibUploading] = useState(false);
  const [calibError, setCalibError] = useState<string | null>(null);
  const [calibDataset, setCalibDataset] = useState<CalibrationDataset | null>(null);
  const [calibRunning, setCalibRunning] = useState(false);
  const [calibExecutionId, setCalibExecutionId] = useState<string | null>(null);
  const [calibResult, setCalibResult] = useState<ExecutionStatus | null>(null);

  useEffect(() => {
    void checkMidendHealth().then((r) => setOnline(r.ok));
    void listSkills().then((r) => {
      if (r.ok) setSkills(r.data.skills);
    });
    void listMidendTools().then((r) => {
      if (r.ok) setToolCount(r.data.total_tools);
    });
  }, []);

  async function startSession() {
    setStarting(true);
    setStartError(null);
    const conv = await createConversation();
    if (!conv.ok) {
      setStartError(conv.error);
      setStarting(false);
      return;
    }
    const book = buildSessionHandbook(skills, toolCount);
    const posted = await postConversationMessage(conv.data.conversation_id, book, "system");
    if (!posted.ok) {
      setStartError(posted.error);
      setStarting(false);
      return;
    }
    setHandbook(book);
    setConversationId(conv.data.conversation_id);
    setTurns([]);
    setStarting(false);
  }

  async function send() {
    if (!conversationId || !input.trim() || sending) return;
    const message = input.trim();
    setInput("");
    setSending(true);

    const userTurn: ChatTurn = { role: "user", content: message };
    setTurns((t) => [...t, userTurn]);

    const started = await sendChatMessage(message, conversationId);
    if (!started.ok) {
      setTurns((t) => [
        ...t,
        { role: "assistant", content: `(request failed: ${started.error})` },
      ]);
      setSending(false);
      return;
    }

    const execId = started.data.execution_id;
    // Add placeholder assistant turn with live execution tracker
    setTurns((t) => [
      ...t,
      {
        role: "assistant",
        content: "",
        executionId: execId,
        isRunning: true,
      },
    ]);

    const result = await pollExecution(execId);
    if (!result.ok) {
      setTurns((prev) => {
        const next = [...prev];
        const lastIdx = next.length - 1;
        if (lastIdx >= 0 && next[lastIdx].role === "assistant") {
          next[lastIdx] = {
            role: "assistant",
            content: `(${result.error})`,
            executionId: execId,
            isRunning: false,
          };
        }
        return next;
      });
    } else {
      setTurns((prev) => {
        const next = [...prev];
        const lastIdx = next.length - 1;
        if (lastIdx >= 0 && next[lastIdx].role === "assistant") {
          next[lastIdx] = {
            role: "assistant",
            content: result.data.assistant_output ?? "(no output)",
            executionId: execId,
            executionStatus: result.data,
            evidence: result.data.tool_calls,
            errors: result.data.errors,
            isRunning: false,
          };
        }
        return next;
      });
    }
    setSending(false);
  }

  async function handleCalibrationUpload(file: File) {
    setCalibUploading(true);
    setCalibError(null);
    setCalibDataset(null);
    setCalibResult(null);
    setCalibExecutionId(null);
    const result = await uploadCalibrationFile(file);
    setCalibUploading(false);
    if (!result.ok) {
      setCalibError(result.error);
      return;
    }
    setCalibDataset(result.data);
  }

  async function runCalibration() {
    if (!calibDataset || calibRunning) return;
    setCalibRunning(true);
    setCalibResult(null);
    setCalibError(null);

    const started = await runSkill("model_calibration", {
      calibration_input: calibDataset.input_id,
    });
    if (!started.ok) {
      setCalibError(started.error);
      setCalibRunning(false);
      return;
    }

    const execId = started.data.execution_id;
    setCalibExecutionId(execId);

    const result = await pollExecution(execId);
    setCalibRunning(false);
    if (!result.ok) {
      setCalibError(result.error);
      return;
    }
    setCalibResult(result.data);
  }

  return (
    <div className="flex-1 pt-24 pb-20 veyra-hero-bg">
      <header className="fixed top-4 inset-x-0 z-50 px-4 sm:px-6">
        <div className="veyra-glass mx-auto max-w-4xl px-5 h-14 flex items-center justify-between rounded-full!">
          <Link href="/" className="flex items-center gap-2 font-display text-sm font-semibold tracking-wide text-foreground">
            <span className={`h-2 w-2 rounded-full ${online ? "veyra-pulse-dot bg-ai" : "bg-risk-high"}`} />
            VEYRA
          </Link>
          <span className="font-mono text-xs text-muted uppercase tracking-widest">MIDEND session</span>
        </div>
      </header>

      <div className="mx-auto max-w-4xl px-4 sm:px-6">
        <div className="mb-8">
          <h1 className="font-display text-2xl font-semibold text-foreground">MIDEND session</h1>
          <p className="mt-2 text-sm text-muted max-w-2xl">
            AI orchestration over the deterministic backend — {skills.length} live skill
            {skills.length === 1 ? "" : "s"}, {toolCount} live tool{toolCount === 1 ? "" : "s"}. Starting a session
            posts a Session Handbook as the conversation&apos;s first (system) message, so the model is oriented
            before your first message — not rediscovering VEYRA from scratch every turn.
          </p>
          {online === false && <p className="mt-3 text-sm text-risk-high">MIDEND unreachable — start it and reload.</p>}
        </div>

        {!conversationId ? (
          <div className="veyra-glass p-6 space-y-4">
            <p className="text-sm text-muted">Skills registered: {skills.map((s) => s.skill_id).join(", ") || "…"}</p>
            {startError && <p className="text-sm text-risk-high">{startError}</p>}
            <button
              onClick={startSession}
              disabled={starting || online === false}
              className="rounded-full bg-linear-to-r from-ai to-primary px-6 py-3 text-sm font-semibold text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {starting ? "Starting…" : "Start session"}
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="veyra-glass p-4">
              <button
                onClick={() => setShowHandbook((v) => !v)}
                className="font-mono text-[10px] uppercase tracking-widest text-muted hover:text-foreground transition-colors"
              >
                {showHandbook ? "Hide" : "Show"} session handbook (posted as system message)
              </button>
              {showHandbook && (
                <pre className="mt-3 max-h-72 overflow-auto rounded-sm border border-border bg-black/30 p-3 font-mono text-[11px] text-foreground whitespace-pre-wrap">
                  {handbook}
                </pre>
              )}
            </div>

            <div className="veyra-glass p-4 space-y-3">
              <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
                Calibration reference file (optional — the {"model_calibration"} skill)
              </p>
              <p className="text-xs text-muted">
                Upload the original experimental dataset (CSV or TSV) to deterministically fit model
                coefficients against it. Calibration is never required for ordinary analyses.
              </p>
              <label className="inline-flex w-max rounded-full border border-border px-4 py-2.5 text-xs text-muted hover:border-primary/40 hover:text-foreground transition-colors cursor-pointer">
                {calibUploading ? "Validating…" : "Upload reference file (.csv / .tsv)"}
                <input
                  type="file"
                  accept=".csv,.tsv"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    e.target.value = "";
                    if (file) void handleCalibrationUpload(file);
                  }}
                />
              </label>
              {calibError && <p className="text-sm text-risk-high">{calibError}</p>}
              {calibDataset && (
                <div className="veyra-readout rounded-sm border border-engine/30 bg-engine/5 p-3 space-y-2">
                  <span className="rounded-full border border-engine/40 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-engine">
                    Engine — dataset validated
                  </span>
                  <p className="font-mono text-[11px] text-muted">
                    {calibDataset.input_id} — {calibDataset.filename} — {calibDataset.row_count} rows ×{" "}
                    {calibDataset.column_count} cols — status {calibDataset.calibration_status}
                  </p>
                  <p className="font-mono text-[11px] text-muted">columns: {calibDataset.columns.join(", ")}</p>
                  <button
                    onClick={runCalibration}
                    disabled={calibRunning}
                    className="mt-1 rounded-full bg-linear-to-r from-ai to-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-50"
                  >
                    {calibRunning ? "Fitting…" : "Run calibration"}
                  </button>

                  {/* Live Execution Activity Panel for Calibration */}
                  {calibExecutionId && (
                    <div className="pt-2">
                      <ExecutionActivity
                        executionId={calibExecutionId}
                        initialData={calibResult}
                        live={calibRunning}
                        title="Calibration execution activity"
                        defaultCollapsed={false}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="veyra-glass p-5 space-y-4 min-h-[200px]">
              {turns.length === 0 && <p className="text-sm text-muted">Session started. Ask VEYRA something.</p>}
              {turns.map((t, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${
                        t.role === "user" ? "text-muted border-border-strong" : "text-ai border-ai/40"
                      }`}
                    >
                      {t.role === "user" ? "You" : "AI"}
                    </span>
                  </div>

                  {/* Assistant response text or loading status */}
                  {t.content ? (
                    <p className="text-sm text-foreground/90 whitespace-pre-line">{t.content}</p>
                  ) : t.isRunning ? (
                    <p className="text-sm text-ai font-mono animate-pulse">
                      AI is orchestrating tool calls...
                    </p>
                  ) : null}

                  {/* Expandable Live Execution Activity Panel */}
                  {t.executionId && (
                    <ExecutionActivity
                      executionId={t.executionId}
                      initialData={t.executionStatus}
                      live={t.isRunning}
                      defaultCollapsed={!t.isRunning}
                    />
                  )}

                  {t.errors && t.errors.length > 0 && (
                    <p className="text-xs text-risk-high">{t.errors.join("; ")}</p>
                  )}
                </div>
              ))}
            </div>

            <div className="veyra-glass p-3 flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && send()}
                placeholder="Ask about a sequence, a skill, or the pipeline…"
                className="flex-1 rounded-full border border-border bg-black/20 px-4 py-2 text-sm text-foreground focus:outline-none focus:border-primary/60"
              />
              <button
                onClick={send}
                disabled={sending || !input.trim()}
                className="rounded-full bg-linear-to-r from-ai to-primary px-5 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {sending ? "…" : "Send"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

