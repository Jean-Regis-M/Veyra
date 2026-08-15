/**
 * Deterministic CRISPR guide-RNA candidate generation and scoring.
 * Pure functions only — no randomness, no network/LLM calls. Same sequence
 * in always produces the same candidates/scores out.
 *
 * Scope and known limitations: docs/scientific-assumptions.md
 */

export type Nucleotide = "A" | "C" | "G" | "T";
export type Strand = "+" | "-";

export interface OffTargetHit {
  position: number;
  strand: Strand;
  mismatches: number;
  seedMismatches: number;
  sequence: string; // the off-target's own protospacer-length window
  pam: string | null; // 3 nt immediately following it, if the sequence extends that far
}

export interface GuideCandidate {
  id: string;
  sequence: string; // 20 nt protospacer
  pam: string; // 3 nt, NGG
  position: number; // 0-indexed start of protospacer in the input sequence
  strand: Strand;
  gcContent: number; // 0-1
  gcQuality: "low" | "optimal" | "high";
  offTargets: OffTargetHit[];
  specificityScore: number; // 0-100, higher = more specific (fewer/weaker off-targets)
  overallScore: number; // 0-100, combined ranking score
  riskLevel: "low" | "moderate" | "high";
}

export interface GenomicEngineResult {
  inputLength: number;
  candidates: GuideCandidate[];
  offTargetScope: "input-sequence-only";
}

const GUIDE_LENGTH = 20;
const SEED_LENGTH = 12; // PAM-proximal seed region, weighted more heavily on mismatch

function reverseComplement(seq: string): string {
  const map: Record<string, string> = { A: "T", T: "A", G: "C", C: "G" };
  return seq
    .split("")
    .reverse()
    .map((b) => map[b] ?? b)
    .join("");
}

export function validateSequence(raw: string): { sequence: string; error: string | null } {
  const sequence = raw.trim().toUpperCase().replace(/\s+/g, "");
  if (sequence.length === 0) {
    return { sequence: "", error: "Sequence is empty." };
  }
  if (!/^[ACGT]+$/.test(sequence)) {
    return { sequence, error: "Sequence must contain only A, C, G, T bases." };
  }
  if (sequence.length < GUIDE_LENGTH + 3) {
    return { sequence, error: `Sequence must be at least ${GUIDE_LENGTH + 3} bp to contain a guide + PAM.` };
  }
  return { sequence, error: null };
}

function gcContent(seq: string): number {
  const gc = seq.split("").filter((b) => b === "G" || b === "C").length;
  return gc / seq.length;
}

function gcQuality(gc: number): GuideCandidate["gcQuality"] {
  if (gc < 0.2 || gc > 0.8) return "low";
  if (gc < 0.4 || gc > 0.65) return "optimal";
  return "optimal";
}

/** Find NGG PAM sites on a strand and return the preceding 20 nt protospacers. */
function findCandidatesOnStrand(
  seq: string,
  strand: Strand
): Omit<GuideCandidate, "offTargets" | "specificityScore" | "overallScore" | "riskLevel">[] {
  const results: Omit<GuideCandidate, "offTargets" | "specificityScore" | "overallScore" | "riskLevel">[] = [];
  for (let i = 0; i <= seq.length - 3; i++) {
    const triplet = seq.slice(i, i + 3);
    if (triplet[1] !== "G" || triplet[2] !== "G") continue; // NGG
    const protospacerStart = i - GUIDE_LENGTH;
    if (protospacerStart < 0) continue;
    const protospacer = seq.slice(protospacerStart, i);
    const gc = gcContent(protospacer);
    results.push({
      id: `${strand}-${protospacerStart}`,
      sequence: protospacer,
      pam: triplet,
      position: strand === "+" ? protospacerStart : seq.length - i - 3,
      strand,
      gcContent: gc,
      gcQuality: gcQuality(gc),
    });
  }
  return results;
}

/** Mismatch-tolerant scan of a candidate protospacer against the full input sequence (both strands). */
function findOffTargets(
  candidate: string,
  fullSeqPlusStrand: string,
  fullSeqMinusStrand: string,
  selfPosition: number,
  selfStrand: Strand
): OffTargetHit[] {
  const hits: OffTargetHit[] = [];
  const maxMismatches = 4;

  for (const [strand, haystack] of [
    ["+", fullSeqPlusStrand],
    ["-", fullSeqMinusStrand],
  ] as [Strand, string][]) {
    for (let i = 0; i <= haystack.length - candidate.length; i++) {
      if (strand === selfStrand && i === selfPosition) continue; // skip self-match
      const window = haystack.slice(i, i + candidate.length);
      let mismatches = 0;
      let seedMismatches = 0;
      for (let j = 0; j < candidate.length; j++) {
        if (window[j] !== candidate[j]) {
          mismatches++;
          if (j >= candidate.length - SEED_LENGTH) seedMismatches++;
        }
      }
      if (mismatches > 0 && mismatches <= maxMismatches) {
        const pamEnd = i + candidate.length + 3;
        const pam = pamEnd <= haystack.length ? haystack.slice(i + candidate.length, pamEnd) : null;
        hits.push({ position: i, strand, mismatches, seedMismatches, sequence: window, pam });
      }
    }
  }
  return hits;
}

function specificityScore(offTargets: OffTargetHit[]): number {
  // Seed mismatches matter more than distal mismatches for Cas9 binding specificity.
  let penalty = 0;
  for (const hit of offTargets) {
    const seedWeight = hit.seedMismatches * 8;
    const distalWeight = (hit.mismatches - hit.seedMismatches) * 2;
    const closeness = Math.max(0, 5 - hit.mismatches); // fewer mismatches = closer match = bigger risk
    penalty += Math.max(seedWeight, distalWeight) + closeness * 3;
  }
  return Math.max(0, 100 - penalty);
}

function riskLevel(specificity: number): GuideCandidate["riskLevel"] {
  if (specificity >= 75) return "low";
  if (specificity >= 45) return "moderate";
  return "high";
}

export function analyzeSequence(rawSequence: string): GenomicEngineResult {
  const { sequence, error } = validateSequence(rawSequence);
  if (error) throw new Error(error);

  const plusStrand = sequence;
  const minusStrand = reverseComplement(sequence);

  const rawCandidates = [
    ...findCandidatesOnStrand(plusStrand, "+"),
    ...findCandidatesOnStrand(minusStrand, "-"),
  ];

  const candidates: GuideCandidate[] = rawCandidates.map((c) => {
    const offTargets = findOffTargets(c.sequence, plusStrand, minusStrand, c.position, c.strand);
    const specificity = specificityScore(offTargets);
    const gcPenalty = c.gcQuality === "low" ? 15 : 0;
    const overall = Math.round(Math.max(0, Math.min(100, specificity - gcPenalty)));
    return {
      ...c,
      offTargets,
      specificityScore: Math.round(specificity),
      overallScore: overall,
      riskLevel: riskLevel(overall),
    };
  });

  candidates.sort((a, b) => b.overallScore - a.overallScore);

  return {
    inputLength: sequence.length,
    candidates,
    offTargetScope: "input-sequence-only",
  };
}
