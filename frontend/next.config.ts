import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["*"],
  ...(process.env.LOCAL_NEXT_DIST ? { distDir: process.env.LOCAL_NEXT_DIST } : {}),
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
