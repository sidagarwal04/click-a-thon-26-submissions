.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE      ?= docker compose
APP_SERVICE  ?= app
CH_DB        ?= $(shell grep -E "^CLICKHOUSE_DB=" .env 2>/dev/null | cut -d= -f2)
LANGFUSE_PORT ?= 3000
PY           ?= python3
VENV         ?= .venv

# The organiser's dataset package: base_context.md, data/, specs/. Reached
# through the gitignored `inputs` symlink so there is one path inside the repo
# and still only one copy on disk - spec 6 drops into the package and is visible
# here immediately. Create the link once: ln -s /path/to/Atlys inputs
# Override with ATLYS_PACKAGE=... if you keep the package somewhere else.
ATLYS_PACKAGE ?= inputs
BASE          ?= $(ATLYS_PACKAGE)/base_context.md
VENV_PY      := $(VENV)/bin/python
VENV_PIP     := $(VENV)/bin/pip

# clickhouse-client as a throwaway container, pointed at whatever .env says.
# There is no local ClickHouse service any more - the database is Cloud.
#
# NOTE: --entrypoint must not be `sh`. That image's /bin/sh is dash, which has
# no `read -s`, so a password prompt written in sh silently yields an empty
# string and the connection fails as "password is incorrect".
CH_CLIENT = docker run --rm -i --env-file .env \
	--entrypoint clickhouse-client clickhouse/clickhouse-server:latest \
	--host "$$CLICKHOUSE_HOST" --port 9440 --secure \
	--user "$$CLICKHOUSE_USER" --password "$$CLICKHOUSE_PASSWORD"

# Same client, but prompts for the password instead of reading .env.
CH_CLIENT_ASK = docker run --rm -it \
	--entrypoint clickhouse-client clickhouse/clickhouse-server:latest \
	--host "$(CH_HOST)" --port 9440 --secure --user "$(CH_USER)" --ask-password

CH_HOST ?= $(shell grep -E '^CLICKHOUSE_HOST=' .env 2>/dev/null | cut -d= -f2)
CH_USER ?= $(shell grep -E '^CLICKHOUSE_USER=' .env 2>/dev/null | cut -d= -f2)

.PHONY: help
help: ## Show this help
	@echo "atlys-prism-ch - available targets:"
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- environment --------------------------------------------------------------

.PHONY: env
env: ## Create .env from .env.example (never overwrites an existing .env)
	@if [ -f .env ]; then \
		echo ".env already exists - leaving it alone"; \
	else \
		cp .env.example .env && echo "wrote .env"; \
	fi

.PHONY: venv
venv: $(VENV_PY) ## Create a local virtualenv

$(VENV_PY):
	$(PY) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip

.PHONY: install
install: venv ## Install runtime dependencies into the virtualenv
	$(VENV_PIP) install -r requirements.txt

.PHONY: install-dev
install-dev: venv ## Install runtime + dev dependencies
	$(VENV_PIP) install -r requirements-dev.txt

.PHONY: lock
lock: install ## Freeze the resolved dependency set into requirements.lock
	$(VENV_PIP) freeze > requirements.lock
	@echo "wrote requirements.lock"

# --- stack lifecycle ----------------------------------------------------------

.PHONY: build
build: ## Build the application image
	$(COMPOSE) build

.PHONY: up
up: ## Start the app in the background
	$(COMPOSE) up -d --build
	@$(MAKE) --no-print-directory wait

.PHONY: up-obs
up-obs: ## Start the stack including the Langfuse tracing services
	COMPOSE_PROFILES=langfuse $(COMPOSE) up -d --build
	@$(MAKE) --no-print-directory wait
	@echo "Langfuse starting at http://localhost:$(LANGFUSE_PORT) (first boot runs migrations - give it a minute)"

.PHONY: wait
wait: ## Block until the configured ClickHouse answers (local or Cloud)
	@$(COMPOSE) run --rm -T app health >/dev/null 2>&1 \
		&& echo "ClickHouse reachable" \
		|| { echo "ClickHouse unreachable - check CLICKHOUSE_HOST/PORT/SECURE in .env" >&2; exit 1; }

.PHONY: down
down: ## Stop the whole stack, every profile included (data volumes are kept)
	COMPOSE_PROFILES=langfuse $(COMPOSE) down

.PHONY: restart
restart: down up ## Recreate the stack

.PHONY: ps
ps: ## Show container status
	$(COMPOSE) ps

.PHONY: logs
logs: ## Tail logs from every service
	$(COMPOSE) logs -f --tail=100

.PHONY: logs-app
logs-app: ## Tail application logs
	$(COMPOSE) logs -f --tail=100 $(APP_SERVICE)

