import type { NextConfig } from "next";

// Backend/MIDEND run over plain HTTP on a separate host. A same-origin
// browser fetch to /api/proxy/* must reach them without the browser ever
// seeing the http:// origin (mixed-content) or a cross-origin request
// (CORS). A hand-rolled Route Handler proxy works but buffers the whole
// body inside a serverless function, hitting Vercel's ~4.5MB payload cap on
// file uploads. Rewriting at the platform/edge layer instead streams the
// request straight through to the destination — no Lambda invocation, no
// buffering, no size cap.
const BACKEND_URL = process.env.VEYRA_BACKEND_URL ?? "http://8.231.81.99:8000";
const MIDEND_URL = process.env.VEYRA_MIDEND_URL ?? "http://8.231.81.99:8080";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/proxy/backend/:path*", destination: `${BACKEND_URL}/:path*` },
      { source: "/api/proxy/midend/:path*", destination: `${MIDEND_URL}/:path*` },
    ];
  },
};

export default nextConfig;
