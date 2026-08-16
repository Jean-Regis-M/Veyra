import { NextRequest, NextResponse } from "next/server";
import type { GuideCandidate } from "@/lib/genomic-engine";

interface ReasonRequestBody {
  sequence: string;
  candidates: GuideCandidate[];
}

interface CandidateNote {
  id: string;
  note: string;
}

interface ReasonResponse {
  summary: string;
  perCandidate: CandidateNote[];
  source: "ai" | "stub";
}

function buildPrompt(body: ReasonRequestBody): string {
  const top = body.candidates.slice(0, 5);
  const lines = top.map(
    (c) =>
      `- Candidate ID: ${c.id} | Protospacer: ${c.sequence} | PAM: ${c.pam} | Strand: ${c.strand} | GC Content: ${(c.gcContent * 100).toFixed(0)}% | Overall Score: ${c.overallScore}/100 | Risk Level: ${c.riskLevel} | Off-Target Hits: ${c.offTargets.length}`
  );
  return [
    "You are VEYRA's genomic intelligence co-pilot explaining CRISPR/Cas9 guide-RNA candidate scores computed by our deterministic algorithms.",
    "Rules:",
    "- Do NOT invent new scores, off-target counts, or clinical claims.",
    "- Only contextualize and interpret the deterministic numbers provided below.",
    "- Explain why the top-ranked candidate is preferred (e.g. balanced GC, high specificity, low off-target risk).",
    "- Be clear, concise, and professional. State that this is an illustrative research prototype, not medical or clinical advice.",
    "",
    `Target sequence length: ${body.sequence.length} bp`,
    "Top candidates evaluated:",
    ...lines,
    "",
    "Provide a structured analysis with an executive summary and brief bulleted evaluations for the top candidate guides.",
  ].join("\n");
}

function stubResponse(body: ReasonRequestBody): ReasonResponse {
  return {
    summary:
      "AI reasoning is not configured for this deployment (no API key set). Showing deterministic scores only — this is the integration point where the AI model explains the ranked candidates below.",
    perCandidate: body.candidates.slice(0, 5).map((c) => ({
      id: c.id,
      note: `Deterministic score ${c.overallScore}/100 (${c.riskLevel} risk), ${c.offTargets.length} off-target hit(s) found within the input sequence.`,
    })),
    source: "stub",
  };
}

export async function POST(req: NextRequest) {
  let body: ReasonRequestBody;
  try {
    body = (await req.json()) as ReasonRequestBody;
  } catch {
    return NextResponse.json({ error: "Expected { sequence, candidates }." }, { status: 400 });
  }

  if (!body?.sequence || !Array.isArray(body.candidates)) {
    return NextResponse.json({ error: "Expected { sequence, candidates }." }, { status: 400 });
  }

  // 1. Check for OpenAI-compatible / MIDEND AI configuration
  const midendKey = process.env.MIDEND_AI_API_KEY || process.env.OPENAI_API_KEY;
  const midendBaseUrl = process.env.MIDEND_AI_BASE_URL || process.env.OPENAI_BASE_URL || "https://api.llm7.io/v1";
  const midendModel = process.env.MIDEND_AI_MODEL || "default";

  if (midendKey) {
    try {
      const endpoint = `${midendBaseUrl.replace(/\/+$/, "")}/chat/completions`;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: `Bearer ${midendKey}`,
        },
        body: JSON.stringify({
          model: midendModel,
          messages: [
            {
              role: "system",
              content:
                "You are VEYRA's AI reasoning layer. Explain CRISPR guide-RNA candidate scores that were computed by deterministic algorithms. Do not invent scores or clinical claims. Only explain the evidence given. Be concise and structured.",
            },
            { role: "user", content: buildPrompt(body) },
          ],
          temperature: 0.2,
          max_tokens: 1024,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const text: string = data?.choices?.[0]?.message?.content ?? "";
        if (text) {
          return NextResponse.json({
            summary: text,
            perCandidate: [],
            source: "ai",
          } satisfies ReasonResponse);
        }
      }
    } catch {
      // Fall through to Anthropic or stub
    }
  }

  // 2. Check for Anthropic API configuration
  const anthropicKey = process.env.ANTHROPIC_API_KEY;
  if (anthropicKey) {
    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": anthropicKey,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify({
          model: "claude-sonnet-5",
          max_tokens: 1024,
          messages: [{ role: "user", content: buildPrompt(body) }],
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const text: string = data?.content?.[0]?.text ?? "";
        return NextResponse.json({
          summary: text,
          perCandidate: [],
          source: "ai",
        } satisfies ReasonResponse);
      }
    } catch {
      // Fall through to stub
    }
  }

  // 3. Fallback to deterministic stub response if no API keys succeed
  return NextResponse.json(stubResponse(body));
}
