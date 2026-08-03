# Atlys solution — common hackathon commands.
# NEVER run `make nuke` against a live demo DB without an explicit backup.
#
# Fresh clone, zero to running:
#   make init        # venv + deps, git-lfs pull, ClickHouse up, schema + data loaded,
#                     # context bootstrapped, stack smoke-tested, full test suite
# See README.md "Setup (fresh clone)" for the manual step-by-step equivalent.

SHELL := /bin/bash
COMPOSE := docker compose -f deploy/docker-compose.yml
COMPOSE_CH := docker compose -f deploy/docker-compose.ch.yml
PYBIN := $(shell command -v python3.12 || command -v python3.13 || command -v python3)
VENV := ./.venv/bin
PY := $(VENV)/python
NETWORK := atlys-net
CH_CONTAINER := atlys-ch

.PHONY: init setup lfs network ch-up ch-down up down mcp mcp-docker seed bootstrap \
        pipeline sim-all eval legacy chat chat-secrets logs connect-ch verify-stack \
        test schema-doc nuke help

help:
	@echo "make init        - zero to running: setup + lfs + ch-up + seed + bootstrap + test"
	@echo "make setup       - create .venv and install this package (editable, dev+mcp extras)"
	@echo "make lfs         - git lfs pull the ../data parquet files (~253MB)"
	@echo "make ch-up       - provision the $(CH_CONTAINER) ClickHouse container from scratch"
	@echo "make seed        - load ../data parquet files into $(CH_CONTAINER)"
	@echo "make bootstrap   - parse ../base_context.md into the context layer"
	@echo "make up          - network + attach $(CH_CONTAINER) + start mcp-clickhouse"
	@echo "make mcp         - run atlys-mcp on the HOST (uses Claude CLI subscription)"
	@echo "make chat        - bring up LibreChat profile + open :3080"
	@echo "make verify-stack- smoke: explain_metric + list_contradictions via Python"
	@echo "make test        - fast, no-LLM test suite (~2s)"
	@echo "make schema-doc  - regenerate docs/SCHEMA_CATALOG.md from the live DB"
	@echo "make eval        - T8 eval harness"
	@echo "make legacy      - T4 projection remediation on destination_card_clicked"
	@echo "make down        - stop mcp/librechat; leaves $(CH_CONTAINER) running"
	@echo "make ch-down     - stop $(CH_CONTAINER) itself (data volume kept)"
	@echo "make nuke        - DANGER: compose down -v (does NOT remove $(CH_CONTAINER))"

init: setup lfs ch-up seed bootstrap verify-stack test
	@echo ""
	@echo "Ready. Try:  $(PY) run_pipeline.py --spec ../specs/05_instant_forex/spec.md --events ../specs/05_instant_forex/events.ndjson"

setup:
	@test -d .venv || $(PYBIN) -m venv .venv
	$(VENV)/pip install --upgrade pip -q
	$(VENV)/pip install -e '.[dev,mcp]' -q
	@test -f .env || { cp .env.example .env; echo "wrote .env from .env.example — fill in Langfuse keys before demoing"; }
	@echo "venv ready: $$($(PY) --version) ($(PYBIN))"

