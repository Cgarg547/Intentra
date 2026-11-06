import type { NextConfig } from "next";

const localApiProxy = "http://127.0.0.1:8000";
const apiProxyTarget = process.env.INTENTRA_API_PROXY_TARGET
  ?? (process.env.VERCEL ? undefined : localApiProxy);

if (!apiProxyTarget) {
  throw new Error("INTENTRA_API_PROXY_TARGET is required for Vercel builds; it must point to the HTTPS API deployment.");
}

const nextConfig: NextConfig = {
  distDir: process.env.INTENTRA_NEXT_DIST_DIR ?? ".next",
  devIndicators: false,
  cacheComponents: true,
  partialPrefetching: true,
  experimental: {
    // Ollama permits a 300s deadline; allow time to persist and return its result.
    proxyTimeout: 330_000,
  },

  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget.replace(/\/$/, "")}/api/:path*`,
      },
    ];
  },

  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
