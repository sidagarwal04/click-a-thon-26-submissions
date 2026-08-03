"""provision_agent.py — auto-create the "Atlys PM" agent in LibreChat.

Run once at service startup (before uvicorn). Idempotent: if the agent already
exists it is reused. Writes the agent_id to <atlys_root>/.atlys_agent_id so
FastAPI's proxy endpoint can inject it into every chat request.

Usage:
    python scripts/provision_agent.py            # waits for LibreChat, then provisions
    python scripts/provision_agent.py --check    # just print current status and exit

ENGINEERING.md §6.1 — "Atlys PM" is the chat front door agent.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Allow running as `python scripts/provision_agent.py` from Atlys/ root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from service.settings import Settings  # noqa: E402

log = logging.getLogger("atlys.provision")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

# --------------------------------------------------------------------------- #
#  Agent definition  (mirrors ENGINEERING.md §6.1 "Atlys PM" system prompt)   #
# --------------------------------------------------------------------------- #

_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "agents" / "atlys_pm.md"

def _system_prompt() -> str:
    if _SYSTEM_PROMPT_PATH.exists():
        return _SYSTEM_PROMPT_PATH.read_text()
    # Inline fallback so the script never crashes if the file is missing
    return (
        "You are Atlys Copilot, the analytics copilot for Atlys's data team. "
        "You help product managers turn a feature spec into a ClickHouse schema, "
        "fresh business context, and a PM-readable insight.\n\n"
        "Workflow: (1) call interrogate_spec first; (2) call run_spec; "
        "(3) present the schema and ask for approval; (4) summarize the insight card.\n\n"
        "For live DB questions use db_schema, table_stats, aggregate, sample_rows "
        "(read-only; no free-form SQL).\n\n"
        "For document or report generation: fetch the data, call save_document, "
        "and return a relative path markdown link: [label](generated/reports/...).\n\n"
        "Rules: quote numbers exactly as returned; never invent figures, SQL, columns, "
        "or trace ids; always include the Langfuse trace id when given."
    )


# MCP tools the agent must have access to (from mcp_server.py TOOLS list).
# LibreChat only loads MCP tools when agent.tools entries include the
# `_mcp_<server>` delimiter (see ToolService.hasMCPTools / mcp_delimiter).
# Bare names like `db_schema` are ignored for MCP binding — the model then
# narrates "let me look that up" with finish_reason=stop and empty tool_calls.
# Do not include ingest_events — disabled on the demo MCP surface.
_MCP_SERVER = "atlys-orchestrator"
_ATLYS_TOOL_NAMES = [
    "interrogate_spec", "run_spec", "approve_schema", "reject_schema",
    "get_insight", "list_insights", "get_changelog", "get_context",
    "propose_context_update", "reconcile",
    "db_schema", "table_stats", "aggregate", "sample_rows", "save_document",
]
_ATLYS_TOOLS = [f"{name}_mcp_{_MCP_SERVER}" for name in _ATLYS_TOOL_NAMES]

_AGENT_NAME = "Atlys PM"
_MODEL = "glm-5.2"  # latest Z.ai flagship; context window in librechat.yaml tokenConfig
# Must match librechat.yaml endpoints.custom[].name — getProviderConfig looks
# up custom endpoints by this provider string (not "customOpenAI").
_PROVIDER = "ZAI"

# --------------------------------------------------------------------------- #
#  LibreChat REST helpers                                                      #
# --------------------------------------------------------------------------- #

try:
    import urllib.request as _urlreq
    import urllib.error as _urlerr
except ImportError:
    _urlreq = None  # type: ignore


def _request(url: str, method: str = "GET", data: dict | None = None,
             token: str | None = None, timeout: int = 15) -> dict:
    body = json.dumps(data).encode() if data else None
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = _urlreq.Request(url, data=body, headers=headers, method=method)
    try:
        with _urlreq.urlopen(req, timeout=timeout) as resp:
            raw_body = resp.read().decode(errors="replace")
            try:
                return json.loads(raw_body)
            except json.JSONDecodeError as jde:
                raise RuntimeError(
                    f"Failed to parse JSON response. Status: {resp.status}. "
                    f"Response preview: {raw_body[:200]}"
                ) from jde
    except _urlerr.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason} — {body_text}") from e



def _wait_for_librechat(base_url: str, max_wait: int = 120) -> None:
    """Block until LibreChat's health endpoint responds (up to max_wait seconds)."""
    health_url = f"{base_url}/health"
    deadline = time.time() + max_wait
    log.info("Waiting for LibreChat at %s …", base_url)
    while time.time() < deadline:
        try:
            req = _urlreq.Request(health_url, method="GET")
            with _urlreq.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    log.info("LibreChat is up.")
                    return
        except Exception as e:
            log.debug("LibreChat not ready: %s", e)
            time.sleep(3)
    raise TimeoutError(f"LibreChat did not become ready within {max_wait}s")




