"use client";

import { useMemo } from "react";
import { Dna, ChevronRight, ChevronLeft, Target, Award } from "lucide-react";
import DnaHelixModel from "@/components/dna/HelixModel";
import { ExecutionActivity } from "@/components/execution";
import { ExecutionStatus } from "@/lib/midend";

export interface SelectedCandidateContext {
  id?: string;
  protospacer?: string;
  sequence?: string;
  pam?: string;
  strand?: "+" | "-" | string;
  position?: number;
  rank?: number | null;
  cutSiteRelative?: number | null;
  cutSiteGenomic?: number | null;
  gcContent?: number | null;
  tm?: number | null;
  mfe?: number | null;
  onTargetScore?: number | null;
  cfdScore?: number | null;
  offTargetCount?: number | null;
}

export interface AnalysisContextData {
  sequence?: string;
  filename?: string;
  inputId?: string;
  executionId?: string;
  executionStatus?: ExecutionStatus | null;
  selectedCandidate?: SelectedCandidateContext | null;
  candidates?: SelectedCandidateContext[];
}

interface DnaAnalysisPanelProps {
  context?: AnalysisContextData | null;
  isOpen: boolean;
  onToggle: () => void;
  onSelectCandidate?: (candidate: SelectedCandidateContext) => void;
}

function gcToColor(gc: number): string {
  const clamped = Math.max(0, Math.min(1, gc > 1 ? gc / 100 : gc));
  const hue = 160 + clamped * 160;
  return `hsl(${hue.toFixed(0)}, 70%, 55%)`;
}

