import { NextRequest } from "next/server";

/**
 * Server-side passthrough to a backend/MIDEND host. Runs on Vercel's servers,
 * not the browser, so it isn't subject to mixed-content blocking (HTTPS page
 * fetching a plain-HTTP API) or same-origin/CORS restrictions the way a
 * direct browser fetch to an http:// VPS would be. Forwards method, body
 * (streamed, so multipart uploads and JSON both pass through unmodified),
 * and content-type verbatim — never reshapes the request or response.
 */
export async function proxyRequest(req: NextRequest, path: string[], targetBase: string): Promise<Response> {
  const url = `${targetBase}/${path.join("/")}${req.nextUrl.search}`;

  const init: RequestInit & { duplex?: "half" } = {
    method: req.method,
    headers: req.headers.get("content-type") ? { "content-type": req.headers.get("content-type")! } : undefined,
  };
  if (req.method !== "GET" && req.method !== "HEAD" && req.method !== "DELETE") {
    init.body = req.body;
    init.duplex = "half";
  }

  try {
    const res = await fetch(url, init);
    const headers = new Headers();
    const contentType = res.headers.get("content-type");
    if (contentType) headers.set("content-type", contentType);
    return new Response(res.body, { status: res.status, headers });
  } catch {
    return Response.json({ error: "Upstream service unreachable" }, { status: 502 });
  }
}
