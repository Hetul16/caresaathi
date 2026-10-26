import type { NextConfig } from "next";

// The browser talks to /api/* on the same origin; Next forwards it to the FastAPI backend. That keeps the
// HttpOnly refresh cookie first-party and avoids CORS in the browser.
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
  },
};

export default nextConfig;
