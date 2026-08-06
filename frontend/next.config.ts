import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["*"],
  distDir: process.env.LOCAL_NEXT_DIST || (process.env.VERCEL || process.env.NODE_ENV === "development" ? ".next" : ".next-local-build"),
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