export function DnaAnalysisPanel({
  context,
  isOpen,
  onToggle,
  onSelectCandidate,
}: DnaAnalysisPanelProps) {
  const candidate = context?.selectedCandidate || context?.candidates?.[0] || null;
  const candGc = candidate?.gcContent;

  // Use authoritative GC content from candidate/tool result if available; otherwise neutral tint
  const tintColor = useMemo(() => {
    if (candGc !== undefined && candGc !== null) {
      return gcToColor(candGc);
    }
    return "#eef3ee";
  }, [candGc]);

  return (
    <>
      {/* Collapsed rail — animates in/out rather than hard-swapping with the panel */}
      <button
        type="button"
        onClick={onToggle}
        aria-hidden={isOpen}
        tabIndex={isOpen ? -1 : 0}
        className={`veyra-tab-pulse fixed right-4 top-24 z-40 flex items-center gap-2 rounded-full border border-primary/40 bg-black/80 px-3.5 py-2 text-xs font-mono text-primary backdrop-blur-md hover:bg-primary/10 transition-all duration-300 cursor-pointer ${
          isOpen ? "translate-x-6 opacity-0 pointer-events-none" : "translate-x-0 opacity-100"
        }`}
        title="Open DNA & Analysis Panel"
      >
        <Dna size={15} className="animate-pulse text-primary" />
        <span className="hidden sm:inline font-semibold">DNA & Evidence</span>
        <ChevronLeft size={14} />
      </button>

      {/* Slide-out panel — always mounted; a collapsing width wrapper does the
          animation so nothing pops in/out abruptly. Reflows the main column
          (rather than overlaying it) so the session banner and header toggle
          stay visible; a one-shot click-triggered transition on a single
          element, not a scroll/drag-driven one, so width is fine here. */}
      <aside
        aria-hidden={!isOpen}
        className={`veyra-panel-slide relative shrink-0 overflow-hidden border-l ${
          isOpen ? "w-full lg:w-105 border-border/60 opacity-100" : "w-0 border-transparent opacity-0"
        }`}
      >
        <div className="relative h-full w-full lg:w-105 bg-black/70 backdrop-blur-xl p-4 space-y-4 max-h-[calc(100vh-5rem)] overflow-y-auto custom-scrollbar">
          {/* Futuristic scan-line accent along the panel's leading edge */}
          <div className="pointer-events-none absolute left-0 top-0 h-24 w-px overflow-hidden">
            <div className="veyra-scan-sweep h-8 w-px bg-linear-to-b from-transparent via-primary to-transparent" />
          </div>

          {/* Header */}
          <div className="flex items-center justify-between border-b border-border/40 pb-3">
            <div className="flex items-center gap-2">
              <Dna size={18} className="text-primary" />
              <h2 className="font-display text-sm font-semibold text-foreground">
                DNA & Analysis Context
              </h2>
            </div>
            <button
              type="button"
              onClick={onToggle}
              className="rounded-full p-1.5 text-muted hover:text-foreground hover:bg-white/10 transition-colors cursor-pointer"
              aria-label="Close side panel"
            >
              <ChevronRight size={16} />
            </button>
          </div>

      {/* 3D DNA Model View */}
      <div className="rounded-xl border border-border/40 bg-black/40 overflow-hidden relative">
        <div className="h-44 w-full">
          <DnaHelixModel tintColor={tintColor} className="h-full w-full" autoRotate={true} />
        </div>
        <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between px-2 py-1 rounded bg-black/60 backdrop-blur-md text-[10px] font-mono text-muted border border-border/30">
          <span>
            GC: {candidate?.gcContent !== undefined && candidate.gcContent !== null
              ? `${(candidate.gcContent > 1 ? candidate.gcContent : candidate.gcContent * 100).toFixed(1)}%`
              : "Pending tool execution"}
          </span>
          <span className="text-secondary">{context?.sequence ? `${context.sequence.length} bp` : "Active Context"}</span>
        </div>
      </div>

      {/* Selected Guide Candidate Card */}
      {candidate ? (
        <div className="rounded-xl border border-primary/40 bg-primary/5 p-3.5 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5 font-mono text-xs font-semibold text-primary">
              <Target size={14} />
              Selected Guide Candidate
            </span>
            {candidate.rank !== undefined && candidate.rank !== null && (
              <span className="inline-flex items-center gap-1 rounded-full bg-primary/20 border border-primary/40 px-2 py-0.5 font-mono text-[10px] text-primary font-bold">
                <Award size={11} />
                Rank #{candidate.rank}
              </span>
            )}
          </div>

          {/* 2D Linear Track Representation with Cut Site */}
          <div className="rounded-lg border border-border/50 bg-black/60 p-2.5 space-y-1.5 font-mono">
            <div className="flex items-center justify-between text-[10px] text-muted">
              <span>5&apos; Protospacer (20 nt)</span>
              <span className="text-ai font-semibold">PAM (3 nt)</span>
            </div>
            <div className="flex items-center text-xs tracking-wider font-bold overflow-x-auto py-1">
              <span className="text-foreground bg-white/5 px-1.5 py-0.5 rounded-l">
                {candidate.protospacer || candidate.sequence || "—"}
              </span>
              <span className="text-ai bg-ai/20 px-1.5 py-0.5 rounded-r border-l border-ai/40">
                {candidate.pam || "—"}
              </span>
            </div>
            {/* Cut mark */}
            <div className="flex items-center gap-1.5 text-[10px] text-engine pt-0.5 border-t border-border/20">
              <span className="h-2 w-0.5 bg-engine rounded-full" />
              <span>
                {candidate.cutSiteRelative !== undefined && candidate.cutSiteRelative !== null
                  ? `Cut Site: Relative pos ${candidate.cutSiteRelative}`
                  : "Cut Site: Inferred canonical (pos 17|18)"}
                {candidate.cutSiteGenomic ? ` (Genomic: ${candidate.cutSiteGenomic})` : ""}
              </span>
              <span className="ml-auto text-muted/80">Strand ({candidate.strand || "+"})</span>
            </div>
          </div>

          {/* Authoritative Metrics Grid (from backend/MIDEND) */}
          <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
            <div className="p-2 rounded bg-black/40 border border-border/30">
              <span className="text-muted text-[9px] uppercase block">GC Content</span>
              <span className="text-foreground font-semibold veyra-readout">
                {candidate.gcContent !== undefined && candidate.gcContent !== null
                  ? `${(candidate.gcContent > 1 ? candidate.gcContent : candidate.gcContent * 100).toFixed(1)}%`
                  : "—"}
              </span>
            </div>
            <div className="p-2 rounded bg-black/40 border border-border/30">
              <span className="text-muted text-[9px] uppercase block">Melting Temp (Tm)</span>
              <span className="text-foreground font-semibold veyra-readout">
                {candidate.tm !== undefined && candidate.tm !== null
                  ? `${Number(candidate.tm).toFixed(1)} °C`
                  : "—"}
              </span>
            </div>
            <div className="p-2 rounded bg-black/40 border border-border/30">
              <span className="text-muted text-[9px] uppercase block">On-Target Score</span>
              <span className="text-foreground font-semibold veyra-readout">
                {candidate.onTargetScore !== undefined && candidate.onTargetScore !== null
                  ? String(candidate.onTargetScore)
                  : "—"}
              </span>
            </div>
            <div className="p-2 rounded bg-black/40 border border-border/30">
              <span className="text-muted text-[9px] uppercase block">Off-Target CFD</span>
              <span className="text-foreground font-semibold veyra-readout">
                {candidate.cfdScore !== undefined && candidate.cfdScore !== null
                  ? String(candidate.cfdScore)
                  : candidate.offTargetCount !== undefined
                  ? `${candidate.offTargetCount} hits`
                  : "—"}
              </span>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-border/60 p-4 text-center text-xs text-muted">
          Attach a gene file or select a candidate to view linear track and cut-site data.
        </div>
      )}

      {/* Candidate List Picker if multiple exist */}
      {context?.candidates && context.candidates.length > 1 && (
        <div className="space-y-1.5">
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted block">
            Ranked Candidates ({context.candidates.length})
          </span>
          <div className="max-h-40 overflow-y-auto space-y-1 pr-1 font-mono text-xs custom-scrollbar">
            {context.candidates.map((c, i) => {
              const isSelected = (c.protospacer || c.sequence) === (candidate?.protospacer || candidate?.sequence);
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => onSelectCandidate?.(c)}
                  className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-left transition-colors cursor-pointer border ${
                    isSelected
                      ? "border-primary/60 bg-primary/15 text-foreground font-semibold"
                      : "border-border/30 bg-black/30 text-muted hover:text-foreground hover:bg-white/5"
                  }`}
                >
                  <span className="truncate max-w-50">
                    {c.protospacer || c.sequence}
                  </span>
                  <span className="text-[10px] text-primary shrink-0">
                    {c.rank !== undefined && c.rank !== null ? `Rank #${c.rank}` : `#${i + 1}`}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

          {/* Live Tool & Execution Activity Section */}
          {context?.executionId && (
            <div className="pt-2 border-t border-border/40">
              <ExecutionActivity
                executionId={context.executionId}
                initialData={context.executionStatus}
                live={true}
                title="Live Tool Activity"
                defaultCollapsed={false}
              />
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