def _login(base_url: str, email: str, password: str) -> str:
    """Authenticate and return a JWT token.

    If the email does not exist, registers the admin account automatically
    so that cold starts require no manual browser registration steps.
    """
    try:
        resp = _request(
            f"{base_url}/api/auth/login",
            method="POST",
            data={"email": email, "password": password},
        )
        token = resp.get("token") or (resp.get("data") or {}).get("token")
        if not token:
            raise RuntimeError(f"Login succeeded but no token in response: {resp}")
        log.info("Authenticated as %s", email)
        return token
    except Exception as e:
        if "Email does not exist" in str(e):
            log.info("Admin user '%s' does not exist. Registering account...", email)
            try:
                _request(
                    f"{base_url}/api/auth/register",
                    method="POST",
                    data={
                        "name": "Admin",
                        "email": email,
                        "password": password,
                        "confirm_password": password,
                    },
                )
                log.info("Registration successful. Logging in...")
                return _login(base_url, email, password)
            except Exception as reg_err:
                raise RuntimeError(f"Auto-registration failed: {reg_err}") from reg_err
        raise



def _find_existing_agent(base_url: str, token: str, name: str) -> str | None:
    """Return agent_id of an existing agent with the given name, or None."""
    try:
        resp = _request(f"{base_url}/api/agents", token=token)
        agents = resp if isinstance(resp, list) else resp.get("data") or resp.get("agents") or []
        for ag in agents:
            if ag.get("name") == name:
                log.info("Found existing agent '%s' → id=%s", name, ag["id"])
                return ag["id"]
    except Exception as e:
        log.warning("Could not list agents: %s", e)
    return None


def _create_agent(base_url: str, token: str) -> str:
    """Create the Atlys PM agent and return its agent_id."""
    payload = {
        "name": _AGENT_NAME,
        "description": "Atlys Copilot — turns feature specs into ClickHouse schemas + insights.",
        "instructions": _system_prompt(),
        "model": _MODEL,
        "provider": _PROVIDER,
        # LibreChat pluginKeys: <tool>_mcp_<server> (not bare MCP tool names).
        "tools": _ATLYS_TOOLS,
        "mcp_servers": [_MCP_SERVER],
    }
    resp = _request(f"{base_url}/api/agents", method="POST", data=payload, token=token)
    agent_id = resp.get("id") or (resp.get("data") or {}).get("id")
    if not agent_id:
        raise RuntimeError(f"Agent creation response has no id: {resp}")
    log.info("Created agent '%s' → id=%s", _AGENT_NAME, agent_id)
    return agent_id


def _ensure_agent_config(base_url: str, token: str, agent_id: str) -> None:
    """Keep provider/model/tools/instructions in sync with this repo's defaults."""
    try:
        resp = _request(f"{base_url}/api/agents/{agent_id}", token=token)
    except Exception as e:
        log.warning("Could not fetch agent %s: %s", agent_id, e)
        return

    patch: dict = {}
    provider = resp.get("provider")
    if provider != _PROVIDER:
        log.info("Updating agent provider %s → %s", provider, _PROVIDER)
        patch["provider"] = _PROVIDER

    model = resp.get("model")
    if model != _MODEL or "model" in patch:
        log.info("Updating agent model %s → %s", model, _MODEL)
        patch["model"] = _MODEL

    current_tools = resp.get("tools") or []
    # Normalize to pluginKey strings (LibreChat may return objects).
    current_names = []
    for t in current_tools:
        if isinstance(t, str):
            current_names.append(t)
        elif isinstance(t, dict):
            current_names.append(
                t.get("pluginKey") or t.get("name") or t.get("tool") or ""
            )
    current_names = [n for n in current_names if n]
    # Also accept legacy bare names and rewrite them to `_mcp_` pluginKeys.
    if set(current_names) != set(_ATLYS_TOOLS):
        log.info(
            "Updating agent tools (%s → %s pluginKeys; sample=%s)",
            len(current_names),
            len(_ATLYS_TOOLS),
            (_ATLYS_TOOLS[0] if _ATLYS_TOOLS else ""),
        )
        patch["tools"] = _ATLYS_TOOLS

    instructions = resp.get("instructions") or ""
    desired = _system_prompt()
    if (
        instructions != desired
        or "db_schema" not in instructions
        or "atlyschart" not in instructions
        or "gte" not in instructions
        or "one call" not in instructions
        or "TOOL_LIMIT" not in instructions
        or "AUTO_APPROVE_EXACT_PHRASES" not in instructions
        or instructions != desired
    ):
        log.info("Updating agent instructions (sync from agents/atlys_pm.md)")
        patch["instructions"] = desired

    if not patch:
        return
    _request(
        f"{base_url}/api/agents/{agent_id}",
        method="PATCH",
        data=patch,
        token=token,
    )


