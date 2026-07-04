import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // Default 10MB: body-ul proxied e trunchiat silentios peste limita si
    // FastAPI nu mai gaseste campul multipart "file" (422). Specurile .docx
    // cu imagini depasesc usor 10MB.
    proxyClientMaxBodySize: "25mb",
  },
};

export default nextConfig;
