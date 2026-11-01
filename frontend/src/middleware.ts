import { NextResponse, type NextRequest } from "next/server";

// Private deployment (D-69). While SITE_GATE_TOKEN is set, the backend answers 404 to anything without the matching header, and this is
// the only place that adds it: it runs on the server, so the token never reaches the browser and a stranger who finds the API's own
// address cannot get past it. Empty, which is the default and what local development uses, changes nothing.
const GATE = process.env.SITE_GATE_TOKEN ?? "";

export function middleware(req: NextRequest) {
  if (!GATE) return NextResponse.next();
  const headers = new Headers(req.headers);
  headers.set("x-site-gate", GATE);
  return NextResponse.next({ request: { headers } });
}

// Only the proxied API calls need the header; the pages are protected by the host while the deployment is private (PUBLIC_LAUNCH.md).
export const config = { matcher: "/api/:path*" };
