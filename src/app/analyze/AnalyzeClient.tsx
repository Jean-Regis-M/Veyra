"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import DnaHelix, { HelixHighlight } from "@/components/dna/Helix";
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

  const highlights: HelixHighlight[] = useMemo(() => {
    if (!selected) return [];
    // Highlight the protospacer window on the rendered helix.
    return Array.from({ length: selected.sequence.length }, (_, i) => ({
      position: selected.position + i,
      riskLevel: selected.riskLevel,
    }));
  }, [selected]);

  return (
    <div className="flex-1 pt-24 pb-20">
      <header className="fixed top-0 inset-x-0 z-50 border-b border-border/60 bg-background/70 backdrop-blur-md">
        <div className="mx-auto max-w-6xl px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 font-mono text-sm tracking-widest text-foreground">
            <span className="h-2 w-2 rounded-full bg-accent" />
            VEYRA
          </Link>
          <span className="font-mono text-xs text-muted uppercase tracking-widest">Analysis</span>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-foreground">Guide-RNA analysis</h1>
          <p className="mt-2 text-sm text-muted max-w-2xl">
            Paste a DNA sequence to run the deterministic PAM search, GC/off-target scoring, and
            ranking pipeline. Results are illustrative — see the scope note below.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          <div className="lg:col-span-2 space-y-4">
            <textarea
              value={sequence}
              onChange={(e) => setSequence(e.target.value)}
              placeholder="ACGTGACCTGAGG..."
              rows={8}
              className="w-full rounded-lg border border-border bg-surface p-4 font-mono text-sm text-foreground placeholder:text-muted/50 focus:outline-none focus:border-accent/60"
            />
            {error && <p className="text-sm text-risk-high">{error}</p>}

            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => runAnalysis(sequence)}
                className="rounded-md bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground hover:opacity-90 transition-opacity"
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
                  className="rounded-md border border-border px-4 py-2.5 text-xs text-muted hover:border-accent/40 hover:text-foreground transition-colors"
                >
                  {ex.label}
                </button>
              ))}
            </div>

            {result && (
              <div className="rounded-lg border border-border bg-surface/60 divide-y divide-border">
                {result.candidates.slice(0, 8).map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setSelectedId(c.id)}
                    className={`w-full text-left px-4 py-3 flex items-center justify-between gap-3 hover:bg-surface-raised transition-colors ${
                      c.id === selectedId ? "bg-surface-raised" : ""
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
                    <span className={`shrink-0 rounded border px-2 py-1 text-[11px] font-mono ${RISK_STYLES[c.riskLevel]}`}>
                      {c.overallScore}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="lg:col-span-3 space-y-4">
            <div className="rounded-2xl border border-border bg-surface/40 h-[340px] overflow-hidden">
              <DnaHelix
                basePairs={selected ? Math.max(selected.sequence.length + 8, 32) : 40}
                highlights={highlights}
                className="h-full w-full"
              />
            </div>

            {selected && (
              <div className="rounded-lg border border-border bg-surface/60 p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="font-mono text-sm text-foreground">{selected.id}</h2>
                  <span className={`rounded border px-2 py-1 text-[11px] font-mono uppercase ${RISK_STYLES[selected.riskLevel]}`}>
                    {selected.riskLevel} risk
                  </span>
                </div>
                <dl className="grid grid-cols-3 gap-4 text-sm">
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

            <div className="rounded-lg border border-border bg-surface/60 p-5">
              <h2 className="font-mono text-xs uppercase tracking-widest text-accent mb-3">
                AI reasoning
              </h2>
              {reasoningLoading && <p className="text-sm text-muted">Generating explanation…</p>}
              {!reasoningLoading && reasoning && (
                <div className="space-y-3">
                  <p className="text-sm text-muted whitespace-pre-line">{reasoning.summary}</p>
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
