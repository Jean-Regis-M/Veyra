/**
 * Client for VEYRA's Python backend (veyra/backend, FastAPI on :8000) —
 * the real deterministic scoring engine (published on-target efficiency
 * models: Rule Set 3 / Doench 2014, with full fallback-chain reporting).
 * Distinct from src/lib/genomic-engine, which is the client-side heuristic
 * used for instant candidate discovery. Never fabricates a score: every
 * call either returns the backend's real result or a typed failure the
 * UI must show as "unavailable," never a fallback number of our own.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_VEYRA_BACKEND_URL ?? "http://localhost:8000";

export interface OnTargetFallbackStep {
  model: string;
  status: string;
  reason: string;
}

export interface OnTargetScoreResult {
  modelUsed: string;
  modelSource: string;
  selectionStatus: string;
  fallbackUsed: boolean;
  fallbackChain: OnTargetFallbackStep[];
  score: number;
  outputScale: string;
  confidenceFlag: string;
}

export interface CfdScoredOffTarget {
  protospacer: string;
  pam: string;
  cfdScore: number;
}

export interface CfdScoreResult {
  scored: CfdScoredOffTarget[];
  meanCfd: number | null;
  maxCfd: number | null;
}

export type BackendCallResult<T> = { ok: true; data: T } | { ok: false; error: string };

async function withTimeout<T>(fn: (signal: AbortSignal) => Promise<T>, ms: number): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fn(controller.signal);
  } finally {
    clearTimeout(timer);
  }
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await withTimeout(
      (signal) => fetch(`${BACKEND_URL}/health`, { signal }),
      2500
    );
    return res.ok;
  } catch {
    return false;
  }
}

/** Build the exact 30 nt context window (4 nt upstream + 20 nt spacer + 3 nt
 * PAM + 3 nt downstream) the backend's on-target model requires, searching
 * the correct strand of the raw input for the candidate's own sequence
 * rather than trusting any position field's coordinate convention. Returns
 * null when the candidate sits too close to an input edge to have enough
 * flanking sequence — a real scope limit, not an error to hide. */
export function buildOnTargetContext(
  rawInput: string,
  candidate: { sequence: string; pam: string; strand: "+" | "-" }
): string | null {
  const normalized = rawInput.trim().toUpperCase().replace(/\s+/g, "");
  const strandSeq = candidate.strand === "+" ? normalized : reverseComplement(normalized);
  const needle = candidate.sequence + candidate.pam;
  const idx = strandSeq.indexOf(needle);
  if (idx === -1) return null;

  const start = idx - 4;
  const end = idx + candidate.sequence.length + candidate.pam.length + 3;
  if (start < 0 || end > strandSeq.length) return null;
  return strandSeq.slice(start, end);
}

function reverseComplement(seq: string): string {
  const map: Record<string, string> = { A: "T", T: "A", G: "C", C: "G" };
  return seq
    .split("")
    .reverse()
    .map((b) => map[b] ?? b)
    .join("");
}

export async function scoreOnTarget(contextSequence: string): Promise<BackendCallResult<OnTargetScoreResult>> {
  try {
    const res = await withTimeout(
      (signal) =>
        fetch(`${BACKEND_URL}/score/ontarget`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ context_sequence: contextSequence, model: "auto" }),
          signal,
        }),
      8000
    );

    const body = await res.json();
    if (!res.ok) {
      const detail = body?.detail?.errors?.[0] ?? body?.detail ?? `HTTP ${res.status}`;
      return { ok: false, error: String(detail) };
    }

    const s = body.summary ?? {};
    const modelUsed: string = s.model_used ?? "unknown";
    return {
      ok: true,
      data: {
        modelUsed,
        modelSource: s.model_source ?? "",
        selectionStatus: s.selection_status ?? "",
        fallbackUsed: Boolean(s.fallback_used),
        fallbackChain: Array.isArray(s.fallback_chain) ? s.fallback_chain : [],
        score: typeof s.ontarget_score === "number" ? s.ontarget_score : s[`ontarget_score_${modelUsed}`],
        outputScale: s.output_scale ?? "0-1",
        confidenceFlag: s.confidence_flag ?? "",
      },
    };
  } catch (e) {
    const message = e instanceof Error && e.name === "AbortError" ? "Backend timed out" : "Backend unreachable";
    return { ok: false, error: message };
  }
}

/** Score real off-target hits (found by the client-side scan within the
 * input sequence) with the backend's CFD algorithm — never a client-side
 * approximation. Candidates without a PAM (window ran off the end of the
 * input) are skipped, since CFD scoring requires one. */
export async function scoreOffTargetsCFD(
  spacerSequence: string,
  candidates: { protospacer: string; pam: string }[]
): Promise<BackendCallResult<CfdScoreResult>> {
  if (candidates.length === 0) {
    return { ok: true, data: { scored: [], meanCfd: null, maxCfd: null } };
  }
  try {
    const res = await withTimeout(
      (signal) =>
        fetch(`${BACKEND_URL}/offtarget/score`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ spacer_sequence: spacerSequence, candidates }),
          signal,
        }),
      8000
    );

    const body = await res.json();
    if (!res.ok) {
      const detail = body?.detail?.errors?.[0] ?? body?.detail ?? `HTTP ${res.status}`;
      return { ok: false, error: String(detail) };
    }

    const rows = Array.isArray(body.rows) ? body.rows : [];
    return {
      ok: true,
      data: {
        scored: rows.map((r: { protospacer: string; pam: string; cfd_score: number }) => ({
          protospacer: r.protospacer,
          pam: r.pam,
          cfdScore: r.cfd_score,
        })),
        meanCfd: body.summary?.mean_cfd ?? null,
        maxCfd: body.summary?.max_cfd ?? null,
      },
    };
  } catch (e) {
    const message = e instanceof Error && e.name === "AbortError" ? "Backend timed out" : "Backend unreachable";
    return { ok: false, error: message };
  }
}
