import type { NextConfig } from "next";

// The browser calls the API at /api on the app's own origin, so the sign-in cookie is first-party. In development
// Next forwards /api to the backend; in production the reverse proxy (deploy/Caddyfile) does the same.
const backend = process.env.CONCOURS_BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // A second dev server (another port, another backend) needs its own build folder, or the two corrupt each other.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  output: "standalone",
  // Compression would buffer the proxied live stream (/api/.../arena/stream); Caddy compresses pages in production.
  compress: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
