import Link from "next/link";
import { ArrowRight, Play } from "lucide-react";
import DnaHelixModel from "@/components/dna/HelixModel";
import PipelineDemo from "@/components/PipelineDemo";
import Reveal from "@/components/Reveal";
import { Header } from "@/components/Header";

// The deterministic engine's actual computational steps — not marketing copy.
const ENGINE_STEPS = ["PAM search", "GC content", "Off-target scan", "Seed mismatch", "Specificity ranking"];

const FEATURES = [
  {
    title: "Deterministic core",
    body: "Every score traces to a reproducible algorithm — PAM search, GC content, seed-weighted mismatch analysis. No black box.",
  },
  {
    title: "Full-locus context",
    body: "Reasoning over the complete provided sequence, not a short isolated window — surfacing risk that short-window tools miss.",
  },
  {
    title: "Interpretable AI layer",
    body: "AI explains why a site is risky, tied to the underlying deterministic numbers — never a bare probability score.",
  },
];

// Honest, engine-derived readouts — not fabricated benchmark numbers.
const READOUTS = [
  { num: "20nt", label: "Protospacer window scored" },
  { num: "NGG", label: "SpCas9 PAM recognized" },
  { num: "±4", label: "Mismatches tracked per off-target hit" },
  { num: "0", label: "Scores not traceable to a function" },
];

// Real, published, cited cases — not VEYRA's own results. Every claim here
// mirrors what the source explicitly established, including where it
// explicitly did NOT find patient harm. Never state more than the source does.
const REAL_WORLD_CASES = [
  {
    sector: "Human medicine",
    finding:
      "In a first-in-human CRISPR-Cas9 sickle-cell study, patients' blood stem cells were edited outside the body and returned. The safety programme specifically investigates unintended genomic changes in these cells — the study did not establish that an off-target mutation harmed patients.",
    source: "New England Journal of Medicine",
  },
  {
    sector: "Cancer treatment",
    finding:
      "In the first-in-human CRISPR-Cas9 T-cell cancer trial, researchers detected chromosomal translocations in the manufactured cells, some persisting after infusion. The study found no evidence these translocations caused patient harm.",
    source: "PubMed Central (PMC); Nature",
  },
  {
    sector: "Livestock",
    finding:
      "CRISPR-edited pigs have been found with off-target mutations at other genomic locations; the animals were not shown to suffer an associated health problem. Separately, gene-edited hornless cattle were found to carry an undisclosed antibiotic-resistance marker from the editing process, surfacing only after regulatory review.",
    source: "Documented off-target case reports",
  },
  {
    sector: "India — regulatory gap",
    finding:
      "India has no dedicated gene-editing statute; oversight relies on advisory ICMR/DBT guidelines, not legally binding law. If an unintended genomic change occurred in an Indian trial today, there is currently no established compensation or liability pathway specific to CRISPR.",
    source: "ICMR/DBT guidelines; ART Act",
  },
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
          className="rounded-full border border-border-strong bg-white/5 px-3.5 py-1.5 font-mono text-xs text-muted"
        >
          {step}
        </span>
      ))}
    </div>
  );
}

