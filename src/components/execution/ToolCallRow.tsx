"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, CheckCircle2, Loader2, XCircle, Sliders, FileText } from "lucide-react";
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
  const paramsMeta = (metadata?.parameters_meta ?? {}) as Record<string, {
    value: unknown;
    default: unknown;
    status: "default" | "overridden" | "supplied";
    units?: string;
  }>;
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
            <span className="font-mono text-[11px] text-muted veyra-readout font-medium">
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
        <div className="border-t border-border/40 bg-black/40 p-3 space-y-3.5 text-xs">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono text-muted border-b border-border/30 pb-2.5">
            <div>
              <span className="text-muted/60 block text-[9px] uppercase">Status</span>
              <span className={isFailed ? "text-risk-high font-semibold" : isCompleted ? "text-engine font-semibold" : "text-ai"}>
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

          {/* Exact Parameter Panel (Authoritative Defaults vs Overrides) */}
          <div>
            <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted/80 mb-1.5 font-semibold">
              <Sliders size={12} className="text-primary" />
              <span>Exact Parameters Supplied ({call.tool})</span>
            </div>
            
            {Object.keys(paramsMeta).length > 0 ? (
              <div className="rounded border border-border/40 bg-black/50 overflow-hidden font-mono text-[11px]">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border/30 bg-white/[0.02] text-[10px] text-muted uppercase">
                      <th className="px-2.5 py-1.5 font-semibold">Parameter</th>
                      <th className="px-2.5 py-1.5 font-semibold">Supplied Value</th>
                      <th className="px-2.5 py-1.5 font-semibold">Contract Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/20">
                    {Object.entries(paramsMeta).map(([param, p]) => (
                      <tr key={param} className="hover:bg-white/[0.02]">
                        <td className="px-2.5 py-1 text-muted/90 font-medium">{param}</td>
                        <td className="px-2.5 py-1 text-foreground font-semibold veyra-readout">
                          {typeof p.value === "object" ? JSON.stringify(p.value) : String(p.value)}
                          {p.units && <span className="text-muted text-[10px] ml-1 font-normal">({p.units})</span>}
                        </td>
                        <td className="px-2.5 py-1">
                          {p.status === "overridden" ? (
                            <span className="rounded px-1.5 py-0.2 text-[9px] uppercase bg-ai/15 text-ai border border-ai/40 font-semibold">
                              overridden (default: {String(p.default)})
                            </span>
                          ) : p.status === "default" ? (
                            <span className="rounded px-1.5 py-0.2 text-[9px] uppercase bg-white/5 text-muted border border-border/30">
                              default
                            </span>
                          ) : (
                            <span className="rounded px-1.5 py-0.2 text-[9px] uppercase bg-white/5 text-foreground/80 border border-border/30">
                              supplied
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : call.arguments && Object.keys(call.arguments).length > 0 ? (
              <pre className="max-h-36 overflow-auto rounded border border-border/30 bg-black/60 p-2 font-mono text-[11px] text-foreground/90 whitespace-pre-wrap">
                {JSON.stringify(call.arguments, null, 2)}
              </pre>
            ) : (
              <p className="text-[11px] font-mono text-muted/60 italic">No parameters required</p>
            )}
          </div>

          {/* Structured Output Summary */}
          {summary && Object.keys(summary).length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted/80 mb-1.5 font-semibold">
                <FileText size={12} className="text-secondary" />
                <span>Summary Output</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 p-2 rounded border border-border/40 bg-black/50 font-mono text-[11px]">
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

          {/* Structured Rows / Output Hits */}
          {rows && rows.length > 0 && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted/80 block mb-1 font-semibold">
                Result Rows ({rows.length} {rows.length === 1 ? "record" : "records"})
              </span>
              <pre className="max-h-48 overflow-auto rounded border border-border/30 bg-black/60 p-2 font-mono text-[11px] text-foreground/90 whitespace-pre-wrap custom-scrollbar">
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

          {/* Errors / Diagnostics */}
          {errors.length > 0 && (
            <div className="rounded border border-risk-high/40 bg-risk-high/10 p-2.5 text-risk-high font-mono">
              <span className="text-[10px] uppercase tracking-wider block font-semibold mb-1">
                Execution Error / Diagnostics
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
                Provenance & Audit Metadata
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
