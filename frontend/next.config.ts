import type { NextConfig } from "next";

// The browser talks to /api/* on the same origin; Next forwards it to the FastAPI backend. That keeps the
// HttpOnly refresh cookie first-party and avoids CORS in the browser.
const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
const dev = process.env.NODE_ENV !== "production";

// Security headers (D-64). Kept as tight as the app actually needs:
//   img-src blob:  photo previews are object URLs (upload, label check, the chat preview)
//   'unsafe-inline' in style-src  the screens use style attributes throughout
//   'unsafe-eval' in development only  the dev server's hot reload needs it; a production build does not
// Microphone is allowed on this origin because Elder mode and the visit recorder need it; everything else is off.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "media-src 'self' blob:",
  "connect-src 'self'",
  "worker-src 'self' blob:",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  ...(dev ? [] : ["upgrade-insecure-requests"]),
].join("; ");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "Content-Security-Policy", value: csp },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Permissions-Policy", value: "camera=(self), microphone=(self), geolocation=(), payment=(), usb=()" },
        ...(dev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }]),
      ],
    }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
  },
};

export default nextConfig;
