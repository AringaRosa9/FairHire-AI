import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1"],
  transpilePackages: ["@fairhire/ui", "@fairhire/api-client"],
  typedRoutes: true,
};

export default nextConfig;