lfs:
	@command -v git-lfs >/dev/null || { echo "git-lfs not installed — 'brew install git-lfs' (or your package manager), then 'git lfs install'"; exit 1; }
	git lfs pull --include="Atlys/data/*.parquet"
	@ls -la ../data/*.parquet | awk '{print $$5, $$NF}'

network:
	docker network create $(NETWORK) 2>/dev/null || true

ch-up: network
	$(COMPOSE_CH) up -d
	@echo -n "waiting for $(CH_CONTAINER)"
	@until docker exec $(CH_CONTAINER) wget --spider -q http://localhost:8123/ping 2>/dev/null; do echo -n "."; sleep 1; done
	@echo " ready on :8123 (user/pass: atlys/atlys, db: atlys)"

ch-down:
	$(COMPOSE_CH) down
	@echo "$(CH_CONTAINER) stopped; data volume atlys-ch-data kept"

connect-ch: network
	# Idempotent fallback for a $(CH_CONTAINER) that predates docker-compose.ch.yml
	# (e.g. started by hand) — `make ch-up` already joins $(NETWORK) with this alias.
	@docker network inspect $(NETWORK) --format '{{range .Containers}}{{.Name}} {{end}}' \
		| grep -q $(CH_CONTAINER) \
		|| docker network connect --alias clickhouse $(NETWORK) $(CH_CONTAINER)
	@echo "connected $(CH_CONTAINER) → $(NETWORK) (alias: clickhouse)"

up: ch-up
	$(COMPOSE) up -d mcp-clickhouse
	@echo "mcp-clickhouse  http://localhost:8000/mcp"
	@echo "atlys-mcp       run: make mcp   (host process, Claude subscription)"

mcp:
	@echo "starting atlys-mcp on :8100 (Ctrl-C to stop)"
	ATLYS_MCP_HOST=0.0.0.0 ATLYS_MCP_PORT=8100 $(PY) -m atlys_mcp

mcp-docker: connect-ch
	$(COMPOSE) up -d --build atlys-mcp
	@echo "atlys-mcp (container) http://localhost:8100/mcp"
	@echo "NOTE: container has no Claude CLI; set ATLYS_LLM_BACKEND=api + ANTHROPIC_API_KEY"

chat-secrets:
	@grep -q '^CREDS_KEY=' .env 2>/dev/null || { \
	  echo "" >> .env; \
	  echo "# ---- LibreChat (local only; never commit) ----" >> .env; \
	  $(PY) -c "import secrets;print('CREDS_KEY='+secrets.token_hex(32));print('CREDS_IV='+secrets.token_hex(16));print('JWT_SECRET='+secrets.token_hex(32));print('JWT_REFRESH_SECRET='+secrets.token_hex(32))" >> .env; \
	  echo "wrote LibreChat secrets into .env"; \
	}
	@grep -q '^LIBRECHAT_ANTHROPIC_API_KEY=' .env 2>/dev/null || \
	  echo "NOTE: set LIBRECHAT_ANTHROPIC_API_KEY in .env for the LibreChat chat model (separate from ATLYS_LLM_BACKEND=cli)"

chat: connect-ch chat-secrets
	@set -a; source .env; set +a; \
	  test -n "$$CREDS_KEY" || { echo "CREDS_KEY missing in .env"; exit 1; }; \
	  $(COMPOSE) --profile librechat up -d mcp-clickhouse mongodb librechat
	@echo ""
	@echo "LibreChat      http://localhost:3080"
	@echo "atlys-mcp      ensure running:  make mcp   (host :8100, Claude subscription)"
	@echo "mcp-clickhouse http://localhost:8000/mcp"
	@echo ""
	@echo "In LibreChat: register → Anthropic/Sonnet → enable MCP 'atlys' + 'clickhouse'"
	@echo "Try:  what is our conversion rate?"
	@command -v open >/dev/null && open http://localhost:3080 || true

down:
	$(COMPOSE) --profile librechat down
	@echo "$(CH_CONTAINER) left running (by design)"

seed:
	cd ../data && CH='docker exec -i $(CH_CONTAINER) clickhouse-client' DB=atlys ./load.sh

bootstrap:
	$(PY) bootstrap_db.py

pipeline:
	$(PY) run_pipeline.py --spec ../specs/$(SPEC)/spec.md \
	                      --events ../specs/$(SPEC)/events.ndjson

sim-all:
	@for s in 01_express_checkout 02_group_family 03_status_sharing \
	          04_abandoned_checkout_recovery 05_instant_forex; do \
		echo "=== $$s ==="; \
		$(PY) run_pipeline.py --spec ../specs/$$s/spec.md \
		                       --events ../specs/$$s/events.ndjson --rebuild --yes || exit 1; \
	done

eval:
	$(PY) -m evalharness --all --out out/eval

legacy:
	$(PY) legacy.py --table destination_card_clicked

verify-stack:
	@$(PY) -c "import tracing; print('langfuse', tracing.verify())"
	@$(PY) -c "\
from ch import CH; import metric_policy, agents.context_agent as ca; \
ch=CH(); ctx=ca.snapshot(ch=ch, run_id='verify', note='make'); \
print(metric_policy.explain_metric(ch, 'conversion rate', ctx)); \
print('contradictions', len(metric_policy.load_open_conflicts(ch, ctx)))"

test:
	$(PY) -m pytest tests/ -q

schema-doc:
	$(PY) -m tools.schema_catalog

logs:
	$(COMPOSE) logs -f --tail=100

nuke:
	@echo "Refusing to touch $(CH_CONTAINER). Stopping compose services only."
	$(COMPOSE) --profile librechat down -v
