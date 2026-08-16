"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { ToolCallRecord } from "@/lib/midend";

interface ToolCallRowProps {
  call: ToolCallRecord;
  defaultExpanded?: boolean;
}

function formatDuration(ms?: number): string {
  if (ms === undefined || ms === null) return "";
  if (ms < 1) return "< 1 ms";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function ToolCallRow({ call, defaultExpanded = false }: ToolCallRowProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const isRunning = call.status === "running" || call.status === "queued";
  const isFailed = call.status === "failed" || call.success === false || (call.errors && call.errors.length > 0);
  const isCompleted = call.status === "completed" || (call.success === true && !isFailed);

  const resultObj = call.result as Record<string, unknown> | undefined;
  const summary = (resultObj?.summary ?? {}) as Record<string, unknown>;
  const rows = (resultObj?.rows ?? []) as unknown[];
  const metadata = (resultObj?.metadata ?? call.metadata ?? {}) as Record<string, unknown>;
  const warnings = (call.warnings ?? resultObj?.warnings ?? []) as string[];
  const errors = (call.errors ?? resultObj?.errors ?? []) as string[];

  return (
    <div className="rounded-lg border border-border/50 bg-black/30 overflow-hidden transition-all">
      {/* Compact Header Row */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-white/[0.03] transition-colors gap-2"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          {isRunning ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-ai shrink-0" />
          ) : isFailed ? (
            <XCircle className="h-3.5 w-3.5 text-risk-high shrink-0" />
          ) : (
            <CheckCircle2 className="h-3.5 w-3.5 text-engine shrink-0" />
          )}

          <div className="flex items-center gap-2 truncate">
            <span className="font-mono text-xs text-foreground/90 font-medium truncate">
              {isRunning
                ? `Calling: ${call.tool}`
                : isFailed
                ? `Tool failed: ${call.tool}`
                : `Tool called: ${call.tool}`}
            </span>
            {call.connector && (
              <span className="hidden sm:inline-block rounded px-1.5 py-0.2 font-mono text-[9px] uppercase tracking-wider bg-white/5 text-muted border border-border/40">
                {call.connector}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {call.duration_ms !== undefined && (
            <span className="font-mono text-[11px] text-muted veyra-readout">
              {formatDuration(call.duration_ms)}
            </span>
          )}
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted" />
          )}
        </div>
      </button>

      {/* Expanded Structured View */}
      {expanded && (
        <div className="border-t border-border/40 bg-black/40 p-3 space-y-3 text-xs">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono text-muted">
            <div>
              <span className="text-muted/60 block text-[9px] uppercase">Status</span>
              <span className={isFailed ? "text-risk-high" : isCompleted ? "text-engine" : "text-ai"}>
                {call.status ?? (call.success ? "completed" : "failed")}
              </span>
            </div>
            <div>
              <span className="text-muted/60 block text-[9px] uppercase">Connector</span>
              <span className="text-foreground/90">{call.connector ?? "http"}</span>
            </div>
            {call.duration_ms !== undefined && (
              <div>
                <span className="text-muted/60 block text-[9px] uppercase">Duration</span>
                <span className="text-foreground/90 veyra-readout">{formatDuration(call.duration_ms)}</span>
              </div>
            )}
            {call.call_id && (
              <div>
                <span className="text-muted/60 block text-[9px] uppercase">Call ID</span>
                <span className="text-foreground/80 truncate block">{call.call_id}</span>
              </div>
            )}
          </div>

          {/* Arguments */}
          {call.arguments && Object.keys(call.arguments).length > 0 && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted/70 block mb-1">
                Arguments
              </span>
              <pre className="max-h-40 overflow-auto rounded border border-border/30 bg-black/60 p-2 font-mono text-[11px] text-foreground/90 whitespace-pre-wrap">
                {JSON.stringify(call.arguments, null, 2)}
              </pre>
            </div>
          )}

          {/* Structured Summary */}
          {summary && Object.keys(summary).length > 0 && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted/70 block mb-1">
                Summary Output
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 p-2 rounded border border-border/30 bg-black/50 font-mono text-[11px]">
                {Object.entries(summary).map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between gap-2 border-b border-border/20 py-0.5 last:border-b-0">
                    <span className="text-muted truncate">{key}:</span>
                    <span className="text-foreground font-medium truncate veyra-readout">
                      {typeof val === "object" ? JSON.stringify(val) : String(val)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Structured Rows / Hits */}
          {rows && rows.length > 0 && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted/70 block mb-1">
                Results ({rows.length} {rows.length === 1 ? "row" : "rows"})
              </span>
              <pre className="max-h-48 overflow-auto rounded border border-border/30 bg-black/60 p-2 font-mono text-[11px] text-foreground/90 whitespace-pre-wrap">
                {JSON.stringify(rows, null, 2)}
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

          {/* Provenance & Metadata */}
          {metadata && Object.keys(metadata).length > 0 && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted/50 block mb-1">
                Provenance & Metadata
              </span>
              <pre className="max-h-24 overflow-auto rounded border border-border/20 bg-black/40 p-1.5 font-mono text-[10px] text-muted/80 whitespace-pre-wrap">
                {JSON.stringify(metadata, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
