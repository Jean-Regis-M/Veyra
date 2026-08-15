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
import Reveal from "@/components/Reveal";

// Standard B-DNA structural constants — textbook facts, not engine output.
const DNA_FACTS = [
  { label: "Structure", value: "Right-handed double helix (B-form)" },
  { label: "Bases", value: "Adenine, Thymine, Guanine, Cytosine" },
  { label: "Diameter", value: "~2 nm" },
  { label: "Helical turn", value: "~10.5 bp per turn" },
  { label: "Strands", value: "Antiparallel, complementary" },
];

// The deterministic engine's actual computational steps — not marketing copy.
const ENGINE_STEPS = ["PAM search", "GC content", "Off-target scan", "Seed mismatch", "Specificity ranking"];

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

// Honest, engine-derived facts — not fabricated benchmark numbers.
const STATS = [
  { num: "20 nt", label: "Protospacer window scored" },
  { num: "NGG", label: "SpCas9 PAM recognized" },
  { num: "±4", label: "Mismatches tracked per off-target hit" },
  { num: "0", label: "Scores not traceable to a function" },
];

const MARQUEE_ITEMS = [
  "deterministic by design",
  "full-locus context",
  "no black-box scores",
  "AI-explained risk",
  "illustrative research prototype",
];

function EngineStepsRow({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-wrap gap-2 ${className}`}>
      {ENGINE_STEPS.map((step) => (
        <span
          key={step}
          className="rounded-sm border border-border-strong px-3 py-1.5 font-mono text-xs text-muted"
        >
          {step}
        </span>
      ))}
    </div>
  );
}

function SectionEyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2.5 font-mono text-xs tracking-[0.3em] text-accent uppercase">
      <span className="h-px w-5 bg-border-strong" />
      {children}
    </span>
  );
}

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

      <section className="pt-32 pb-10 px-4 sm:px-6">
        <Reveal className="mx-auto max-w-[1680px]">
          <span className="inline-flex items-center gap-2 rounded-full border border-border-strong px-3.5 py-1.5 font-mono text-[11px] tracking-[0.14em] text-muted uppercase mb-6">
            <span className="veyra-pulse-dot h-1.5 w-1.5 rounded-full bg-accent" />
            Genomic Intelligence · Research Prototype
          </span>
          <h1 className="font-display text-4xl sm:text-5xl font-semibold leading-[1.1] text-foreground max-w-3xl">
            Reasoning over the <mark>whole genomic locus</mark>, not a 20&nbsp;base-pair window.
          </h1>
          <p className="mt-6 text-lg text-muted max-w-xl leading-relaxed">
            VEYRA scores CRISPR guide-RNA candidates with a deterministic engine, layers
            interpretable AI reasoning on top, and renders the result as an interactive 3D
            structure — so every risk assessment is traceable, not a black-box number.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link
              href="/analyze"
              className="inline-flex items-center gap-2 rounded-sm bg-accent px-6 py-3 text-sm font-medium text-accent-foreground hover:opacity-90 transition-opacity"
            >
              Run an analysis
              <ArrowRight size={16} />
            </Link>
            <a
              href="#pipeline"
              className="rounded-sm border border-border-strong px-6 py-3 text-sm text-foreground hover:border-accent transition-colors"
            >
              See the pipeline
            </a>
          </div>
          <EngineStepsRow className="mt-8" />
        </Reveal>
      </section>

      <section className="pt-2 pb-6 px-4 sm:px-6">
        <Reveal className="mx-auto max-w-[1680px] grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 h-[68vh] min-h-[520px] max-h-[780px]">
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
              Specimen
            </p>
            <h2 className="font-display text-4xl font-semibold text-foreground mb-1">DNA</h2>
            <p className="text-sm text-accent italic mb-6">The molecule everything else reasons about</p>

            <dl className="space-y-3 border-t border-border pt-5">
              {DNA_FACTS.map((fact) => (
                <div key={fact.label} className="flex items-baseline justify-between gap-4 text-sm">
                  <dt className="text-muted shrink-0">{fact.label}</dt>
                  <dd className="text-foreground text-right">{fact.value}</dd>
                </div>
              ))}
            </dl>

            <p className="mt-auto pt-6 font-mono text-[11px] text-muted">
              Illustrative prototype — not a validated clinical or diagnostic tool.
            </p>
          </aside>
        </Reveal>
      </section>

      <section className="border-t border-border py-14">
        <Reveal className="mx-auto max-w-6xl px-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 rounded-md border border-border overflow-hidden divide-x divide-y lg:divide-y-0 divide-border">
            {STATS.map((s) => (
              <div key={s.label} className="p-6">
                <div className="font-display text-3xl font-bold text-foreground tracking-tight">{s.num}</div>
                <div className="mt-2 font-mono text-[11px] tracking-wide uppercase text-muted leading-relaxed">
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      <div className="border-y border-border bg-surface py-4 overflow-hidden" aria-hidden="true">
        <div className="veyra-marquee-track flex gap-12 w-max">
          {[...MARQUEE_ITEMS, ...MARQUEE_ITEMS].map((item, i) => (
            <span key={i} className="font-mono text-xs tracking-[0.16em] uppercase text-muted whitespace-nowrap">
              {item}
            </span>
          ))}
        </div>
      </div>

      <section id="pipeline" className="border-t border-border py-24">
        <Reveal className="mx-auto max-w-6xl px-6">
          <SectionEyebrow>The Pipeline</SectionEyebrow>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mt-10">
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
        </Reveal>
      </section>

      <section id="features" className="border-t border-border py-24">
        <Reveal className="mx-auto max-w-6xl px-6">
          <SectionEyebrow>Approach</SectionEyebrow>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-10">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-md border border-border bg-surface-raised p-6">
                <f.icon size={22} className="text-accent mb-4" strokeWidth={1.75} />
                <h3 className="font-display text-foreground font-medium mb-3">{f.title}</h3>
                <p className="text-sm text-muted leading-relaxed">{f.body}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      <section className="dark border-t border-border bg-background text-foreground py-28 text-center">
        <Reveal className="mx-auto max-w-2xl px-6 flex flex-col items-center">
          <SectionEyebrow>Get started</SectionEyebrow>
          <h2 className="font-display text-3xl sm:text-4xl font-semibold text-foreground mt-4 leading-tight">
            Paste a sequence. See the whole locus reason back.
          </h2>
          <p className="mt-5 text-muted leading-relaxed">
            Deterministic scoring, AI-explained risk, and an interactive 3D structure —
            one pipeline, fully traceable.
          </p>
          <Link
            href="/analyze"
            className="mt-8 inline-flex items-center gap-2 rounded-sm bg-accent px-7 py-3.5 text-sm font-medium text-accent-foreground hover:opacity-90 transition-opacity"
          >
            Run an analysis
            <ArrowRight size={16} />
          </Link>
          <EngineStepsRow className="mt-10 justify-center" />
        </Reveal>
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