# --- database -----------------------------------------------------------------

.PHONY: bootstrap
bootstrap: ## Apply the demo schema via the app
	$(COMPOSE) run --rm $(APP_SERVICE) bootstrap

.PHONY: client
client: ## Interactive clickhouse-client against the configured ClickHouse
	@set -a; . ./.env; set +a; $(CH_CLIENT) --database "$$CLICKHOUSE_DB"

.PHONY: tables
tables: ## List tables in the working database
	@set -a; . ./.env; set +a; $(CH_CLIENT) --query "SELECT name, engine, sorting_key, total_rows \
		FROM system.tables WHERE database = '"'"'$$CLICKHOUSE_DB'"'"' ORDER BY name FORMAT PrettyCompact"


# --- agents -------------------------------------------------------------------

.PHONY: instrument
instrument: ## Run the Instrumentation Agent: make instrument SPEC=path/to/spec_dir [SAMPLE_PCT=15]
	@test -n "$(SPEC)" || { echo "usage: make instrument SPEC=path/to/spec_dir" >&2; exit 1; }
	$(VENV_PY) -m prism_ch instrument "$(SPEC)" --sample-pct "$(or $(SAMPLE_PCT),15)"

.PHONY: instrument-dry
instrument-dry: ## Same, but validate the DDL without creating real tables
	@test -n "$(SPEC)" || { echo "usage: make instrument-dry SPEC=path/to/spec_dir" >&2; exit 1; }
	$(VENV_PY) -m prism_ch instrument "$(SPEC)" --dry-run

# --- application --------------------------------------------------------------

.PHONY: run
run: ## Run the service on the host against the configured ClickHouse
	$(VENV_PY) -m prism_ch serve

.PHONY: info
info: ## Print cluster info as seen by the app (Cloud has no named cluster)
	$(COMPOSE) run --rm $(APP_SERVICE) info

.PHONY: health
health: ## Curl the app health endpoint
	@curl -fsS http://localhost:$${APP_PORT:-8000}/ready | $(PY) -m json.tool

.PHONY: shell
shell: ## Open a shell inside the app container
	$(COMPOSE) exec $(APP_SERVICE) /bin/bash

# --- observability ------------------------------------------------------------

.PHONY: langfuse
langfuse: ## Open the Langfuse UI in a browser
	@open http://localhost:$(LANGFUSE_PORT) 2>/dev/null \
		|| xdg-open http://localhost:$(LANGFUSE_PORT) 2>/dev/null \
		|| echo "open http://localhost:$(LANGFUSE_PORT)"

.PHONY: langfuse-logs
langfuse-logs: ## Tail the Langfuse web + worker logs
	COMPOSE_PROFILES=langfuse $(COMPOSE) logs -f --tail=100 langfuse-web langfuse-worker

.PHONY: langfuse-ready
langfuse-ready: ## Block until Langfuse answers its health endpoint
	@for i in $$(seq 1 90); do \
		if curl -fsS http://localhost:$(LANGFUSE_PORT)/api/public/health >/dev/null 2>&1; then \
			echo "Langfuse is ready at http://localhost:$(LANGFUSE_PORT)"; exit 0; fi; \
		sleep 2; \
	done; \
	echo "Langfuse not ready - check 'make langfuse-logs'" >&2; exit 1

.PHONY: trace-check
trace-check: ## Emit one demo trace and verify it reaches Langfuse
	$(COMPOSE) run --rm $(APP_SERVICE) trace-check

.PHONY: trace-check-local
trace-check-local: ## Same, from the host virtualenv
	LANGFUSE_HOST=http://localhost:$(LANGFUSE_PORT) $(VENV_PY) -m prism_ch trace-check

.PHONY: langfuse-secrets
langfuse-secrets: ## Generate real SALT / NEXTAUTH_SECRET / ENCRYPTION_KEY for .env
	@echo "LANGFUSE_SALT=$$(openssl rand -base64 32)"
	@echo "LANGFUSE_NEXTAUTH_SECRET=$$(openssl rand -base64 32)"
	@echo "LANGFUSE_ENCRYPTION_KEY=$$(openssl rand -hex 32)"
	@echo ""
	@echo "# Paste the three lines above into .env, replacing the dev placeholders."

.PHONY: langfuse-down
langfuse-down: ## Stop the Langfuse services only
	COMPOSE_PROFILES=langfuse $(COMPOSE) stop \
		langfuse-web langfuse-worker langfuse-clickhouse \
		langfuse-postgres langfuse-redis langfuse-minio

# --- quality ------------------------------------------------------------------

.PHONY: lint
lint: ## Run ruff
	$(VENV)/bin/ruff check prism_ch tests

