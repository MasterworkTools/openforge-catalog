/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.BACKEND_API ? undefined : "export",
  trailingSlash: true,
  env: {
    NEXT_PUBLIC_BASE_GENERATOR_URL: process.env.NEXT_PUBLIC_BASE_GENERATOR_URL || 'http://localhost:8000',
  },
}

if (process.env.BACKEND_API) {
  nextConfig.rewrites = async () => {
    return [
      {
        source: '/api/:path*',
        destination:
          process.env.NODE_ENV === 'development'
            ? 'http://127.0.0.1:5328/api/:path*'
            : '/api/',
      },
    ]
  }
}

module.exports = nextConfig
