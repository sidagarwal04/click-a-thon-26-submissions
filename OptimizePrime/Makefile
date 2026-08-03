# Makefile — the one place that knows how to build, test and lint this repo.
# CI runs these same targets, so "works on my machine" and "passes CI" cannot drift.

BINARY      := sonyliv
CMD_PKG     := ./cmd/sonyliv
BIN_DIR     := bin
COVER_FILE  := coverage.out

VERSION     := $(shell git describe --tags --always --dirty 2>/dev/null || echo dev)
LDFLAGS     := -s -w -X main.version=$(VERSION)

GO          ?= go
GOFLAGS     ?=
ARGS        ?=

# The exact golangci-lint this repo expects — the same pin as devbox.json.
# .golangci.yml is v2 schema; a v1 binary rejects it, and an unpinned v2 can
# drift from CI. lint refuses to run anything else rather than silently using
# whatever happens to be on PATH.
GOLANGCI_LINT_VERSION := 2.12.2

export CGO_ENABLED ?= 0

.DEFAULT_GOAL := help

## help: list the targets
.PHONY: help
help:
	@grep -hE '^## ' $(MAKEFILE_LIST) | sed 's/^## /  /' | awk -F': ' '{printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

## build: compile the CLI into ./bin
.PHONY: build
build:
	$(GO) build $(GOFLAGS) -trimpath -ldflags '$(LDFLAGS)' -o $(BIN_DIR)/$(BINARY) $(CMD_PKG)

## run: build and run — make run ARGS="verify -target cloud"
.PHONY: run
run: build
	./$(BIN_DIR)/$(BINARY) $(ARGS)

## test: unit tests with the race detector
.PHONY: test
test:
	CGO_ENABLED=1 $(GO) test -race -count=1 ./...

## test-short: unit tests without the race detector (faster inner loop)
.PHONY: test-short
test-short:
	$(GO) test -count=1 ./...

## cover: test with coverage and print the per-function summary
.PHONY: cover
cover:
	CGO_ENABLED=1 $(GO) test -race -count=1 -coverprofile=$(COVER_FILE) -covermode=atomic ./...
	$(GO) tool cover -func=$(COVER_FILE) | tail -20

## cover-html: open the coverage report in a browser
.PHONY: cover-html
cover-html: cover
	$(GO) tool cover -html=$(COVER_FILE)

# lint-toolcheck: fail LOUDLY if the golangci-lint on PATH is not the pinned
# version. A global v1.x against our v2 config, or a drifted v2, must stop the
# build with instructions — not lint with whatever was installed last.
.PHONY: lint-toolcheck
lint-toolcheck:
	@command -v golangci-lint >/dev/null 2>&1 || { \
		echo "ERROR: golangci-lint not found on PATH."; \
		echo "  This repo pins golangci-lint $(GOLANGCI_LINT_VERSION) via devbox.json."; \
		echo "  Run 'direnv allow' (or 'devbox shell') to get the pinned toolchain."; \
		exit 1; }
	@golangci-lint version 2>/dev/null | head -1 | grep -qF "$(GOLANGCI_LINT_VERSION)" || { \
		echo "ERROR: wrong golangci-lint on PATH:"; \
		echo "  found:  $$(golangci-lint version 2>/dev/null | head -1)"; \
		echo "  wanted: golangci-lint $(GOLANGCI_LINT_VERSION) (the devbox.json pin; .golangci.yml is v2 schema)"; \
		echo "  Run 'direnv allow' (or 'devbox shell') so the pinned binary shadows the global one."; \
		exit 1; }

## lint: golangci-lint over everything (refuses to run an unpinned binary)
.PHONY: lint
lint: lint-toolcheck
	golangci-lint run ./...

## lint-fix: golangci-lint with autofix — hooks FIX, they do not just flag
.PHONY: lint-fix
lint-fix: lint-toolcheck
	golangci-lint run --fix ./...

## fmt: gofmt + import grouping
.PHONY: fmt
fmt:
	$(GO) fmt ./...
	@command -v goimports >/dev/null 2>&1 && goimports -w -local github.com/d-cryptic/clickathon . || echo "goimports not found (devbox shell provides it)"

## vet: go vet
.PHONY: vet
vet:
	$(GO) vet ./...

## tidy: sync go.mod/go.sum and fail if that produced a diff
.PHONY: tidy
tidy:
	$(GO) mod tidy
	@git diff --exit-code go.mod go.sum || { echo "go.mod/go.sum are stale — commit the tidy result"; exit 1; }

## verify: run the CLI's verify against the cloud service
.PHONY: verify
verify: build
	./$(BIN_DIR)/$(BINARY) verify -target cloud

## stack-up: start ClickHouse + ClickStack (the oss profile)
.PHONY: stack-up
stack-up:
	docker compose --profile oss up -d
	@echo "waiting for ClickStack API ..."
	@until curl -sf -o /dev/null http://localhost:8000/health; do sleep 2; done
	@echo "ClickHouse :8123  ·  HyperDX UI :8080  ·  OTLP :4317/:4318"

## stack-down: stop both containers (keeps volumes)
.PHONY: stack-down
stack-down:
	docker compose --profile oss down

## clickstack: self-hosted — bootstrap the team, then register our sources
.PHONY: clickstack
clickstack:
	tools/clickstack-bootstrap.sh
	tools/clickstack-sources.sh

## clickstack-cloud: hosted HyperDX — sources, dashboard and saved searches
.PHONY: clickstack-cloud
clickstack-cloud:
	tools/clickstack-cloud.sh

## model: rebuild intervals + deltas + views, then reconcile (TARGET=cloud for Cloud)
.PHONY: model
model:
	tools/build-model.sh

## reconcile: THE GATE — recompute from ev_raw and compare (TARGET=cloud for Cloud)
.PHONY: reconcile
reconcile:
	tools/reconcile.sh

## publish: ONE incremental publication batch — DB=name (ADR 0013). LOOP=60 to run continuously
.PHONY: publish
publish:
	@test -n "$(DB)" || { echo "usage: make publish DB=<database> [LOOP=60]"; exit 2; }
	tools/publish.sh --database $(DB) $(if $(LOOP),--loop $(LOOP),)

## publish-test: prove the aggregates move without a rebuild; writes evidence/publish.txt
.PHONY: publish-test
publish-test:
	tools/publish-test.sh

## sql-local: apply sql/*.sql to the local container
.PHONY: sql-local
sql-local:
	tools/apply-sql.sh

## sql-cloud: apply sql/*.sql to the graded Cloud service
.PHONY: sql-cloud
sql-cloud:
	TARGET=cloud tools/apply-sql.sh

## hooks: point git at .githooks (fixing pre-commit hook)
.PHONY: hooks
hooks:
	git config core.hooksPath .githooks
	@chmod +x .githooks/*
	@echo "git hooks installed from .githooks/"

## ci: everything CI runs, in CI's order
.PHONY: ci
ci: tidy vet lint test build

## clean: remove build and coverage artifacts
.PHONY: clean
clean:
	rm -rf $(BIN_DIR) $(COVER_FILE)
