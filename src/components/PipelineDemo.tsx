"use client";

import { useEffect, useRef, useState } from "react";
import { FileText, Layers, Orbit, ScanLine, Sparkles, type LucideIcon } from "lucide-react";

interface Scene {
  icon: LucideIcon;
  label: string;
  detail: string;
  source: "Input" | "Engine" | "AI";
  /** Which rung (0-4) lights up for this scene, or null for none highlighted. */
  activeRung: number | null;
  color: string;
}

const SCENES: Scene[] = [
  { icon: FileText, label: "Sequence", detail: "Ingest raw DNA input", source: "Input", activeRung: null, color: "var(--muted)" },
  { icon: ScanLine, label: "Deterministic scoring", detail: "PAM search · GC · off-target · seed mismatch", source: "Engine", activeRung: 1, color: "var(--engine)" },
  { icon: Layers, label: "Genomic context", detail: "Ranked candidates, structured features", source: "Engine", activeRung: 3, color: "var(--engine)" },
  { icon: Sparkles, label: "AI reasoning", detail: "Explains risk in plain language", source: "AI", activeRung: 2, color: "var(--ai)" },
  { icon: Orbit, label: "Visualization", detail: "Interactive 3D helix, cut-site highlighting", source: "Input", activeRung: null, color: "var(--primary)" },
];

const SOURCE_STYLES: Record<Scene["source"], string> = {
  Input: "text-muted border-border-strong",
  Engine: "text-engine border-engine/40",
  AI: "text-ai border-ai/40",
};

const SCENE_MS = 3200;
const RUNG_X = [20, 65, 110, 155, 200];

/** A small two-strand ladder — the same "cut site" visual grammar as a
 * textbook CRISPR mechanism diagram, drawn from VEYRA's own tokens rather
 * than a static illustration. */
function MiniHelix({ activeRung, color }: { activeRung: number | null; color: string }) {
  return (
    <svg viewBox="0 0 220 68" className="w-full h-auto" aria-hidden="true">
      <path d="M 4 8 C 60 8, 60 60, 110 60 S 160 8, 216 8" stroke="var(--border-strong)" strokeWidth={2.5} fill="none" />
      <path d="M 4 60 C 60 60, 60 8, 110 8 S 160 60, 216 60" stroke="var(--border-strong)" strokeWidth={2.5} fill="none" />
      {RUNG_X.map((x, i) => {
        const active = i === activeRung;
        return (
          <line
            key={x}
            x1={x}
            y1={22}
            x2={x}
            y2={46}
            stroke={active ? color : "var(--border-strong)"}
            strokeWidth={active ? 4 : 3}
            strokeLinecap="round"
            opacity={active ? 1 : 0.6}
            style={active ? { filter: `drop-shadow(0 0 6px ${color})` } : undefined}
          />
        );
      })}
    </svg>
  );
}

/** An autoplaying, click-through walkthrough of VEYRA's real pipeline
 * steps — the "see the pipeline" demo. Pauses on hover/focus and never
 * autoplays under prefers-reduced-motion. */
export default function PipelineDemo() {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [autoplay, setAutoplay] = useState(true);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handler = (e: MediaQueryListEvent) => setAutoplay(!e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (!autoplay || paused) return;
    timerRef.current = setInterval(() => {
      setIndex((i) => (i + 1) % SCENES.length);
    }, SCENE_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [autoplay, paused]);

  const scene = SCENES[index];
  const Icon = scene.icon;

  return (
    <div
      className="veyra-glass p-8 sm:p-12"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div key={index} className="veyra-scene-in flex flex-col items-center text-center max-w-md mx-auto">
        <span
          className="flex h-12 w-12 items-center justify-center rounded-full border mb-5"
          style={{ borderColor: scene.color, color: scene.color }}
        >
          <Icon size={20} />
        </span>
        <MiniHelix activeRung={scene.activeRung} color={scene.color} />
        <span className={`mt-6 rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wide ${SOURCE_STYLES[scene.source]}`}>
          {scene.source}
        </span>
        <h3 className="mt-3 font-display text-lg font-medium text-foreground">{scene.label}</h3>
        <p className="mt-1.5 text-sm text-muted leading-relaxed">{scene.detail}</p>
      </div>

      <div className="mt-8 flex items-center justify-center gap-2">
        {SCENES.map((s, i) => (
          <button
            key={s.label}
            onClick={() => setIndex(i)}
            aria-label={`Show step: ${s.label}`}
            aria-current={i === index}
            className={`h-1.5 rounded-full transition-all cursor-pointer ${
              i === index ? "w-6 bg-primary" : "w-1.5 bg-border-strong hover:bg-muted"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
