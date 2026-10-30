import type { NextConfig } from "next";

// One origin for everything: this site at /, the product app (frontend/, basePath /app) behind it, the API at /api.
// Same origin keeps the sign-in cookie first-party and lets the hero hand the typed email to the sign-up page.
const app = process.env.CONCOURS_APP_URL || "http://127.0.0.1:3000";
const backend = process.env.CONCOURS_BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // A build next to a running dev server needs its own folder, or the two corrupt each other.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Compression would buffer the proxied live stream (/api/.../arena/stream).
  compress: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backend}/:path*` },
      { source: "/app", destination: `${app}/app` },
      { source: "/app/:path*", destination: `${app}/app/:path*` },
    ];
  },
  // Links from before the app moved under /app.
  async redirects() {
    return ["/login", "/signup", "/account", "/projects/:path*"].map((source) => ({
      source,
      destination: `/app${source}`,
      permanent: false,
    }));
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