def _ensure_api_key(base_url: str, token: str, settings: Settings) -> str:
    """Return an Agents API key for /api/agents/v1/* (login JWTs are rejected).

    Reuses LIBRECHAT_API_KEY / persisted file when present; otherwise creates a
    new key via POST /api/api-keys and writes it to generated/.atlys_librechat_api_key.
    """
    existing = settings.load_librechat_api_key()
    if existing:
        log.info("Reusing existing LibreChat Agents API key")
        return existing

    # remoteAgents.create must be enabled (librechat.yaml) or the user must be ADMIN.
    last_err: Exception | None = None
    for attempt in range(1, 9):
        try:
            resp = _request(
                f"{base_url}/api/api-keys",
                method="POST",
                data={"name": "atlys-proxy"},
                token=token,
            )
            api_key = resp.get("key")
            if not api_key:
                raise RuntimeError(f"API key create response missing key: {resp}")
            # Check if key is already persisted and correct before writing to avoid permission issues
            if not settings.librechat_api_key_path.exists() or settings.librechat_api_key_path.read_text().strip() != api_key:
                settings.librechat_api_key_path.write_text(api_key)
                log.info("Agents API key persisted to %s", settings.librechat_api_key_path)
            else:
                log.info("Agents API key already matched in %s", settings.librechat_api_key_path)
            return api_key
        except Exception as e:
            last_err = e
            # Role permissions from interface.remoteAgents may lag a few seconds after boot.
            log.warning(
                "API key create attempt %s failed (%s); retrying…", attempt, e
            )
            time.sleep(2)
    raise RuntimeError(
        "Failed to create LibreChat Agents API key. Enable interface.remoteAgents "
        f"(use/create) and endpoints.agents.remoteApi.auth.apiKey.enabled in "
        f"librechat.yaml. Last error: {last_err}"
    )


# --------------------------------------------------------------------------- #
#  Main                                                                        #
# --------------------------------------------------------------------------- #

def provision(settings: Settings) -> str:
    """Ensure the Atlys PM agent + Agents API key exist. Returns the agent_id."""
    if not settings.librechat_admin_email or not settings.librechat_admin_password:
        raise RuntimeError(
            "LIBRECHAT_ADMIN_EMAIL and LIBRECHAT_ADMIN_PASSWORD must be set for provisioning. "
            "Set them in .env."
        )

    base = settings.librechat_url.rstrip("/")
    _wait_for_librechat(base)

    token = _login(base, settings.librechat_admin_email, settings.librechat_admin_password)

    # Reuse existing agent if already provisioned
    agent_id = _find_existing_agent(base, token, _AGENT_NAME)
    if not agent_id:
        agent_id = _create_agent(base, token)
    else:
        _ensure_agent_config(base, token, agent_id)

    # Persist so the proxy can read it across restarts
    settings.generated_dir.mkdir(parents=True, exist_ok=True)
    if not settings.agent_id_path.exists() or settings.agent_id_path.read_text().strip() != agent_id:
        settings.agent_id_path.write_text(agent_id)
        log.info("agent_id persisted to %s", settings.agent_id_path)
    else:
        log.info("agent_id already matched in %s", settings.agent_id_path)

    # Agents OpenAI-compatible route requires an API key, not the login JWT.
    _ensure_api_key(base, token, settings)
    return agent_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision the Atlys PM agent in LibreChat")
    parser.add_argument("--check", action="store_true",
                        help="Print current agent_id status and exit (no provisioning)")
    args = parser.parse_args()

    settings = Settings()

    if args.check:
        agent_id = settings.load_agent_id()
        api_key = settings.load_librechat_api_key()
        if agent_id and api_key:
            print(f"✅  Provisioned — agent_id: {agent_id}, api_key: set")
        elif agent_id:
            print(f"⚠️  Agent exists ({agent_id}) but Agents API key missing — re-run provision")
        else:
            print("❌  Not provisioned — run without --check to provision")
        return

    try:
        agent_id = provision(settings)
        print(f"✅  Done — agent_id: {agent_id}")
    except Exception as e:
        log.error("Provisioning failed: %s", e)
        log.warning("Continuing without agent provisioning — chat proxy will return 503 until provisioned")
        sys.exit(1)


if __name__ == "__main__":
    main()
