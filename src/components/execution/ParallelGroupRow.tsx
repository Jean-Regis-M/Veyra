"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Loader2, XCircle, Layers } from "lucide-react";
import { ParallelGroupRecord } from "@/lib/midend";
import { ToolCallRow } from "./ToolCallRow";

interface ParallelGroupRowProps {
  group: ParallelGroupRecord;
  defaultExpanded?: boolean;
}

function formatDuration(ms?: number): string {
  if (ms === undefined || ms === null) return "";
  if (ms < 1) return "< 1 ms";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function ParallelGroupRow({ group, defaultExpanded = false }: ParallelGroupRowProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const calls = group.calls || [];
  const anyRunning = calls.some((c) => c.status === "running" || c.status === "queued");
  const anyFailed = calls.some((c) => c.status === "failed" || c.success === false);

  return (
    <div className="rounded-lg border border-border/70 bg-black/40 overflow-hidden transition-all space-y-0">
      {/* Group Header Button */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-white/[0.04] transition-colors gap-2"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          {anyRunning ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-ai shrink-0" />
          ) : anyFailed ? (
            <XCircle className="h-3.5 w-3.5 text-risk-high shrink-0" />
          ) : (
            <Layers className="h-3.5 w-3.5 text-secondary shrink-0" />
          )}

          <div className="flex items-center gap-2 truncate">
            <span className="font-mono text-xs text-foreground font-semibold truncate">
              Parallel tools ({calls.length})
            </span>
            {group.group_id && (
              <span className="hidden sm:inline-block rounded px-1.5 py-0.2 font-mono text-[9px] uppercase tracking-wider text-muted/80 bg-white/5 border border-border/30">
                {group.group_id}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {group.duration_ms !== undefined && (
            <span className="font-mono text-[11px] text-muted veyra-readout font-medium">
              {formatDuration(group.duration_ms)}
            </span>
          )}
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted" />
          )}
        </div>
      </button>

      {/* Visual Compact Tree View (when collapsed or compact) */}
      {!expanded && calls.length > 0 && (
        <div className="px-4 pb-2.5 font-mono text-[11px] text-muted space-y-1 border-t border-border/20 pt-1.5">
          {calls.map((c, idx) => {
            const isLast = idx === calls.length - 1;
            const prefix = isLast ? "└─" : "├─";
            const callFailed = c.status === "failed" || c.success === false;
            return (
              <div key={idx} className="flex items-center justify-between pl-1">
                <span className="truncate flex items-center gap-1.5">
                  <span className="text-muted/50 select-none">{prefix}</span>
                  <span className={callFailed ? "text-risk-high" : "text-foreground/80"}>
                    {c.tool}
                  </span>
                </span>
                <span className="text-muted/70 text-[10px] veyra-readout shrink-0 ml-2">
                  {c.duration_ms !== undefined ? formatDuration(c.duration_ms) : (c.status ?? "running")}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Expanded Deep List of Calls */}
      {expanded && (
        <div className="border-t border-border/40 p-3 space-y-2 bg-black/60">
          <p className="font-mono text-[10px] uppercase tracking-wider text-muted/70 mb-1">
            Group Tools ({calls.length} concurrent calls)
          </p>
          <div className="space-y-2">
            {calls.map((c, idx) => (
              <ToolCallRow key={c.call_id || idx} call={c} defaultExpanded={false} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
