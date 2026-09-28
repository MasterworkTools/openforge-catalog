/** @type {import('next').NextConfig} */

// The one version there is. `package.json` is where npm already keeps
// it, so anything else is a copy that can disagree — and the page
// header was exactly that copy, kept by hand, until this.
//
// Baked in at build time rather than read at runtime: this is a static
// export, so there is no server to ask, and the built site is a fixed
// set of files that were produced from a particular version. That is
// also what makes it trustworthy — the number on the page cannot drift
// from the bundle it was built with, because it *is* the bundle.
const { version } = require('./package.json');

const nextConfig = {
  output: process.env.BACKEND_API ? undefined : "export",
  trailingSlash: true,
  env: {
    NEXT_PUBLIC_BASE_GENERATOR_URL: process.env.NEXT_PUBLIC_BASE_GENERATOR_URL || 'http://localhost:8000',
    NEXT_PUBLIC_APP_VERSION: version,
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
