# GO — the Go toolchain and how we write Go here

> **Summary:** Go 1.26.4 pinned by [devbox.json](../devbox.json), entered automatically by
> [.envrc](../.envrc) via direnv, driven by the [Makefile](../Makefile). `make ci` runs exactly what
> GitHub Actions runs. Lint is golangci-lint **v2** (`.golangci.yml` is v2 schema — a v1 binary
> cannot read it). Layout is `cmd/` for binaries, `internal/` for everything else. Config comes from
> the SAME `.env` the bash tools in `tools/` read, so Go and shell can never disagree about which
> ClickHouse was loaded. Per ADR 0018 each target owns its variables — cloud reads
> `CH_HOST`+`CH_DATABASE`, local reads `CH_LOCAL_URL`+`CH_DATABASE_LOCAL`, both REQUIRED, no
> cross-target fallback. Every ClickHouse call takes a `context.Context` — enforced by the `noctx`
> linter, because a query with no deadline is how a demo hangs in front of judges.

## First-time setup

```bash
direnv allow          # once — .envrc pulls in devbox's toolchain and .env
make hooks            # point git at .githooks (the fixing pre-commit hook)
make ci               # tidy, vet, lint, test, build — should pass on a clean tree
```

Without direnv: `devbox shell` gives the same environment, then use `make` normally.

## Layout

| Path | Holds |
|---|---|
| `cmd/<name>/` | one directory per binary; `main` packages only, no logic worth testing |
| `internal/config/` | `.env` → typed settings. Owns host normalization |
| `internal/chdb/` | ClickHouse connection + query helpers |

`internal/` is deliberate: nothing here is a public API, and the compiler enforcing that is free.

## Make targets

`make help` lists them. The ones that matter: `build`, `test` (race), `cover`, `lint`, `lint-fix`,
`tidy`, `verify` (runs the CLI against Cloud), `ci`, `hooks`.

## Conventions

- **Errors wrap with `%w` and name the operation and the input**: `fmt.Errorf("query tables in %q:
  %w", database, err)`. `errorlint` catches comparisons that should be `errors.Is`.
- **Never return a bare `err` from a boundary.** If the caller cannot tell which of three ClickHouse
  calls failed, the error is not finished.
- **Context everywhere.** Every exported function that does I/O takes `ctx` as its first argument.
- **No naked `os.Getenv` outside `internal/config`.** One place reads the environment; everywhere
  else takes typed config. This is what stops Go and `tools/ch` drifting apart.
- **One target, one database
  ([ADR 0018](adr/0018-one-target-one-database-no-cross-target-fallback.md)).** `TargetCloud`
  requires `CH_DATABASE`; `TargetLocal` requires `CH_DATABASE_LOCAL` and never reads `CH_DATABASE`
  (that is the graded Cloud database — borrowing it is how local verification 404ed). Missing
  config is a `Load` error naming the variable, never a fallback to the server default.
- **Table-driven tests with `t.Parallel()`**, named cases, and a message that prints got *and* want.
- **Test the bug, not the function.** `TestParseHost` exists because a pasted `https://` host broke
  `tools/ch` in production-equivalent conditions; each case is a real failure mode.

## Why HTTP and not the native protocol

`internal/chdb` connects over HTTP on `CH_PORT` (8443 on Cloud), the same port `tools/ch` uses.
The native protocol on 9440 is faster for bulk transfer, but a second port in `.env` is a second
thing that can be wrong, and the graded path is dashboard-shaped queries, not bulk export. Revisit
if a benchmark shows the transfer, not the scan, is the bottleneck.

## Gotchas

- `CGO_ENABLED=0` by default (static binaries); `make test` flips it to 1 because `-race` needs cgo.
- `golangci-lint` on your PATH may be v1 (which cannot read `.golangci.yml`) or a drifted v2.
  `make lint` now refuses to run anything but the pinned 2.12.2 and fails loudly with instructions —
  `direnv allow` (or `devbox shell`) puts the pinned binary on PATH.
- `make tidy` **fails** if it produces a diff — that is the point; commit the tidy result.
