import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  output: "standalone", // Required for Docker deployment
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "cdn.simpleicons.org",
      },
    ],
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/:path*`,
      },
      {
        // Proxy Twilio/Telnyx webhooks to backend
        source: "/webhooks/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/webhooks/:path*`,
      },
      {
        // Proxy WebSocket connections to backend
        source: "/ws/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/ws/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        // Allow embed pages to be iframed from any origin
        // The backend API validates allowed_domains per agent
        source: "/embed/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors *",
          },
          {
            key: "X-Frame-Options",
            value: "", // Clear X-Frame-Options (CSP frame-ancestors takes precedence)
          },
        ],
      },
    ];
  },
};

export default nextConfig;