export default function Home() {
  return (
    <div className="flex-1 veyra-hero-bg">
      <Header />

      <section className="pt-36 pb-10 px-4 sm:px-6">
        <Reveal className="mx-auto max-w-[1440px] grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
          <div>
            <span className="veyra-glass inline-flex items-center gap-2 px-3.5 py-1.5 font-mono text-[11px] tracking-[0.14em] text-muted uppercase mb-6 rounded-full!">
              <span className="veyra-pulse-dot h-1.5 w-1.5 rounded-full bg-secondary" />
              Genomic Intelligence · Research Prototype
            </span>
            <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-semibold leading-[1.02] text-foreground">
              Reasoning over the <mark>whole genomic locus</mark>, not a 20&nbsp;bp window.
            </h1>
            <p className="mt-6 text-lg text-muted max-w-lg leading-relaxed">
              VEYRA scores CRISPR guide-RNA candidates with a deterministic engine, layers
              interpretable AI reasoning on top, and renders the result as an interactive 3D
              structure — so every risk assessment is traceable, not a black-box number.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Link
                href="/analyze"
                className="veyra-glow-primary inline-flex items-center gap-2 rounded-full bg-linear-to-r from-primary to-secondary px-7 py-3.5 text-sm font-semibold text-primary-foreground hover:opacity-90 transition-opacity"
              >
                Run an analysis
                <ArrowRight size={16} />
              </Link>
              <a
                href="#pipeline"
                className="veyra-glass inline-flex items-center gap-2.5 px-6 py-3.5 text-sm text-foreground hover:border-primary/50 transition-colors rounded-full!"
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/10">
                  <Play size={11} fill="currentColor" />
                </span>
                See the pipeline
              </a>
            </div>
            <EngineStepsRow className="mt-9" />
          </div>

          <div className="relative">
            <div className="relative h-[420px] sm:h-[560px]">
              <div className="absolute inset-0 rounded-[2.5rem] bg-linear-to-br from-primary/25 via-transparent to-secondary/20 blur-2xl" aria-hidden="true" />
              <DnaHelixModel className="relative h-full w-full" />
            </div>

            <div className="veyra-glass absolute top-4 right-4 sm:right-8 inline-flex w-max items-center gap-2 px-3.5 py-2 rounded-full!">
              <span className="h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
              <span className="font-mono text-[10px] uppercase tracking-wide text-muted whitespace-nowrap">Drag to explore</span>
            </div>

            <div className="veyra-glass absolute bottom-4 left-4 sm:left-8 w-56 p-4">
              <p className="font-mono text-[10px] uppercase tracking-wide text-secondary mb-1.5">Deterministic core</p>
              <p className="text-xs text-muted leading-relaxed">
                Every score traces to PAM search, GC content, and seed-weighted mismatch analysis.
              </p>
            </div>
          </div>
        </Reveal>
      </section>

      <section className="pt-4 pb-14 px-4 sm:px-6">
        <Reveal className="mx-auto max-w-6xl">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {READOUTS.map((r) => (
              <div key={r.label} className="veyra-glass p-6">
                <div className="veyra-readout font-display text-3xl font-bold text-foreground tracking-tight">{r.num}</div>
                <div className="mt-2 font-mono text-[11px] tracking-wide uppercase text-muted leading-relaxed">
                  {r.label}
                </div>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      <div className="border-y border-border bg-white/[0.02] py-4 overflow-hidden" aria-hidden="true">
        <div className="veyra-marquee-track flex gap-12 w-max">
          {[...MARQUEE_ITEMS, ...MARQUEE_ITEMS].map((item, i) => (
            <span key={i} className="font-mono text-xs tracking-[0.16em] uppercase text-muted whitespace-nowrap">
              {item}
            </span>
          ))}
        </div>
      </div>

      <section id="pipeline" className="py-24 px-4 sm:px-6">
        <Reveal className="mx-auto max-w-2xl">
          <h2 className="font-display text-2xl sm:text-3xl font-semibold text-foreground mb-3 text-center">The pipeline</h2>
          <p className="text-sm text-muted text-center mb-10">
            Every step below is real — click a dot or let it play through.
          </p>
          <PipelineDemo />
        </Reveal>
      </section>

      <section id="features" className="py-24 px-4 sm:px-6">
        <Reveal className="mx-auto max-w-6xl">
          <h2 className="font-display text-2xl sm:text-3xl font-semibold text-foreground mb-10">Approach</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            {FEATURES.map((f) => (
              <div key={f.title} className="veyra-glass p-7">
                <h3 className="font-display text-foreground font-medium mb-2.5">{f.title}</h3>
                <p className="text-sm text-muted leading-relaxed">{f.body}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      <section id="stakes" className="py-24 px-4 sm:px-6">
        <Reveal className="mx-auto max-w-6xl">
          <h2 className="font-display text-2xl sm:text-3xl font-semibold text-foreground mb-3">Why off-target evidence matters</h2>
          <p className="text-sm text-muted max-w-2xl mb-10 leading-relaxed">
            Off-target risk isn&apos;t hypothetical — it&apos;s been documented in real published trials, and
            India currently has no dedicated gene-editing statute to fall back on. This is cited, published
            evidence, distinct from VEYRA&apos;s own illustrative research-prototype scores below.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {REAL_WORLD_CASES.map((c) => (
              <div key={c.sector} className="veyra-glass p-6">
                <p className="font-mono text-[10px] uppercase tracking-wide text-secondary mb-2">{c.sector}</p>
                <p className="text-sm text-muted leading-relaxed">{c.finding}</p>
                <p className="mt-3 font-mono text-[10px] uppercase tracking-wide text-muted/70">Source: {c.source}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      <section className="py-28 px-4 sm:px-6 text-center">
        <Reveal className="mx-auto max-w-2xl flex flex-col items-center">
          <h2 className="font-display text-3xl sm:text-4xl font-semibold text-foreground leading-tight">
            Paste a sequence. See the whole locus reason back.
          </h2>
          <p className="mt-5 text-muted leading-relaxed">
            Deterministic scoring, AI-explained risk, and an interactive 3D structure —
            one pipeline, fully traceable.
          </p>
          <Link
            href="/analyze"
            className="veyra-glow-primary mt-8 inline-flex items-center gap-2 rounded-full bg-linear-to-r from-primary to-secondary px-7 py-3.5 text-sm font-semibold text-primary-foreground hover:opacity-90 transition-opacity"
          >
            Run an analysis
            <ArrowRight size={16} />
          </Link>
          <EngineStepsRow className="mt-10 justify-center" />
        </Reveal>
      </section>

      <footer className="border-t border-border py-10 px-4 sm:px-6">
        <div className="mx-auto max-w-6xl flex flex-col sm:flex-row justify-between gap-4 text-xs text-muted font-mono">
          <span>VEYRA — Genomic Intelligence</span>
          <span>Research prototype. Not for clinical or diagnostic use.</span>
        </div>
      </footer>
    </div>
  );
}
