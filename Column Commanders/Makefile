APP      := clickhouse-go-service
IMAGE    := $(APP)
TAG      := latest

.PHONY: build run test lint docker-build docker-run docker-down tidy

## build: compile the binary
build:
	CGO_ENABLED=0 go build -o bin/$(APP) ./...

## run: run the service locally (requires .env)
run:
	set -a && source .env && set +a && CGO_ENABLED=0 go run ./main.go

## test: run all tests
test:
	go test ./...

## lint: run go vet
lint:
	go vet ./...

## tidy: tidy and verify go modules
tidy:
	go mod tidy
	go mod verify

## docker-build: build the Docker image
docker-build:
	docker build -t $(IMAGE):$(TAG) .

## docker-run: run the service in Docker (uses .env file)
docker-run:
	docker run --rm \
		--env-file .env \
		-p 8080:8080 \
		--name $(APP) \
		$(IMAGE):$(TAG)

## langfuse-auth: print the base64 auth string for Langfuse OTLP headers
## Usage: LANGFUSE_PUBLIC_KEY=pk-lf-... LANGFUSE_SECRET_KEY=sk-lf-... make langfuse-auth
langfuse-auth:
	@echo "AUTH_STRING=$$(echo -n "$(LANGFUSE_PUBLIC_KEY):$(LANGFUSE_SECRET_KEY)" | base64)"
	@echo ""
	@echo "Add to .env:"
	@echo "  OTEL_EXPORTER_OTLP_ENDPOINT=https://cloud.langfuse.com/api/public/otel"
	@echo "  OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic $$(echo -n "$(LANGFUSE_PUBLIC_KEY):$(LANGFUSE_SECRET_KEY)" | base64),x-langfuse-ingestion-version=4"

## docker-down: stop and remove the container
docker-down:
	docker rm -f $(APP) || true

## create-tables: create ClickHouse tables and materialized views (requires env vars)
create-tables:
	set -a && source .env && set +a && ./scripts/create_tables.sh

## help: list available targets
help:
	@grep -E '^##' Makefile | sed 's/## //'
