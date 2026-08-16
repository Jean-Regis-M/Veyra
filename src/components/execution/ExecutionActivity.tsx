"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { ChevronDown, ChevronRight, Activity, Loader2, XCircle } from "lucide-react";
import {
  ExecutionStatus,
  ExecutionStreamEvent,
  getExecution,
  ParallelGroupRecord,
  subscribeExecutionEvents,
  ToolCallRecord,
} from "@/lib/midend";
import { ToolCallRow } from "./ToolCallRow";
import { SkillCallRow } from "./SkillCallRow";
import { ParallelGroupRow } from "./ParallelGroupRow";
import { AIActivityRow } from "./AIActivityRow";

interface ExecutionActivityProps {
  executionId?: string;
  initialData?: ExecutionStatus | null;
  live?: boolean;
  title?: string;
  defaultCollapsed?: boolean;
  onFinished?: (status: ExecutionStatus) => void;
}

export function ExecutionActivity({
  executionId,
  initialData,
  live = true,
  title = "Execution details",
  defaultCollapsed = true,
  onFinished,
}: ExecutionActivityProps) {
  const [panelOpen, setPanelOpen] = useState(!defaultCollapsed);
  const [execState, setExecState] = useState<ExecutionStatus | null>(initialData ?? null);

  // Live state tracking for events
  const [toolCalls, setToolCalls] = useState<ToolCallRecord[]>(initialData?.tool_calls ?? []);
  const [parallelGroups, setParallelGroups] = useState<ParallelGroupRecord[]>(initialData?.parallel_groups ?? []);
  const [skillResult, setSkillResult] = useState<Record<string, unknown> | null>(
    initialData?.skill_result ?? null
  );
  const [activeSkillId, setActiveSkillId] = useState<string | null>(null);
  const [skillStatus, setSkillStatus] = useState<string | null>(null);
  const [reasoningActive, setReasoningActive] = useState<boolean>(initialData?.reasoning_active ?? false);
  const [generationActive, setGenerationActive] = useState<boolean>(initialData?.generation_active ?? false);
  const [aiDurationMs, setAiDurationMs] = useState<number | undefined>(undefined);
  const [isFinished, setIsFinished] = useState<boolean>(
    initialData?.status === "completed" || initialData?.status === "failed"
  );

  // Handle incoming live stream events
  const handleStreamEvent = useCallback(
    (event: ExecutionStreamEvent) => {
      switch (event.event) {
        case "tool_call_started": {
          const callData = event.call as ToolCallRecord | undefined;
          if (callData) {
            setToolCalls((prev) => {
              const existingIdx = prev.findIndex((c) => c.call_id === callData.call_id);
              if (existingIdx >= 0) {
                const next = [...prev];
                next[existingIdx] = { ...next[existingIdx], ...callData, status: "running" };
                return next;
              }
              return [...prev, { ...callData, status: "running" }];
            });
          }
          break;
        }

        case "tool_call_completed":
        case "tool_call_failed": {
          const callData = event.call as ToolCallRecord | undefined;
          if (callData) {
            setToolCalls((prev) => {
              const existingIdx = prev.findIndex((c) => c.call_id === callData.call_id);
              if (existingIdx >= 0) {
                const next = [...prev];
                next[existingIdx] = {
                  ...next[existingIdx],
                  ...callData,
                  status: event.event === "tool_call_completed" ? "completed" : "failed",
                };
                return next;
              }
              return [
                ...prev,
                { ...callData, status: event.event === "tool_call_completed" ? "completed" : "failed" },
              ];
            });
          }
          break;
        }

        case "parallel_group_started": {
          const groupId = event.group_id as string;
          const callIds = (event.calls as string[]) || [];
          setParallelGroups((prev) => {
            if (prev.some((g) => g.group_id === groupId)) return prev;
            return [
              ...prev,
              {
                group_id: groupId,
                calls: callIds.map((id) => ({ call_id: id, tool: id, status: "running" })),
              },
            ];
          });
          break;
        }

        case "parallel_group_completed": {
          const groupId = event.group_id as string;
          const callsData = (event.calls as ToolCallRecord[]) || [];
          const duration = event.duration_ms as number | undefined;
          setParallelGroups((prev) => {
            const idx = prev.findIndex((g) => g.group_id === groupId);
            const updatedGroup = { group_id: groupId, duration_ms: duration, calls: callsData };
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = updatedGroup;
              return next;
            }
            return [...prev, updatedGroup];
          });
          break;
        }

        case "skill_started": {
          setActiveSkillId((event.skill as string) || null);
          setSkillStatus("running");
          break;
        }

        case "skill_completed": {
          setActiveSkillId((event.skill as string) || null);
          setSkillStatus((event.status as string) || "complete");
          break;
        }

        case "skill_failed": {
          setActiveSkillId((event.skill as string) || null);
          setSkillStatus("failed");
          break;
        }

        case "ai_generation_started": {
          setReasoningActive(Boolean(event.reasoning_active));
          setGenerationActive(Boolean(event.generation_active));
          break;
        }

        case "ai_generation_completed":
        case "ai_generation_failed": {
          setReasoningActive(false);
          setGenerationActive(false);
          const req = event.request as { duration_ms?: number } | undefined;
          if (req?.duration_ms) {
            setAiDurationMs(req.duration_ms);
          }
          break;
        }

        case "execution_completed":
        case "execution_failed":
        case "execution_finished": {
          setIsFinished(true);
          break;
        }
      }
    },
    []
  );

  // Subscribe to SSE stream if live and executionId exists
  useEffect(() => {
    if (!live || !executionId || isFinished) return;

    const unsubscribe = subscribeExecutionEvents(
      executionId,
      handleStreamEvent,
      () => {
        setIsFinished(true);
        // Refresh full execution snapshot
        void getExecution(executionId).then((r) => {
          if (r.ok) {
            setExecState(r.data);
            setToolCalls(r.data.tool_calls ?? []);
            setParallelGroups(r.data.parallel_groups ?? []);
            setSkillResult(r.data.skill_result ?? null);
            setReasoningActive(r.data.reasoning_active ?? false);
            setGenerationActive(r.data.generation_active ?? false);
            onFinished?.(r.data);
          }
        });
      }
    );

    return () => {
      unsubscribe();
    };
  }, [live, executionId, isFinished, handleStreamEvent, onFinished]);

  // Group tool calls that belong to parallel groups
  const parallelCallIds = useMemo(() => {
    const ids = new Set<string>();
    for (const group of parallelGroups) {
      for (const call of group.calls || []) {
        if (call.call_id) ids.add(call.call_id);
      }
    }
    return ids;
  }, [parallelGroups]);

  // Standalone tool calls not in a parallel group
  const standaloneCalls = useMemo(() => {
    const calls = toolCalls.length > 0 ? toolCalls : execState?.tool_calls ?? initialData?.tool_calls ?? [];
    return calls.filter((c) => !c.call_id || !parallelCallIds.has(c.call_id));
  }, [toolCalls, execState, initialData, parallelCallIds]);

  const activeParallelGroups = parallelGroups.length > 0 ? parallelGroups : execState?.parallel_groups ?? initialData?.parallel_groups ?? [];
  const activeSkill = activeSkillId || skillResult || execState?.skill_result || initialData?.skill_result;

  const totalActivityCount =
    (activeSkill ? 1 : 0) +
    activeParallelGroups.length +
    standaloneCalls.length +
    (reasoningActive || generationActive || aiDurationMs || execState?.ai_requests?.length ? 1 : 0);

  if (totalActivityCount === 0 && !executionId) {
    return null;
  }

  const isRunning =
    !isFinished &&
    (reasoningActive ||
      generationActive ||
      skillStatus === "running" ||
      standaloneCalls.some((c) => c.status === "running") ||
      execState?.status === "running");

  return (
    <div className="w-full my-2 space-y-1.5">
      {/* Toggle Button / Header Bar */}
      <button
        type="button"
        onClick={() => setPanelOpen((v) => !v)}
        className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-black/40 px-3 py-1 text-xs font-mono text-muted hover:text-foreground hover:border-primary/40 transition-colors"
        aria-expanded={panelOpen}
      >
        {isRunning ? (
          <Loader2 className="h-3 w-3 animate-spin text-ai" />
        ) : execState?.status === "failed" ? (
          <XCircle className="h-3 w-3 text-risk-high" />
        ) : (
          <Activity className="h-3 w-3 text-engine" />
        )}

        <span>
          {title} ({totalActivityCount})
        </span>

        {execState?.elapsed_ms !== undefined && (
          <span className="text-[10px] text-muted/70 veyra-readout font-mono">
            {(execState.elapsed_ms / 1000).toFixed(2)}s
          </span>
        )}

        {panelOpen ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted" />
        )}
      </button>

      {/* Expanded Activity List */}
      {panelOpen && (
        <div className="p-3 rounded-xl border border-border/50 bg-black/50 space-y-2 backdrop-blur-md animate-in fade-in duration-150">
          {/* AI Reasoning / Generation Row */}
          {(reasoningActive || generationActive || aiDurationMs || execState?.ai_requests?.length) && (
            <AIActivityRow
              aiRequest={execState?.ai_requests?.[0]}
              reasoningActive={reasoningActive}
              generationActive={generationActive}
              provider={execState?.provider}
              model={execState?.model}
              durationMs={aiDurationMs}
            />
          )}

          {/* Skill Call Row */}
          {activeSkill && (
            <SkillCallRow
              skillId={activeSkillId || (skillResult?.skill as string) || (execState?.skill_result?.skill as string) || "skill"}
              result={skillResult || execState?.skill_result || initialData?.skill_result}
              status={skillStatus || undefined}
              durationMs={execState?.elapsed_ms}
            />
          )}

          {/* Parallel Groups */}
          {activeParallelGroups.map((group, idx) => (
            <ParallelGroupRow key={group.group_id || idx} group={group} defaultExpanded={false} />
          ))}

          {/* Standalone Tool Calls */}
          {standaloneCalls.map((call, idx) => (
            <ToolCallRow key={call.call_id || idx} call={call} defaultExpanded={false} />
          ))}
        </div>
      )}
    </div>
  );
}
