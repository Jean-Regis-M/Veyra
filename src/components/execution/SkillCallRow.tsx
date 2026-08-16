"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, CheckCircle2, Loader2, XCircle, Sparkles } from "lucide-react";

interface SkillCallRowProps {
  skillId: string;
  result?: Record<string, unknown> | null;
  status?: string;
  durationMs?: number;
  defaultExpanded?: boolean;
}

function formatDuration(ms?: number): string {
  if (ms === undefined || ms === null) return "";
  if (ms < 1) return "< 1 ms";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function SkillCallRow({
  skillId,
  result,
  status: inputStatus,
  durationMs,
  defaultExpanded = false,
}: SkillCallRowProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const rawStatus = (result?.status as string) || inputStatus || "running";
  const isRunning = rawStatus === "running" || rawStatus === "queued";
  const isFailed = rawStatus === "failed";
  const isComplete = rawStatus === "complete" || rawStatus === "completed";
  const isPartial = rawStatus === "partial" || rawStatus === "prototype" || rawStatus === "unavailable";

  const candidates = (result?.candidates ?? []) as Record<string, unknown>[];
  const warnings = (result?.warnings ?? []) as string[];
  const errors = (result?.errors ?? []) as string[];
  const calibration = result?.calibration as Record<string, unknown> | undefined;
  const metrics = result?.metrics as Record<string, unknown> | undefined;
  const aiReview = result?.ai_review_summary as Record<string, unknown> | undefined;

  return (
    <div className="rounded-lg border border-ai/40 bg-ai/5 overflow-hidden transition-all">
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
          ) : isPartial ? (
            <Sparkles className="h-3.5 w-3.5 text-ai shrink-0" />
          ) : (
            <CheckCircle2 className="h-3.5 w-3.5 text-engine shrink-0" />
          )}

          <div className="flex items-center gap-2 truncate">
            <span className="font-mono text-xs text-foreground font-semibold truncate">
              {isRunning
                ? `Running skill: ${skillId}`
                : isFailed
                ? `Skill failed: ${skillId}`
                : `Skill called: ${skillId}`}
            </span>
            <span
              className={`rounded px-1.5 py-0.2 font-mono text-[9px] uppercase tracking-wider border ${
                isFailed
                  ? "border-risk-high/40 text-risk-high bg-risk-high/10"
                  : isComplete
                  ? "border-engine/40 text-engine bg-engine/10"
                  : "border-ai/40 text-ai bg-ai/10"
              }`}
            >
              {rawStatus}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {durationMs !== undefined && (
            <span className="font-mono text-[11px] text-muted veyra-readout">
              {formatDuration(durationMs)}
            </span>
          )}
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted" />
          )}
        </div>
      </button>

      {/* Expanded Structured Skill View */}
      {expanded && (
        <div className="border-t border-ai/20 bg-black/40 p-3 space-y-3 text-xs">
          {/* Skill Info Header */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono text-muted">
            <div>
              <span className="text-muted/60 block text-[9px] uppercase">Skill ID</span>
              <span className="text-foreground font-medium">{skillId}</span>
            </div>
            <div>
              <span className="text-muted/60 block text-[9px] uppercase">Status</span>
              <span className={isFailed ? "text-risk-high" : isComplete ? "text-engine" : "text-ai"}>
                {rawStatus}
              </span>
            </div>
            {result?.validated !== undefined && (
              <div>
                <span className="text-muted/60 block text-[9px] uppercase">Validated</span>
                <span className={result.validated ? "text-engine font-bold" : "text-muted"}>
                  {result.validated ? "Yes (calibrated)" : "No (prototype)"}
                </span>
              </div>
            )}
            {candidates.length > 0 && (
              <div>
                <span className="text-muted/60 block text-[9px] uppercase">Candidates</span>
                <span className="text-foreground font-medium veyra-readout">{candidates.length}</span>
              </div>
            )}
            {durationMs !== undefined && (
              <div>
                <span className="text-muted/60 block text-[9px] uppercase">Duration</span>
                <span className="text-foreground veyra-readout">{formatDuration(durationMs)}</span>
              </div>
            )}
          </div>

          {/* Candidates Summary for Gene Cutting */}
          {candidates.length > 0 && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted/70 block mb-1">
                Discovered Candidates ({candidates.length})
              </span>
              <div className="space-y-1.5 max-h-48 overflow-auto rounded border border-border/30 bg-black/50 p-2">
                {candidates.slice(0, 10).map((cand, idx) => (
                  <div key={idx} className="flex items-center justify-between text-[11px] font-mono border-b border-border/20 pb-1 last:border-b-0">
                    <span className="text-foreground truncate">
                      {String(cand.cutting_site_string || cand.protospacer)}
                    </span>
                    {cand.rank !== undefined && cand.rank !== null && (
                      <span className="text-ai font-semibold shrink-0 ml-2">
                        Rank #{String(cand.rank)}
                      </span>
                    )}
                  </div>
                ))}
                {candidates.length > 10 && (
                  <p className="text-[10px] text-muted italic">
                    + {candidates.length - 10} more candidates in full payload
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Model Calibration Summary */}
          {metrics && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted/70 block mb-1">
                Calibration Metrics
              </span>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-2 rounded border border-border/30 bg-black/50 font-mono text-[11px]">
                {Object.entries(metrics).map(([k, v]) => (
                  <div key={k}>
                    <span className="text-muted/60 block text-[9px] uppercase">{k}</span>
                    <span className="text-foreground font-medium veyra-readout">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Calibration Metadata */}
          {calibration && (
            <div className="rounded border border-border/30 bg-black/40 p-2 text-[11px] font-mono">
              <span className="text-muted/60 block text-[9px] uppercase mb-1">Calibration Status</span>
              <p className="text-foreground">
                Status: <span className="text-ai font-semibold">{String(calibration.status)}</span>
                {calibration.model_id ? ` | Model: ${String(calibration.model_id)}` : ""}
              </p>
            </div>
          )}

          {/* AI Review Summary */}
          {aiReview && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted/70 block mb-1">
                AI Interpretation Evidence
              </span>
              <pre className="max-h-32 overflow-auto rounded border border-border/30 bg-black/60 p-2 font-mono text-[11px] text-foreground/90 whitespace-pre-wrap">
                {JSON.stringify(aiReview, null, 2)}
              </pre>
            </div>
          )}

          {/* Warnings */}
          {warnings.length > 0 && (
            <div className="rounded border border-risk-moderate/30 bg-risk-moderate/10 p-2 text-risk-moderate">
              <span className="font-mono text-[10px] uppercase tracking-wider block font-semibold mb-0.5">
                Warnings
              </span>
              <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                {warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Errors */}
          {errors.length > 0 && (
            <div className="rounded border border-risk-high/40 bg-risk-high/10 p-2 text-risk-high">
              <span className="font-mono text-[10px] uppercase tracking-wider block font-semibold mb-0.5">
                Errors
              </span>
              <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                {errors.map((err, idx) => (
                  <li key={idx}>{err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
