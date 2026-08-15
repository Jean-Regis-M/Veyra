"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BACKEND_ENDPOINTS, BackendEndpoint } from "@/lib/backendEndpoints";
import { callBackendRaw, checkBackendHealth, BACKEND_BASE_URL } from "@/lib/backend";

const CATEGORIES = Array.from(new Set(BACKEND_ENDPOINTS.map((e) => e.category)));

export default function RawConsole() {
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [selected, setSelected] = useState<BackendEndpoint>(BACKEND_ENDPOINTS[0]);
  const [path, setPath] = useState(selected.path);
  const [bodyText, setBodyText] = useState(selected.exampleBody ? JSON.stringify(selected.exampleBody, null, 2) : "");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<{ status: number; json: unknown } | null>(null);
  const [callError, setCallError] = useState<string | null>(null);

  useEffect(() => {
    void checkBackendHealth().then(setBackendOnline);
  }, []);

  function select(ep: BackendEndpoint) {
    setSelected(ep);
    setPath(ep.path);
    setBodyText(ep.exampleBody ? JSON.stringify(ep.exampleBody, null, 2) : "");
    setResponse(null);
    setCallError(null);
  }

  async function run() {
    setLoading(true);
    setResponse(null);
    setCallError(null);
    let body: Record<string, unknown> | undefined;
    if (selected.method === "POST") {
      try {
        body = bodyText.trim() ? JSON.parse(bodyText) : {};
      } catch {
        setCallError("Request body is not valid JSON.");
        setLoading(false);
        return;
      }
    }
    const result = await callBackendRaw(selected.method, path, body);
    if (result.ok) {
      setResponse(result.data);
    } else {
      setCallError(result.error);
    }
    setLoading(false);
  }

  const grouped = useMemo(
    () => CATEGORIES.map((cat) => ({ cat, items: BACKEND_ENDPOINTS.filter((e) => e.category === cat) })),
    []
  );

  return (
    <div className="flex-1 pt-24 pb-20 veyra-hero-bg">
      <header className="fixed top-4 inset-x-0 z-50 px-4 sm:px-6">
        <div className="veyra-glass mx-auto max-w-4xl px-5 h-14 flex items-center justify-between rounded-full!">
          <Link href="/" className="flex items-center gap-2 font-display text-sm font-semibold tracking-wide text-foreground">
            <span
              className={`h-2 w-2 rounded-full ${backendOnline ? "veyra-pulse-dot bg-engine" : "bg-risk-high"}`}
            />
            VEYRA
          </Link>
          <span className="font-mono text-xs text-muted uppercase tracking-widest">Raw backend</span>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mb-8">
          <h1 className="font-display text-2xl font-semibold text-foreground">Raw backend access</h1>
          <p className="mt-2 text-sm text-muted max-w-2xl">
            Every deterministic VEYRA HTTP endpoint, called directly — no AI in the loop. This is the &ldquo;raw
            backend&rdquo; surface from the frontend/MIDEND plan; the AI-orchestration (MIDEND) layer is separate
            and not built yet. Responses shown here are exactly what {BACKEND_BASE_URL} returns.
          </p>
          {backendOnline === false && (
            <p className="mt-3 text-sm text-risk-high">Backend unreachable at {BACKEND_BASE_URL} — start it and reload.</p>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-2 space-y-4 max-h-[70vh] overflow-y-auto pr-1">
            {grouped.map(({ cat, items }) => (
              <div key={cat} className="veyra-glass p-4">
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted mb-2">{cat}</p>
                <div className="space-y-1">
                  {items.map((ep) => (
                    <button
                      key={ep.method + ep.path}
                      onClick={() => select(ep)}
                      className={`w-full text-left rounded-sm px-2.5 py-2 text-xs transition-colors ${
                        selected === ep ? "bg-white/10 text-foreground" : "text-muted hover:bg-white/5 hover:text-foreground"
                      }`}
                    >
                      <span
                        className={`font-mono mr-2 ${ep.method === "GET" ? "text-engine" : "text-ai"}`}
                      >
                        {ep.method}
                      </span>
                      <span className="font-mono">{ep.path}</span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="lg:col-span-3 space-y-4">
            <div className="veyra-glass p-5 space-y-4">
              <div className="flex items-center gap-2">
                <span className={`font-mono text-xs rounded-full border px-2 py-0.5 ${selected.method === "GET" ? "text-engine border-engine/40" : "text-ai border-ai/40"}`}>
                  {selected.method}
                </span>
                <input
                  value={path}
                  onChange={(e) => setPath(e.target.value)}
                  className="flex-1 rounded-sm border border-border bg-black/20 px-3 py-1.5 font-mono text-xs text-foreground focus:outline-none focus:border-primary/60"
                />
              </div>
              <p className="text-xs text-muted">{selected.description}</p>
              {selected.needsGenome && (
                <p className="text-[11px] font-mono text-risk-moderate">
                  Needs a registered reference genome — none is registered in this deployment by default, so this
                  will likely return a real &ldquo;not found&rdquo; error, not a fabricated result.
                </p>
              )}

              {selected.method === "POST" && (
                <textarea
                  value={bodyText}
                  onChange={(e) => setBodyText(e.target.value)}
                  rows={6}
                  className="w-full rounded-sm border border-border bg-black/20 p-3 font-mono text-xs text-foreground focus:outline-none focus:border-primary/60"
                />
              )}

              <button
                onClick={run}
                disabled={loading}
                className="rounded-full bg-linear-to-r from-primary to-secondary px-5 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {loading ? "Calling…" : "Run"}
              </button>
            </div>

            <div className="veyra-glass p-5 space-y-2">
              <p className="font-mono text-[10px] uppercase tracking-widest text-muted">Response</p>
              {callError && <p className="text-sm text-risk-high">{callError}</p>}
              {response && (
                <>
                  <span
                    className={`inline-block rounded-full border px-2 py-0.5 font-mono text-[11px] ${
                      response.status < 300
                        ? "text-risk-low border-risk-low/40"
                        : response.status < 500
                          ? "text-risk-moderate border-risk-moderate/40"
                          : "text-risk-high border-risk-high/40"
                    }`}
                  >
                    HTTP {response.status}
                  </span>
                  <pre className="mt-2 max-h-96 overflow-auto rounded-sm border border-border bg-black/30 p-3 font-mono text-[11px] text-foreground whitespace-pre-wrap break-words">
                    {JSON.stringify(response.json, null, 2)}
                  </pre>
                </>
              )}
              {!callError && !response && <p className="text-sm text-muted">Run a call to see the real response.</p>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
