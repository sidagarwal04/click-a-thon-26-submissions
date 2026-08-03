import type { NextConfig } from "next";

/*
  Static export, so `next build` emits plain HTML/CSS/JS into ./out and the Go
  binary serves it from an embed.FS. That keeps the deploy to ONE artifact: no
  second Node process on the box, no reverse proxy, and the existing deploy script
  needs no change.

  Consequences, all of which this app already lives within — the full list of
  unsupported features is in the bundled doc at
  node_modules/next/dist/docs/01-app/02-guides/static-exports.md:

  - No rewrites. The usual trick of proxying /api to the Go service through
    next.config is unavailable, and using it errors even under `next dev`. So the
    API base is an env var instead: empty in production (same origin, served by
    Go) and set to Go's address in .env.development. That cross-origin dev hop is
    why the Go server takes an explicit --cors-origin flag.
  - No Route Handlers, Server Actions, cookies, or Image Optimization. None are
    wanted: the Go service IS the API, and this is a tool with no images.
  - Every page is a Client Component fetching through SWR, which is the pattern
    the static-export guide recommends for client-side data.

  trailingSlash keeps the emitted layout at /manual/index.html rather than
  /manual.html, so Go's static file handler resolves a bare /manual with no
  special casing.
*/
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,

  // Served from a Go binary, not a CDN with an image pipeline.
  images: { unoptimized: true },

  // Fail the build on a type error rather than shipping one to the box.
  //
  // There is deliberately no `eslint` key: Next 16 removed it from NextConfig
  // (and removed `next lint`), so linting is its own step — `npm run lint`, which
  // runs eslint against eslint.config.mjs.
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
