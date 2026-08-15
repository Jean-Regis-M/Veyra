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
      `- id=${c.id} seq=${c.sequence} pam=${c.pam} strand=${c.strand} gc=${(c.gcContent * 100).toFixed(0)}% overallScore=${c.overallScore} riskLevel=${c.riskLevel} offTargets=${c.offTargets.length}`
  );
  return [
    "You are explaining CRISPR guide-RNA candidate scores that were already computed by a deterministic algorithm.",
    "Do not invent new scores or numbers. Only explain and contextualize the numbers given below.",
    "Be concise, plain-language, and note this is an illustrative research prototype, not clinical guidance.",
    "",
    `Input sequence length: ${body.sequence.length} bp`,
    "Top candidates:",
    ...lines,
    "",
    "Return a short overall summary, then one short note per candidate id explaining its risk level in plain language.",
  ].join("\n");
}

function stubResponse(body: ReasonRequestBody): ReasonResponse {
  return {
    summary:
      "AI reasoning is not configured for this deployment (no ANTHROPIC_API_KEY set). Showing deterministic scores only — this is the integration point where an LLM would explain the ranked candidates below.",
    perCandidate: body.candidates.slice(0, 5).map((c) => ({
      id: c.id,
      note: `Deterministic score ${c.overallScore}/100 (${c.riskLevel} risk), ${c.offTargets.length} off-target hit(s) found within the input sequence. Set ANTHROPIC_API_KEY to enable AI-generated explanations.`,
    })),
    source: "stub",
  };
}

export async function POST(req: NextRequest) {
  const body = (await req.json()) as ReasonRequestBody;

  if (!body?.sequence || !Array.isArray(body.candidates)) {
    return NextResponse.json({ error: "Expected { sequence, candidates }." }, { status: 400 });
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return NextResponse.json(stubResponse(body));
  }

  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: "claude-sonnet-5",
        max_tokens: 1024,
        messages: [{ role: "user", content: buildPrompt(body) }],
      }),
    });

    if (!res.ok) {
      return NextResponse.json(stubResponse(body));
    }

    const data = await res.json();
    const text: string = data?.content?.[0]?.text ?? "";

    return NextResponse.json({
      summary: text,
      perCandidate: [],
      source: "ai",
    } satisfies ReasonResponse);
  } catch {
    return NextResponse.json(stubResponse(body));
  }
}
