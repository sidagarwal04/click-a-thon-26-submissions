"""Creates (or re-creates) the 4 real agents in LibreChat from agents/prompts.py,
generates an Agents API key if one isn't already set, and writes everything back
into .env. Reproducible — this is why prompts live in code, not just clicked into
the LibreChat UI.

Requires in .env: LIBRECHAT_URL, LIBRECHAT_ADMIN_EMAIL, LIBRECHAT_ADMIN_PASSWORD.
"""
import pathlib
import sys

import requests
from dotenv import load_dotenv
import os

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
load_dotenv()

from agents.prompts import AGENTS  # noqa: E402

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
MODEL = "gpt-5.6-luna"

ENV_VAR_BY_AGENT = {
    "instrumentation_proposer": "LIBRECHAT_AGENT_INSTRUMENTATION_PROPOSER",
    "context_reviewer": "LIBRECHAT_AGENT_CONTEXT_REVIEWER",
    "context_chronicler": "LIBRECHAT_AGENT_CONTEXT_CHRONICLER",
    "analytics_agent": "LIBRECHAT_AGENT_ANALYTICS",
}


def login(base_url: str) -> str:
    resp = requests.post(
        f"{base_url}/api/auth/login",
        headers={"User-Agent": UA, "Content-Type": "application/json"},
        json={
            "email": os.environ["LIBRECHAT_ADMIN_EMAIL"],
            "password": os.environ["LIBRECHAT_ADMIN_PASSWORD"],
        },
    )
    resp.raise_for_status()
    return resp.json()["token"]


def create_agent(base_url: str, jwt: str, name: str, spec: dict) -> str:
    resp = requests.post(
        f"{base_url}/api/agents",
        headers={"User-Agent": UA, "Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
        json={
            "name": name,
            "description": spec["description"],
            "provider": "openAI",
            "model": MODEL,
            # reasoning_effort must be a real level (not "none"/unset) so LibreChat
            # routes gpt-5.6 through the upstream Responses API — otherwise function
            # tools + reasoning 400 on Chat Completions. See agents/prompts.py header.
            "model_parameters": {"model": MODEL, "response_format": {"type": "json_object"}, "reasoning_effort": "low"},
            "instructions": spec["instructions"],
            "tools": spec.get("tools", []),
            "skills_enabled": spec.get("skills_enabled", False),
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def create_api_key(base_url: str, jwt: str) -> str:
    resp = requests.post(
        f"{base_url}/api/api-keys",
        headers={"User-Agent": UA, "Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
        json={"name": "orchestrator"},
    )
    resp.raise_for_status()
    return resp.json()["key"]


def update_env_file(updates: dict):
    env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    lines = env_path.read_text().splitlines()
    seen = set()
    for i, line in enumerate(lines):
        for key, value in updates.items():
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                seen.add(key)
    for key, value in updates.items():
        if key not in seen:
            lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n")


def main():
    base_url = os.environ["LIBRECHAT_URL"]
    jwt = login(base_url)
    print("logged in")

    updates = {}
    for name, spec in AGENTS.items():
        agent_id = create_agent(base_url, jwt, name, spec)
        env_var = ENV_VAR_BY_AGENT[name]
        updates[env_var] = agent_id
        print(f"created {name} -> {agent_id}")

    if not os.environ.get("LIBRECHAT_API_KEY"):
        api_key = create_api_key(base_url, jwt)
        updates["LIBRECHAT_API_KEY"] = api_key
        print("created new Agents API key")
    else:
        print("LIBRECHAT_API_KEY already set, leaving as-is")

    update_env_file(updates)
    print(f"\n.env updated with {len(updates)} values")


if __name__ == "__main__":
    main()
