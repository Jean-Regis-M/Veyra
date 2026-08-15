import Link from "next/link";
import {
  ArrowRight,
  Dna,
  ScanSearch,
  Layers3,
  BrainCircuit,
  Boxes,
  ShieldCheck,
  Microscope,
  FlaskConical,
} from "lucide-react";
import DnaHelixModel from "@/components/dna/HelixModel";

// Standard B-DNA structural constants — textbook facts, not engine output.
const DNA_FACTS = [
  { label: "Structure", value: "Right-handed double helix (B-form)" },
  { label: "Bases", value: "Adenine, Thymine, Guanine, Cytosine" },
  { label: "Diameter", value: "~2 nm" },
  { label: "Helical turn", value: "~10.5 bp per turn" },
  { label: "Strands", value: "Antiparallel, complementary" },
];

const PIPELINE_STEPS = [
  { icon: Dna, label: "Sequence", detail: "Ingest raw DNA input" },
  { icon: ScanSearch, label: "Deterministic scoring", detail: "PAM search · GC · off-target · seed mismatch" },
  { icon: Layers3, label: "Genomic context", detail: "Ranked candidates, structured features" },
  { icon: BrainCircuit, label: "AI reasoning", detail: "Explains risk in plain language" },
  { icon: Boxes, label: "Visualization", detail: "Interactive 3D helix, cut-site highlighting" },
];

const FEATURES = [
  {
    icon: ShieldCheck,
    title: "Deterministic core",
    body: "Every score traces to a reproducible algorithm — PAM search, GC content, seed-weighted mismatch analysis. No black box.",
  },
  {
    icon: Microscope,
    title: "Full-locus context",
    body: "Reasoning over the complete provided sequence, not a short isolated window — surfacing risk that short-window tools miss.",
  },
  {
    icon: FlaskConical,
    title: "Interpretable AI layer",
    body: "AI explains why a site is risky, tied to the underlying deterministic numbers — never a bare probability score.",
  },
];

export default function Home() {
  return (
    <div className="flex-1">
      <header className="fixed top-0 inset-x-0 z-50 border-b border-border bg-background/85 backdrop-blur-md">
        <div className="mx-auto max-w-6xl px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2 font-mono text-sm tracking-widest text-foreground">
            <span className="h-2 w-2 rounded-full bg-accent" />
            VEYRA
          </div>
          <nav className="hidden sm:flex items-center gap-8 text-sm text-muted">
            <a href="#pipeline" className="hover:text-foreground transition-colors">Pipeline</a>
            <a href="#features" className="hover:text-foreground transition-colors">Approach</a>
          </nav>
          <Link
            href="/analyze"
            className="rounded-sm border border-border-strong px-4 py-2 text-sm text-foreground hover:border-accent hover:text-accent transition-colors"
          >
            Launch analysis
          </Link>
        </div>
      </header>

      <section className="pt-20 pb-6 px-4 sm:px-6">
        <div className="mx-auto max-w-[1680px] grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 h-[72vh] min-h-[560px] max-h-[840px]">
          <div className="veyra-grid-bg relative rounded-md border border-border bg-surface-raised shadow-[0_1px_0_rgba(20,19,17,0.04),0_8px_24px_-12px_rgba(20,19,17,0.15)] overflow-hidden">
            <DnaHelixModel className="h-full w-full" />
            <span className="absolute top-4 left-5 font-mono text-[11px] tracking-widest text-muted uppercase">
              3D specimen · drag to rotate · click a dot to explore
            </span>
            <span className="absolute bottom-3 right-4 font-mono text-[10px] text-muted/80">
              3D model: &ldquo;DNA&rdquo; by LucasPresoto (Sketchfab), CC BY 4.0
            </span>
          </div>

          <aside className="rounded-md border border-border bg-surface-raised p-6 flex flex-col overflow-y-auto">
            <p className="font-mono text-xs tracking-[0.3em] text-accent uppercase mb-3">
              Genomic Intelligence
            </p>
            <h1 className="font-display text-4xl font-semibold text-foreground mb-1">DNA</h1>
            <p className="text-sm text-accent italic mb-5">The molecule everything else reasons about</p>
            <p className="text-sm text-muted leading-relaxed mb-6">
              VEYRA scores CRISPR guide-RNA candidates with a deterministic engine, layers
              interpretable AI reasoning on top, and renders the result as an interactive 3D
              structure — every risk assessment is traceable, not a black-box number.
            </p>

            <dl className="space-y-3 border-t border-border pt-5 mb-6">
              {DNA_FACTS.map((fact) => (
                <div key={fact.label} className="flex items-baseline justify-between gap-4 text-sm">
                  <dt className="text-muted shrink-0">{fact.label}</dt>
                  <dd className="text-foreground text-right">{fact.value}</dd>
                </div>
              ))}
            </dl>

            <div className="mt-auto space-y-2">
              <Link
                href="/analyze"
                className="flex items-center justify-center gap-2 rounded-sm bg-accent px-5 py-3 text-sm font-medium text-accent-foreground hover:opacity-90 transition-opacity"
              >
                Run an analysis
                <ArrowRight size={16} />
              </Link>
              <a
                href="#pipeline"
                className="flex items-center justify-center rounded-sm border border-border-strong px-5 py-3 text-sm text-foreground hover:border-accent transition-colors"
              >
                See the pipeline
              </a>
            </div>
            <p className="mt-4 font-mono text-[11px] text-muted">
              Illustrative prototype — not a validated clinical or diagnostic tool.
            </p>
          </aside>
        </div>
      </section>

      <section id="pipeline" className="border-t border-border py-24">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="font-mono text-sm tracking-[0.3em] text-accent uppercase mb-12">
            The Pipeline
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {PIPELINE_STEPS.map((step, i) => (
              <div
                key={step.label}
                className="rounded-md border border-border bg-surface-raised p-5 hover:border-border-strong hover:shadow-[0_2px_4px_rgba(20,19,17,0.06)] transition-all"
              >
                <div className="flex items-center justify-between mb-4">
                  <step.icon size={20} className="text-accent" strokeWidth={1.75} />
                  <span className="font-mono text-xs text-muted">{String(i + 1).padStart(2, "0")}</span>
                </div>
                <h3 className="font-display text-foreground font-medium mb-1.5">{step.label}</h3>
                <p className="text-sm text-muted leading-relaxed">{step.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="features" className="border-t border-border py-24">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="font-mono text-sm tracking-[0.3em] text-accent uppercase mb-12">
            Approach
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-md border border-border bg-surface-raised p-6">
                <f.icon size={22} className="text-accent mb-4" strokeWidth={1.75} />
                <h3 className="font-display text-foreground font-medium mb-3">{f.title}</h3>
                <p className="text-sm text-muted leading-relaxed">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-border py-10">
        <div className="mx-auto max-w-6xl px-6 flex flex-col sm:flex-row justify-between gap-4 text-xs text-muted font-mono">
          <span>VEYRA — Genomic Intelligence</span>
          <span>Research prototype. Not for clinical or diagnostic use.</span>
        </div>
      </footer>
    </div>
  );
}
