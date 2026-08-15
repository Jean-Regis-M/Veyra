"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import DnaHelixModel from "@/components/dna/HelixModel";
import { analyzeSequence, GenomicEngineResult, GuideCandidate } from "@/lib/genomic-engine";
import { EXAMPLE_SEQUENCES } from "@/lib/examples";

interface ReasonResponse {
  summary: string;
  perCandidate: { id: string; note: string }[];
  source: "ai" | "stub";
}

const RISK_STYLES: Record<GuideCandidate["riskLevel"], string> = {
  low: "text-risk-low border-risk-low/40 bg-risk-low/10",
  moderate: "text-risk-moderate border-risk-moderate/40 bg-risk-moderate/10",
  high: "text-risk-high border-risk-high/40 bg-risk-high/10",
};

function SourceTag({ source }: { source: "Engine" | "AI" }) {
  const color = source === "Engine" ? "text-engine border-engine/40" : "text-ai border-ai/40";
  return (
    <span className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${color}`}>
      {source}
    </span>
  );
}

export default function AnalyzeClient() {
  const [sequence, setSequence] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GenomicEngineResult | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reasoning, setReasoning] = useState<ReasonResponse | null>(null);
  const [reasoningLoading, setReasoningLoading] = useState(false);

  function runAnalysis(input: string) {
    try {
      const r = analyzeSequence(input);
      setResult(r);
      setSelectedId(r.candidates[0]?.id ?? null);
      setError(null);
      setReasoning(null);
      void fetchReasoning(input, r.candidates);
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : "Failed to analyze sequence.");
    }
  }

  async function fetchReasoning(seq: string, candidates: GuideCandidate[]) {
    setReasoningLoading(true);
    try {
      const res = await fetch("/api/reason", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sequence: seq, candidates }),
      });
      const data = (await res.json()) as ReasonResponse;
      setReasoning(data);
    } catch {
      setReasoning(null);
    } finally {
      setReasoningLoading(false);
    }
  }

  const selected = useMemo(
    () => result?.candidates.find((c) => c.id === selectedId) ?? null,
    [result, selectedId]
  );

  return (
    <div className="flex-1 pt-24 pb-20 veyra-hero-bg">
      <header className="fixed top-4 inset-x-0 z-50 px-4 sm:px-6">
        <div className="veyra-glass mx-auto max-w-4xl px-5 h-14 flex items-center justify-between rounded-full!">
          <Link href="/" className="flex items-center gap-2 font-display text-sm font-semibold tracking-wide text-foreground">
            <span className="veyra-pulse-dot h-2 w-2 rounded-full bg-primary" />
            VEYRA
          </Link>
          <span className="font-mono text-xs text-muted uppercase tracking-widest">Analysis</span>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mb-8">
          <h1 className="font-display text-2xl font-semibold text-foreground">Guide-RNA analysis</h1>
          <p className="mt-2 text-sm text-muted max-w-2xl">
            Paste a DNA sequence to run the deterministic PAM search, GC/off-target scoring, and
            ranking pipeline. Results are illustrative — see the scope note below.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <div className="veyra-glass p-4 space-y-4">
              <textarea
                value={sequence}
                onChange={(e) => setSequence(e.target.value)}
                placeholder="ACGTGACCTGAGG..."
                rows={8}
                className="w-full rounded-2xl border border-border bg-black/20 p-4 font-mono text-sm text-foreground placeholder:text-muted/50 focus:outline-none focus:border-primary/60"
              />
              {error && <p className="text-sm text-risk-high">{error}</p>}

              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => runAnalysis(sequence)}
                  className="rounded-full bg-linear-to-r from-primary to-secondary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
                >
                  Run analysis
                </button>
                {EXAMPLE_SEQUENCES.map((ex) => (
                  <button
                    key={ex.id}
                    onClick={() => {
                      setSequence(ex.sequence);
                      runAnalysis(ex.sequence);
                    }}
                    className="rounded-full border border-border px-4 py-2.5 text-xs text-muted hover:border-primary/40 hover:text-foreground transition-colors"
                  >
                    {ex.label}
                  </button>
                ))}
              </div>
            </div>

            {result && (
              <div className="veyra-glass overflow-hidden">
                <div className="flex items-center justify-between px-4 pt-4">
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Candidates</span>
                  <SourceTag source="Engine" />
                </div>
                <div className="veyra-readout divide-y divide-border mt-3">
                  {result.candidates.slice(0, 8).map((c) => (
                    <button
                      key={c.id}
                      onClick={() => setSelectedId(c.id)}
                      className={`w-full text-left px-4 py-3 flex items-center justify-between gap-3 hover:bg-white/5 transition-colors ${
                        c.id === selectedId ? "bg-white/5" : ""
                      }`}
                    >
                      <div>
                        <div className="font-mono text-xs text-foreground">
                          {c.sequence} <span className="text-muted">{c.pam}</span>
                        </div>
                        <div className="text-[11px] text-muted mt-1">
                          pos {c.position} · strand {c.strand} · GC {(c.gcContent * 100).toFixed(0)}%
                        </div>
                      </div>
                      <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-mono ${RISK_STYLES[c.riskLevel]}`}>
                        {c.overallScore}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="lg:col-span-3 space-y-4">
            <div className="relative h-[340px]">
              <DnaHelixModel className="h-full w-full" />
            </div>

            {selected && (
              <div className="veyra-glass p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-foreground">{selected.id}</span>
                    <SourceTag source="Engine" />
                  </div>
                  <span className={`rounded-full border px-2.5 py-1 text-[11px] font-mono uppercase ${RISK_STYLES[selected.riskLevel]}`}>
                    {selected.riskLevel} risk
                  </span>
                </div>
                <dl className="veyra-readout grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <dt className="text-muted text-xs">Specificity</dt>
                    <dd className="text-foreground font-mono">{selected.specificityScore}/100</dd>
                  </div>
                  <div>
                    <dt className="text-muted text-xs">GC content</dt>
                    <dd className="text-foreground font-mono">{(selected.gcContent * 100).toFixed(1)}%</dd>
                  </div>
                  <div>
                    <dt className="text-muted text-xs">Off-targets found</dt>
                    <dd className="text-foreground font-mono">{selected.offTargets.length}</dd>
                  </div>
                </dl>
              </div>
            )}

            <div className="veyra-glass p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Reasoning</span>
                <SourceTag source="AI" />
              </div>
              {reasoningLoading && <p className="text-sm text-muted">Generating explanation…</p>}
              {!reasoningLoading && reasoning && (
                <div className="space-y-3">
                  <p className="text-sm text-foreground/90 whitespace-pre-line">{reasoning.summary}</p>
                  {reasoning.source === "stub" && (
                    <p className="text-[11px] font-mono text-muted/70">
                      integration point — not a model-generated response
                    </p>
                  )}
                </div>
              )}
              {!reasoningLoading && !reasoning && (
                <p className="text-sm text-muted">Run an analysis to generate an explanation.</p>
              )}
            </div>

            <p className="text-[11px] font-mono text-muted/70 leading-relaxed">
              Off-target search is scoped to the provided sequence only (no genome-wide index).
              Scores are a simplified heuristic — see docs/scientific-assumptions.md. Research
              prototype, not a clinical or diagnostic tool.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
