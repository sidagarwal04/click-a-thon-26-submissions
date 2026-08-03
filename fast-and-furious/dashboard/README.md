# dashboard

Next.js 16 App Router UI for `sonyliv-mock`. Two routes:

| route | purpose |
|---|---|
| `/` | load simulator — viewer count, content, pace; live ingest telemetry |
| `/manual` | event stepper — drive one session by hand, watch derived state |

## Architecture

**Static export served by Go.** `next build` emits `./out`, which is copied into
`ingest/internal/mock/web/` and embedded with `go:embed`. The Go binary serves it,
so a deploy is one artifact: no second Node process, no reverse proxy, and the API
is same-origin.

Consequences that shape the code — the full list of what `output: 'export'`
forbids is in `node_modules/next/dist/docs/01-app/02-guides/static-exports.md`:

- **No rewrites**, so `/api` cannot be proxied through `next.config`. The API base
  is `NEXT_PUBLIC_API_BASE` instead: set in `.env.development`, empty in
  production. That cross-origin dev hop is why the Go server takes
  `--cors-origin`.
- **No Route Handlers or Server Actions.** The Go service is the API.
- Pages are Client Components fetching through SWR, which is the pattern the
  static-export guide recommends.

**No `next/font`.** Geist would need network access at build time and adds ~100KB
to an export a Go binary ships. The system mono/sans pairing in `globals.css` is
the right register for an operator's tool anyway.

**Dark only, deliberately.** This is read next to a terminal; the semantic colours
are tuned for one ground rather than compromised across two.

## Develop

Requires **Node >= 20.9** (Next 16). Run the Go service with CORS open to the dev
origin, then the dev server:

```bash
cd ../ingest && ./bin/sonyliv-mock --cors-origin http://localhost:3000
cd ../dashboard && npm run dev          # http://localhost:3000
```

## Ship a change

```bash
cd ../ingest && make web    # builds, then stages out/ into internal/mock/web/
make build                  # embeds it into the binary
```

The export is committed so `make build` needs no Node toolchain. Run `make web`
only after changing this directory.

## Verify

```bash
npm run lint       # eslint (Next 16 removed `next lint` and the eslint key in next.config)
npm run build      # also typechecks; fails the build on a type error
```
