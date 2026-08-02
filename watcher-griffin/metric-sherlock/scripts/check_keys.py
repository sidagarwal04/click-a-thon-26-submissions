"""Diagnose credential/config problems in one command instead of by symptom.

Exists because "Narration unavailable (gemini): GEMINI_API_KEY is not set" and
"no logs in Langfuse" are both the SAME root cause -- an empty or MISNAMED key
in utils/.env -- but neither message says so. The failure modes this catches:

  - key simply empty
  - key pasted into the wrong file, or into an unsaved editor buffer
  - key present under a name this project doesn't read (e.g. LANGFUSE_BASE_URL
    before aliasing, or REDIS_HOST which nothing here uses)
  - Langfuse keys valid but pointed at the WRONG REGION -- Langfuse is
    region-specific (cloud / us.cloud / jp.cloud); wrong region means valid
    keys and zero traces, with no error that points at the cause
  - a configured Gemini model that doesn't actually exist for your key

NEVER prints a secret value: only whether each key is set, its length, and a
4-char masked fingerprint so two keys can be told apart without exposing either.

Usage: .venv/Scripts/python.exe scripts/check_keys.py
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from engine.config import LLMProvider, Settings, settings  # noqa: E402

ENV_PATH = os.path.join(REPO, "utils", ".env")
OK = "OK  "
BAD = "MISSING"


def mask(value: str) -> str:
    if not value:
        return "<EMPTY>"
    return f"<SET, {len(value)} chars, starts '{value[:4]}...'>"


def env_file_keys() -> dict:
    """Raw key -> value from utils/.env, byte-level and CRLF-safe."""
    out = {}
    if not os.path.exists(ENV_PATH):
        return out
    with open(ENV_PATH, "rb") as f:
        for line in f.read().decode("utf-8", "replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def known_env_names() -> set:
    """Every env var name the Settings model actually reads, including aliases."""
    names = set()
    for field_name, field in Settings.model_fields.items():
        names.add(field_name.upper())
        alias = field.validation_alias
        if alias is None:
            continue
        choices = getattr(alias, "choices", None)
        if choices:
            names.update(str(c).upper() for c in choices)
        else:
            names.add(str(alias).upper())
    return names


def main() -> int:
    problems = []

    print(f"Reading config from: {ENV_PATH}")
    print(f"  (file exists on disk: {os.path.exists(ENV_PATH)})")
    print()

    raw = env_file_keys()

    # --- ClickHouse ---
    print("ClickHouse")
    print(f"  host     {mask(settings.clickhouse_host)}")
    print(f"  database {settings.clickhouse_database}")
    print(f"  password {mask(settings.clickhouse_password)}")
    if not settings.clickhouse_password:
        problems.append("CLICKHOUSE_PASSWORD is empty -- nothing will work.")
    print()

    # --- LLM narrator ---
    provider = settings.llm_provider
    key_for_provider = {
        LLMProvider.gemini: ("GEMINI_API_KEY", settings.gemini_api_key, settings.gemini_model),
        LLMProvider.anthropic: ("ANTHROPIC_API_KEY", settings.anthropic_api_key, settings.anthropic_model),
        LLMProvider.openai: ("OPENAI_API_KEY", settings.openai_api_key, settings.openai_model),
        LLMProvider.grok: ("GROK_API_KEY", settings.grok_api_key, settings.grok_model),
        LLMProvider.stub: (None, None, None),
    }
    print(f"LLM narrator (LLM_PROVIDER={provider.value})")
    name, value, model = key_for_provider[provider]
    if name is None:
        print("  stub provider -- no real LLM call, narration will be placeholder text")
    else:
        print(f"  [{OK if value else BAD}] {name} {mask(value or '')}")
        print(f"  model: {model}")
        if not value:
            problems.append(
                f"{name} is empty, so narration will report 'unavailable'. "
                f"Paste your key into utils/.env (or point LLM_PROVIDER at a provider whose key IS set)."
            )
        elif provider == LLMProvider.gemini:
            # Verify the configured model actually exists for this key, rather
            # than discovering it at narration time.
            try:
                from google import genai

                client = genai.Client(api_key=value)
                available = []
                for m in client.models.list():
                    mid = getattr(m, "name", "") or ""
                    available.append(mid.replace("models/", ""))
                if any(model == a or a.endswith("/" + model) for a in available):
                    print(f"  [{OK}] model '{model}' is available for this key")
                else:
                    flash = sorted(a for a in available if "flash" in a)[:6]
                    problems.append(
                        f"Configured gemini_model '{model}' was NOT found among the models this key can use. "
                        f"Some available flash models: {flash or available[:6]}. "
                        f"Set GEMINI_MODEL (or GEMINI_MODEL_FAST) in utils/.env to one of them."
                    )
            except Exception as e:
                print(f"  [WARN] could not list models to verify '{model}': {e}")
    print()

    # --- Langfuse ---
    print("Langfuse")
    pub, sec = settings.langfuse_public_key, settings.langfuse_secret_key
    print(f"  [{OK if pub else BAD}] LANGFUSE_PUBLIC_KEY {mask(pub or '')}")
    print(f"  [{OK if sec else BAD}] LANGFUSE_SECRET_KEY {mask(sec or '')}")
    print(f"  host (region): {settings.langfuse_host}")
    if "jp." not in settings.langfuse_host and "us." not in settings.langfuse_host:
        print("    ^ this is the default EU region. Langfuse is region-specific --")
        print("      if your project is US/JP, keys will be rejected. Set LANGFUSE_HOST")
        print("      (or LANGFUSE_BASE_URL) to https://us.cloud.langfuse.com / https://jp.cloud.langfuse.com")
    if not (pub and sec):
        problems.append(
            "Langfuse keys are empty, so tracing silently no-ops and NO traces are produced. "
            "Create a free project at cloud.langfuse.com and paste both keys into utils/.env."
        )
    else:
        try:
            from engine.tracing import get_langfuse_client

            client = get_langfuse_client()
            if client is None:
                problems.append("Langfuse keys are set but the client failed to construct.")
            else:
                print(f"  verifying credentials against {settings.langfuse_host} ...")
                if client.auth_check():
                    print(f"  [{OK}] auth_check passed -- traces will be delivered")
                else:
                    problems.append(
                        f"Langfuse auth_check FAILED against {settings.langfuse_host}. "
                        f"Keys are present but rejected -- most often this is the WRONG REGION."
                    )
        except Exception as e:
            # The SDK's exception stringifies the entire HTTP header block,
            # which buries the one line that matters. Keep the status + server
            # message only.
            text = str(e)
            status = "401" if "status_code: 401" in text else ""
            msg = text.split("body:", 1)[1].strip() if "body:" in text else text[:200]
            hint = ""
            if status == "401":
                hint = (
                    f" -- a 401 here is most often the WRONG REGION, not a bad key. "
                    f"Confirm your project really lives at {settings.langfuse_host}."
                )
            problems.append(f"Langfuse auth_check failed ({status or 'error'}): {msg}{hint}")
    print()

    # --- Keys present in the file that this project never reads ---
    known = known_env_names()
    unread = {k: v for k, v in raw.items() if k.upper() not in known}
    if unread:
        print("Set in utils/.env but NOT read by this project")
        for k, v in unread.items():
            print(f"  [INFO] {k} {mask(v)}")
        print("  ^ these are ignored entirely. If you expected one to take effect,")
        print("    it's misnamed -- check the spelling against utils/.env.example.")
        print()

    if problems:
        print("PROBLEMS FOUND:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("All configured. Narration and Langfuse tracing should both work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
