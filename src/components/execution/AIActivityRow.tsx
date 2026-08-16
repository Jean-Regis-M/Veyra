"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Loader2, XCircle, Sparkles } from "lucide-react";
import { AIRequestRecord } from "@/lib/midend";

interface AIActivityRowProps {
  aiRequest?: AIRequestRecord;
  reasoningActive?: boolean;
  generationActive?: boolean;
  provider?: string | null;
  model?: string | null;
  durationMs?: number;
  defaultExpanded?: boolean;
}

function formatDuration(ms?: number): string {
  if (ms === undefined || ms === null) return "";
  if (ms < 1) return "< 1 ms";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function AIActivityRow({
  aiRequest,
  reasoningActive = false,
  generationActive = false,
  provider,
  model,
  durationMs,
  defaultExpanded = false,
}: AIActivityRowProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const isRunning = reasoningActive || generationActive || aiRequest?.status === "running";
  const isFailed = aiRequest?.status === "failed" || (aiRequest?.error && aiRequest.error.length > 0);
  const isCompleted = aiRequest?.status === "completed" || (!isRunning && !isFailed);

  const activeProvider = aiRequest?.provider || provider || "openai_compatible";
  const activeModel = aiRequest?.model || model || "default";
  const usage = aiRequest?.usage;

  const statusLabel = reasoningActive
    ? "AI is reasoning..."
    : generationActive
    ? "Generating response..."
    : isRunning
    ? "AI processing..."
    : isFailed
    ? "AI generation failed"
    : "AI generation complete";

  return (
    <div className="rounded-lg border border-ai/30 bg-ai/5 overflow-hidden transition-all">
      {/* Compact Header Row */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-ai/10 transition-colors gap-2"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          {isRunning ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-ai shrink-0" />
          ) : isFailed ? (
            <XCircle className="h-3.5 w-3.5 text-risk-high shrink-0" />
          ) : (
            <Sparkles className="h-3.5 w-3.5 text-ai shrink-0" />
          )}

          <div className="flex items-center gap-2 truncate">
            <span className="font-mono text-xs text-foreground font-medium truncate">
              {statusLabel}
            </span>
            <span className="hidden sm:inline-block rounded px-1.5 py-0.2 font-mono text-[9px] uppercase tracking-wider text-ai bg-ai/10 border border-ai/30">
              {activeModel}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {(aiRequest?.duration_ms ?? durationMs) !== undefined && (
            <span className="font-mono text-[11px] text-muted veyra-readout">
              {formatDuration(aiRequest?.duration_ms ?? durationMs)}
            </span>
          )}
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted" />
          )}
        </div>
      </button>

      {/* Expanded View */}
      {expanded && (
        <div className="border-t border-ai/20 bg-black/40 p-3 space-y-3 text-xs">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono text-muted">
            <div>
              <span className="text-muted/60 block text-[9px] uppercase">Provider</span>
              <span className="text-foreground">{activeProvider}</span>
            </div>
            <div>
              <span className="text-muted/60 block text-[9px] uppercase">Model</span>
              <span className="text-foreground font-medium">{activeModel}</span>
            </div>
            <div>
              <span className="text-muted/60 block text-[9px] uppercase">Status</span>
              <span className={isFailed ? "text-risk-high" : isCompleted ? "text-ai" : "text-foreground"}>
                {aiRequest?.status ?? (isRunning ? "running" : "completed")}
              </span>
            </div>
            {(aiRequest?.duration_ms ?? durationMs) !== undefined && (
              <div>
                <span className="text-muted/60 block text-[9px] uppercase">Duration</span>
                <span className="text-foreground veyra-readout">
                  {formatDuration(aiRequest?.duration_ms ?? durationMs)}
                </span>
              </div>
            )}
          </div>

          {/* Token Usage Stats if available */}
          {usage && Object.keys(usage).length > 0 && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted/70 block mb-1">
                Token Usage
              </span>
              <div className="flex flex-wrap gap-3 p-2 rounded border border-border/30 bg-black/50 font-mono text-[11px]">
                {Object.entries(usage).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-1.5">
                    <span className="text-muted">{k}:</span>
                    <span className="text-foreground font-semibold veyra-readout">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error if failed */}
          {aiRequest?.error && (
            <div className="rounded border border-risk-high/40 bg-risk-high/10 p-2 text-risk-high font-mono text-[11px]">
              <span className="font-semibold block mb-0.5">Error</span>
              {aiRequest.error}
            </div>
          )}

          <div className="text-[10px] font-mono text-muted/60 italic">
            Privacy Note: Internal reasoning tokens, prompt templates, and credentials are intentionally isolated and never exposed.
          </div>
        </div>
      )}
    </div>
  );
}