.PHONY: fmt
fmt: ## Format with ruff
	$(VENV)/bin/ruff format prism_ch tests

.PHONY: typecheck
typecheck: ## Run mypy
	$(VENV)/bin/mypy prism_ch

.PHONY: test
test: ## Run the test suite
	$(VENV_PY) -m pytest -q

.PHONY: check
check: lint typecheck test ## Lint, typecheck and test

# --- cleanup ------------------------------------------------------------------

.PHONY: clean
clean: ## Remove Python caches and the virtualenv
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +

.PHONY: destroy
destroy: ## Stop everything AND delete all data volumes, traces included (irreversible)
	@read -p "This deletes all ClickHouse data and every Langfuse trace. Type 'yes' to continue: " ans; \
	if [ "$$ans" = "yes" ]; then COMPOSE_PROFILES=langfuse $(COMPOSE) down -v; else echo "aborted"; fi

.PHONY: context
context: ## Refresh the context layer (set ATLYS_PACKAGE, or pass BASE=path/to/base_context.md)
	$(VENV_PY) -m prism_ch context $(if $(BASE),--base-context "$(BASE)")

.PHONY: context-log
context-log: ## Print the context layer changelog
	$(VENV_PY) -m prism_ch context-log


.PHONY: sync-rules
sync-rules: ## Vendor the exact ClickHouse rules: make sync-rules CH_SKILLS=/tmp/ch-skills
	@src="$(CH_SKILLS)/skills/clickhouse-best-practices/rules"; \
	test -d "$$src" || { \
		echo "clone it first:" >&2; \
		echo "  git clone --depth 1 https://github.com/ClickHouse/agent-skills.git /tmp/ch-skills" >&2; \
		exit 1; }; \
	cp "$$src"/*.md prism_ch/agents/rules/ 2>/dev/null; \
	rm -f prism_ch/agents/rules/_sections.md prism_ch/agents/rules/_template.md; \
	printf '%s\n' "synced $$(ls prism_ch/agents/rules/*.md | grep -v README | wc -l | tr -d ' ') rules (verbatim)"; \
	$(VENV_PY) -c "from prism_ch.agents.rules import rule_ids; print(' ', ', '.join(rule_ids()))" 2>/dev/null || true

.PHONY: analyze
analyze: ## Run the Analytics Agent: make analyze [FOCUS="express checkout"]
	$(COMPOSE) run --rm $(APP_SERVICE) analyze $(if $(FOCUS),--focus "$(FOCUS)")

.PHONY: ui
ui: ## Open the browser UI (start it with `make up` first)
	@open http://localhost:$${APP_PORT:-8000} 2>/dev/null \
		|| xdg-open http://localhost:$${APP_PORT:-8000} 2>/dev/null \
		|| echo "open http://localhost:$${APP_PORT:-8000}"

.PHONY: query
query: ## Run one SQL statement, prompting for the password: make query Q="SELECT 1"
	@test -n "$(Q)" || { echo 'usage: make query Q="SELECT 1"' >&2; exit 1; }
	$(CH_CLIENT_ASK) --query "$(Q)"

.PHONY: drop-generated
drop-generated: ## Drop every agent-generated table (prism_ prefix). Prompts twice.
	@echo "Tables that will be dropped from $(CH_DB):"
	@$(CH_CLIENT_ASK) --query "SELECT name FROM system.tables WHERE database = '$(CH_DB)' AND name LIKE 'prism_%' ORDER BY name"
	@read -p "Drop all of the above? Type 'yes': " ans; \
	if [ "$$ans" != "yes" ]; then echo aborted; exit 0; fi; \
	$(CH_CLIENT_ASK) --query "SELECT concat('DROP TABLE IF EXISTS $(CH_DB).', name) FROM system.tables WHERE database = '$(CH_DB)' AND name LIKE 'prism_%' FORMAT TSVRaw" \
		| while read -r stmt; do echo "$$stmt"; $(CH_CLIENT_ASK) --query "$$stmt"; done

.PHONY: pricing
pricing: ## Show configured per-model token prices
	@$(VENV_PY) -c "from prism_ch.pricing import MODEL_PRICES, TIER_MULTIPLIERS; \
	print('USD per 1M tokens (standard tier)'); \
	[print(f'  {k:<26} in {v.input:>6.2f}  out {v.output:>6.2f}' + (f'   >200k: in {v.long_input:.2f} out {v.long_output:.2f}' if v.long_input else '')) for k,v in sorted(MODEL_PRICES.items())]; \
	print(); print('tiers:', ', '.join(f'{k}x{v}' for k,v in TIER_MULTIPLIERS.items()))"
