"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { MessageSquare, ArrowRight } from "lucide-react";
import DnaHelixModel from "@/components/dna/HelixModel";
import { Header } from "@/components/Header";
import { analyzeSequence, GenomicEngineResult, GuideCandidate } from "@/lib/genomic-engine";
import { EXAMPLE_SEQUENCES } from "@/lib/examples";
import {
  BackendCallResult,
  buildOnTargetContext,
  checkBackendHealth,
  checkHomopolymerRuns,
  CfdScoreResult,
  computeMeltingTemp,
  HomopolymerResult,
  IngestedRecord,
  ingestFile,
  MeltingTempResult,
  OnTargetScoreResult,
  scoreOffTargetsCFD,
  scoreOnTarget,
} from "@/lib/backend";

const CFD_OFFTARGET_CAP = 8; // keep the scoring request small and fast

function riskBucket(cfd: number): "high" | "moderate" | "low" {
  if (cfd >= 0.5) return "high";
  if (cfd >= 0.1) return "moderate";
  return "low";
}

// Interpolating hue directly (not RGB-lerping two hex colors) — an RGB lerp
// between green and pink desaturates through a muddy gray at the midpoint,
// which is exactly what read as "just light and dark" for balanced-GC
// sequences. Fixed saturation/lightness keeps every GC% visibly distinct.
function gcToColor(gc: number): string {
  const hue = 160 + gc * 160; // 160° teal-green (low GC) -> 320° magenta (high GC)
  return `hsl(${hue.toFixed(0)}, 70%, 55%)`;
}

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
  const router = useRouter();
  const [sequence, setSequence] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GenomicEngineResult | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reasoning, setReasoning] = useState<ReasonResponse | null>(null);
  const [reasoningLoading, setReasoningLoading] = useState(false);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [onTargetLoading, setOnTargetLoading] = useState(false);
  const [onTarget, setOnTarget] = useState<BackendCallResult<OnTargetScoreResult> | null>(null);
  const [offTargetCfdLoading, setOffTargetCfdLoading] = useState(false);
  const [offTargetCfd, setOffTargetCfd] = useState<BackendCallResult<CfdScoreResult> | null>(null);
  const [tm, setTm] = useState<BackendCallResult<MeltingTempResult> | null>(null);
  const [homopolymer, setHomopolymer] = useState<BackendCallResult<HomopolymerResult> | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadedRecords, setUploadedRecords] = useState<IngestedRecord[] | null>(null);

  function continueInVeyra(withReasoning = false) {
    if (!sequence) return;
    const analysisContext = {
      sequence: sequence,
      inputId: uploadedRecords?.[0]?.id || null,
      selectedCandidate: selected
        ? {
            id: selected.id,
            protospacer: selected.sequence,
            pam: selected.pam,
            strand: selected.strand,
            position: selected.position,
            gcContent: selected.gcContent,
            tm: tm?.ok ? tm.data.tmCelsius : null,
            onTargetScore: onTarget?.ok ? onTarget.data.score : null,
            cfdScore: offTargetCfd?.ok ? offTargetCfd.data.maxCfd : null,
          }
        : null,
      reasoningSummary: withReasoning ? reasoning?.summary : null,
    };
    if (typeof window !== "undefined") {
      sessionStorage.setItem("veyra_analysis_continuation", JSON.stringify(analysisContext));
    }
    router.push("/chat");
  }

  async function handleFileUpload(file: File) {
    setUploading(true);
    setUploadError(null);
    setUploadedRecords(null);
    const result = await ingestFile(file);
    setUploading(false);
    if (!result.ok) {
      setUploadError(result.error);
      return;
    }
    if (result.data.length === 1) {
      const rec = result.data[0];
      const seq = rec.sequence.length > 5000 ? rec.sequence.slice(0, 5000) : rec.sequence;
      setSequence(seq);
      if (rec.sequence.length > 5000) {
        setError(`Note: The uploaded genome/sequence is ${rec.length.toLocaleString()} bp. Loaded the first 5,000 bp for in-browser guide design.`);
      }
      runAnalysis(seq);
    } else {
      setUploadedRecords(result.data);
    }
  }

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
        body: JSON.stringify({ sequence: seq.slice(0, 5000), candidates }),
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

  // The shared DNA model's own material tint, driven by the pasted
  // sequence's GC content — 0% GC renders green, 100% GC renders pink,
  // interpolated between. Neutral (landing's default) until a result exists.
  const tintColor = useMemo(() => {
    if (!result) return "#eef3ee";
    const sampleLen = Math.min(sequence.length, 5000);
    let gcCount = 0;
    let validCount = 0;
    for (let i = 0; i < sampleLen; i++) {
      const ch = sequence[i].toUpperCase();
      if (ch === "G" || ch === "C") {
        gcCount++;
        validCount++;
      } else if (ch === "A" || ch === "T") {
        validCount++;
      }
    }
    if (validCount === 0) return "#eef3ee";
    const gc = gcCount / validCount;
    return gcToColor(gc);
  }, [result, sequence]);

  useEffect(() => {
    void checkBackendHealth().then(setBackendOnline);
  }, []);

  useEffect(() => {
    if (!selected || !backendOnline) return;
    const context = buildOnTargetContext(sequence, selected);
    if (!context) return;
    let cancelled = false;
    Promise.resolve().then(() => {
      if (!cancelled) setOnTargetLoading(true);
      return scoreOnTarget(context);
    }).then((r) => {
      if (!cancelled) {
        setOnTarget(r);
        setOnTargetLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [selected, backendOnline, sequence]);

  useEffect(() => {
    if (!selected || !backendOnline) return;
    const scorable = selected.offTargets
      .filter((h): h is typeof h & { pam: string } => h.pam !== null)
      .slice(0, CFD_OFFTARGET_CAP);
    if (scorable.length === 0) return;
    let cancelled = false;
    Promise.resolve().then(() => {
      if (!cancelled) setOffTargetCfdLoading(true);
      return scoreOffTargetsCFD(
        selected.sequence,
        scorable.map((h) => ({ protospacer: h.sequence, pam: h.pam }))
      );
    }).then((r) => {
      if (!cancelled) {
        setOffTargetCfd(r);
        setOffTargetCfdLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [selected, backendOnline]);

  useEffect(() => {
    if (!selected || !backendOnline) return;
    let cancelled = false;
    computeMeltingTemp(selected.sequence).then((r) => {
      if (!cancelled) setTm(r);
    });
    checkHomopolymerRuns(selected.sequence).then((r) => {
      if (!cancelled) setHomopolymer(r);
    });
    return () => {
      cancelled = true;
    };
  }, [selected, backendOnline]);

  const riskCounts = useMemo(() => {
    if (!offTargetCfd?.ok) return null;
    const counts = { high: 0, moderate: 0, low: 0 };
    for (const hit of offTargetCfd.data.scored) counts[riskBucket(hit.cfdScore)]++;
    return counts;
  }, [offTargetCfd]);

  return (
    <div className="flex-1 pt-24 pb-20 veyra-hero-bg">
      <Header online={backendOnline} />

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
                <label className="rounded-full border border-border px-4 py-2.5 text-xs text-muted hover:border-primary/40 hover:text-foreground transition-colors cursor-pointer">
                  {uploading ? "Parsing…" : "Upload FASTA / FASTQ / GenBank"}
                  <input
                    type="file"
                    accept=".fa,.fasta,.fna,.faa,.fq,.fastq,.gb,.gbk,.gbff,.genbank"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      e.target.value = "";
                      if (file) void handleFileUpload(file);
                    }}
                  />
                </label>
              </div>
              {uploadError && <p className="text-sm text-risk-high">{uploadError}</p>}
              {uploadedRecords && (
                <div className="space-y-1.5">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
                    {uploadedRecords.length} records — pick one
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {uploadedRecords.map((r) => (
                      <button
                        key={r.id}
                        onClick={() => {
                          setSequence(r.sequence);
                          setUploadedRecords(null);
                          runAnalysis(r.sequence);
                        }}
                        className="rounded-full border border-border px-3 py-1.5 text-xs text-muted hover:border-primary/40 hover:text-foreground transition-colors"
                        title={r.description}
                      >
                        {r.id || r.accession || "record"} ({r.length}bp)
                      </button>
                    ))}
                  </div>
                </div>
              )}
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

                <div className="p-3 border-t border-border/40 bg-black/40 flex items-center justify-between">
                  <span className="text-xs text-muted">Explore with Grounded AI</span>
                  <button
                    type="button"
                    onClick={() => continueInVeyra(false)}
                    className="inline-flex items-center gap-1.5 rounded-full bg-linear-to-r from-primary to-secondary px-4 py-1.5 text-xs font-semibold text-primary-foreground hover:opacity-90 transition-opacity cursor-pointer shadow-md"
                  >
                    <MessageSquare size={13} />
                    <span>Continue in VEYRA</span>
                    <ArrowRight size={13} />
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="lg:col-span-3 space-y-4">
            <div className="relative h-[340px]">
              <DnaHelixModel className="h-full w-full" tintColor={tintColor} />
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

            {selected && backendOnline && (
              <div className="veyra-glass p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
                    Off-target risk · CFD (backend)
                  </span>
                  <SourceTag source="Engine" />
                </div>
                {offTargetCfdLoading && <p className="text-sm text-muted">Scoring off-targets via backend…</p>}
                {!offTargetCfdLoading && offTargetCfd && !offTargetCfd.ok && (
                  <p className="text-sm text-muted">{offTargetCfd.error}</p>
                )}
                {!offTargetCfdLoading && offTargetCfd?.ok && riskCounts && (
                  <>
                    {offTargetCfd.data.scored.length === 0 ? (
                      <p className="text-sm text-muted">
                        {selected.offTargets.length === 0
                          ? "No off-target hits found within the input sequence."
                          : "Off-target hits found, but none extend far enough to include a PAM — CFD scoring needs one."}
                      </p>
                    ) : (
                      <>
                        <div className="flex gap-2">
                          <span className="rounded-full border px-2.5 py-1 text-[11px] font-mono border-risk-high/40 text-risk-high bg-risk-high/10">
                            {riskCounts.high} high
                          </span>
                          <span className="rounded-full border px-2.5 py-1 text-[11px] font-mono border-risk-moderate/40 text-risk-moderate bg-risk-moderate/10">
                            {riskCounts.moderate} moderate
                          </span>
                          <span className="rounded-full border px-2.5 py-1 text-[11px] font-mono border-risk-low/40 text-risk-low bg-risk-low/10">
                            {riskCounts.low} low
                          </span>
                        </div>
                        <p className="text-[11px] text-muted leading-relaxed">
                          {selected.id} has {selected.offTargets.length} off-target site
                          {selected.offTargets.length === 1 ? "" : "s"} within the input sequence
                          {selected.offTargets.length > offTargetCfd.data.scored.length
                            ? `; the ${offTargetCfd.data.scored.length} closest were CFD-scored (max ${offTargetCfd.data.maxCfd?.toFixed(2)})`
                            : ` — all CFD-scored (max ${offTargetCfd.data.maxCfd?.toFixed(2)})`}
                          . Higher CFD means a mismatched site is more likely to still be cut by Cas9.
                        </p>
                      </>
                    )}
                  </>
                )}
              </div>
            )}

            {selected && backendOnline && (
              <div className="veyra-glass p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
                    Sequence QC · backend
                  </span>
                  <SourceTag source="Engine" />
                </div>
                <dl className="veyra-readout grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <dt className="text-muted text-xs">Melting temp (Tm)</dt>
                    <dd className="text-foreground font-mono">
                      {tm?.ok ? `${tm.data.tmCelsius.toFixed(1)}°C` : tm && !tm.ok ? "—" : "…"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted text-xs">Homopolymer runs</dt>
                    <dd className="text-foreground font-mono">
                      {homopolymer?.ok
                        ? homopolymer.data.maxRun > 0
                          ? `max ${homopolymer.data.maxRun}nt${homopolymer.data.passesFilter ? "" : " ⚠"}`
                          : "none"
                        : homopolymer && !homopolymer.ok
                          ? "—"
                          : "…"}
                    </dd>
                  </div>
                </dl>
              </div>
            )}

            {selected && backendOnline && (
              <div className="veyra-glass p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
                    On-target efficiency · backend model
                  </span>
                  <SourceTag source="Engine" />
                </div>
                {onTargetLoading && <p className="text-sm text-muted">Scoring via backend…</p>}
                {!onTargetLoading && onTarget && !onTarget.ok && (
                  <p className="text-sm text-muted">{onTarget.error}</p>
                )}
                {!onTargetLoading && onTarget?.ok && (
                  <div className="space-y-2">
                    <div className="flex items-baseline gap-3">
                      <span className="veyra-readout font-mono text-2xl text-foreground">
                        {onTarget.data.score.toFixed(2)}
                      </span>
                      <span className="text-xs text-muted">/ 1.0 · {onTarget.data.modelUsed.replace(/_/g, " ")}</span>
                    </div>
                    {onTarget.data.fallbackUsed && (
                      <p className="text-[11px] text-muted leading-relaxed">
                        Preferred model unavailable in this deployment — fell back through{" "}
                        {onTarget.data.fallbackChain.map((f) => f.model.replace(/_/g, " ")).join(" → ")}.
                      </p>
                    )}
                    <p className="text-[11px] font-mono text-muted/70 truncate">{onTarget.data.modelSource}</p>
                  </div>
                )}
              </div>
            )}

            {backendOnline === false && (
              <p className="text-[11px] font-mono text-muted/70">
                Backend engine offline — showing client-side heuristic scores only.
              </p>
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
                  <div className="pt-2 border-t border-border/30 flex items-center justify-between">
                    <span className="text-[11px] font-mono text-muted/70">
                      {reasoning.source === "ai" ? "Grounded AI Co-Pilot analysis" : "Deterministic preview"}
                    </span>
                    <button
                      type="button"
                      onClick={() => continueInVeyra(true)}
                      className="inline-flex items-center gap-1.5 text-xs font-mono text-primary hover:underline cursor-pointer"
                    >
                      <span>Continue this in chat</span>
                      <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              )}
              {!reasoningLoading && !reasoning && (
                <p className="text-sm text-muted">Run an analysis to generate an explanation.</p>
              )}
            </div>

            <p className="text-[11px] font-mono text-muted/70 leading-relaxed">
              Off-target search is scoped to the provided sequence only (no genome-wide reference
              index). When the backend is online, off-target and on-target scores use published
              algorithms (CFD, Rule Set 3 / Doench 2014); otherwise scores are the client-side
              heuristic only — see docs/scientific-assumptions.md. Research prototype, not a
              clinical or diagnostic tool.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
