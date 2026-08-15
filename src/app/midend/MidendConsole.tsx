"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  buildSessionHandbook,
  checkMidendHealth,
  createConversation,
  ExecutionStatus,
  listSkills,
  listMidendTools,
  pollExecution,
  postConversationMessage,
  sendChatMessage,
  SkillMetadata,
} from "@/lib/midend";

interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  evidence?: ExecutionStatus["tool_calls"];
  errors?: string[];
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
    setTurns((t) => [...t, { role: "user", content: message }]);
    setSending(true);
    const started = await sendChatMessage(message, conversationId);
    if (!started.ok) {
      setTurns((t) => [...t, { role: "assistant", content: `(request failed: ${started.error})` }]);
      setSending(false);
      return;
    }
    const result = await pollExecution(started.data.execution_id);
    if (!result.ok) {
      setTurns((t) => [...t, { role: "assistant", content: `(${result.error})` }]);
    } else {
      setTurns((t) => [
        ...t,
        {
          role: "assistant",
          content: result.data.assistant_output ?? "(no output)",
          evidence: result.data.tool_calls,
          errors: result.data.errors,
        },
      ]);
    }
    setSending(false);
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
                  <p className="text-sm text-foreground/90 whitespace-pre-line">{t.content}</p>
                  {t.evidence && t.evidence.length > 0 && (
                    <div className="veyra-readout rounded-sm border border-engine/30 bg-engine/5 p-3 space-y-1">
                      <span className="rounded-full border border-engine/40 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-engine">
                        Engine — tool calls
                      </span>
                      {t.evidence.map((tc, j) => (
                        <p key={j} className="font-mono text-[11px] text-muted">
                          {tc.tool} — {tc.success ? "ok" : "failed"}
                        </p>
                      ))}
                    </div>
                  )}
                  {t.errors && t.errors.length > 0 && <p className="text-xs text-risk-high">{t.errors.join("; ")}</p>}
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
