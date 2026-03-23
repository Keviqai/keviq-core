import type { NextConfig } from 'next';

// Docker: api-gateway:8000 (service name). Local dev: set API_GATEWAY_URL=http://localhost:8080
const API_GATEWAY = process.env.API_GATEWAY_URL ?? 'http://api-gateway:8000';

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      { source: '/v1/:path*', destination: `${API_GATEWAY}/v1/:path*` },
    ];
  },
  transpilePackages: [
    '@keviq/domain-types',
    '@keviq/api-client',
    '@keviq/server-state',
    '@keviq/live-state',
    '@keviq/ui-state',
    '@keviq/routing',
    '@keviq/permissions',
  ],
};

export default nextConfig;
