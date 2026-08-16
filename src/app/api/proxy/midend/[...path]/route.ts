import { NextRequest } from "next/server";
import { proxyRequest } from "@/lib/serverProxy";

// Server-only var (no NEXT_PUBLIC_ prefix) — never shipped to the client bundle.
const TARGET = process.env.VEYRA_MIDEND_URL ?? "http://8.231.81.99:8080";

async function handle(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return proxyRequest(req, path, TARGET);
}

export const GET = handle;
export const POST = handle;
export const DELETE = handle;
