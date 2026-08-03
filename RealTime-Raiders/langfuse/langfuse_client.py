"""
langfuse_client.py  (Langfuse SDK v4)
-------------------------------------
Shared plumbing for the concurrency prompt-ops pipeline: a Langfuse client, a
ClickHouse client for ground truth, an HTTP caller for the live agent, and
role-configurable LLM calls.

Runs STANDALONE on your machine, not inside a container.

Env (same .env as docker compose, plus the roles below):
    LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
    CH_HOST_BARE, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DATABASE
    AGENT_BASE_URL     default http://localhost:3002/v1
    AGENT_API_KEY

Three LLM roles, each independently configurable:
    JUDGE_*     scores outputs        — needs reliable JSON, use a capable model
    IMPROVER_*  rewrites prompts
    TASK_*      only used if you evaluate a bare prompt instead of the agent
Provider is anthropic | openrouter | google; keys are
ANTHROPIC_API_KEY / OPENROUTER_KEY / GOOGLE_KEY.
"""

import os

import requests
from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()

_lf = Langfuse(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    host=os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com"),
)


def client() -> Langfuse:
    return _lf


# ---- ClickHouse (ground truth) ----

def ch_client():
    import clickhouse_connect

    host = os.getenv("CH_HOST_BARE") or (
        os.environ["CLICKHOUSE_ENDPOINT"].replace("https://", "").replace("http://", "").split(":")[0]
    )
    return clickhouse_connect.get_client(
        host=host,
        port=int(os.getenv("CH_PORT", "8443")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=True,
        database=os.getenv("CLICKHOUSE_DATABASE", "liv"),
    )


# ---- The live agent under test ----

def call_agent(question: str, agent_id: str = "liv-analyst", timeout: int = 180) -> str:
    """
    POST to lc-agent's OpenAI-compatible endpoint.

    This is the point of the whole pipeline: we evaluate the REAL agent — with
    its MCP tools, its Langfuse-served prompt, its routing — not a prompt
    compiled in isolation. What gets scored is what gets demoed.

    Requires lc-agent's port to be published. Add to docker-compose.yml:
        lc-agent:
          ports:
            - "3002:3002"
    """
    base = os.getenv("AGENT_BASE_URL", "http://localhost:3002/v1")
    headers = {"Content-Type": "application/json"}
    key = os.getenv("AGENT_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    resp = requests.post(
        f"{base}/chat/completions",
        headers=headers,
        json={
            "model": agent_id,
            "messages": [{"role": "user", "content": question}],
            "stream": False,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ---- Role-configurable LLM calls ----

def _complete(provider: str, model: str, user: str,
              system: str | None = None, max_tokens: int = 1024) -> str:
    provider = (provider or "anthropic").lower()

    if provider in ("openrouter", "google", "xai"):
        from openai import OpenAI

        base_url, key_env = {
            "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_KEY"),
            "google": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GOOGLE_KEY"),
            "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
        }[provider]

        oai = OpenAI(api_key=os.environ[key_env], base_url=base_url)
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": user}]
        resp = oai.chat.completions.create(model=model, max_tokens=max_tokens, messages=messages)
        return resp.choices[0].message.content

    import anthropic

    kwargs = {"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": user}]}
    if system:
        kwargs["system"] = system
    return anthropic.Anthropic().messages.create(**kwargs).content[0].text


def _role(role: str, default_provider: str, default_model: str) -> tuple[str, str]:
    return (
        os.getenv(f"{role}_PROVIDER", default_provider).lower(),
        os.getenv(f"{role}_MODEL", default_model),
    )


def call_judge(user: str, system: str, max_tokens: int = 512) -> str:
    provider, model = _role("JUDGE", "openrouter", "openai/gpt-oss-120b")
    return _complete(provider, model, user, system=system, max_tokens=max_tokens)


def call_improver(user: str, system: str, max_tokens: int = 1500) -> str:
    provider, model = _role("IMPROVER", "openrouter", "openai/gpt-oss-120b")
    return _complete(provider, model, user, system=system, max_tokens=max_tokens)


def call_task(prompt_text: str, max_tokens: int = 1024) -> str:
    provider, model = _role("TASK", "openrouter", "nvidia/nemotron-3-super-120b-a12b:free")
    return _complete(provider, model, prompt_text, max_tokens=max_tokens)