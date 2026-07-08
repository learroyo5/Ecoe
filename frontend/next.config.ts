import type { NextConfig } from "next";

// Media (photos/PDF/audio/video) is fetched as a blob and rendered via
// object URLs (see components/media-preview.tsx, app/(app)/student/page.tsx),
// and the live timer connects over WebSocket to the same or a different
// origin/port depending on the deployment topology (see lib/ws.ts) — both
// need explicit CSP allowances or the app breaks.
const CSP_DIRECTIVES = [
  "default-src 'self'",
  // React's inline style={{...}} attributes (e.g. progress bars) require
  // 'unsafe-inline' for style-src without a nonce-based CSP setup.
  "style-src 'self' 'unsafe-inline'",
  "script-src 'self' 'unsafe-inline'",
  "img-src 'self' blob: data:",
  "media-src 'self' blob:",
  "frame-src 'self' blob:",
  "connect-src 'self' ws: wss:",
  "font-src 'self' data:",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.INTERNAL_API_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: CSP_DIRECTIVES },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
