"""Narrator: the single LLM call at the end of an investigation, plus the
deterministic template used when no LLM key is configured or the LLM draft fails
the guardrail twice. The LLM narrates and formats only — the verdict and every
number are already in the bundle. Templates cite bundle values verbatim (str() of
the stored floats), so they pass the guardrail by construction.

Providers (zero dependencies, urllib only):
  Anthropic Messages API      — ANTHROPIC_API_KEY, models claude-*
  Google Gemini generateContent — GOOGLE_KEY (or GEMINI_API_KEY), models gemini-*
  OpenAI Chat Completions     — OPENAI_API_KEY, any other model name (gpt-*, o*)
NARRATOR_MODEL picks the model; the provider follows from its name and which keys
exist (a model naming a key-less provider falls back to whichever provider has a
key, with that provider's default model).

On OpenAI reasoning models (gpt-5*, o*) NARRATOR_EFFORT sets reasoning_effort;
default "minimal" — narration copies figures out of a finished bundle, so paid
reasoning tokens buy nothing here.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
DEFAULT_OPENAI_MODEL = "gpt-5-nano"     # cheapest OpenAI tier; ample for narration
DEFAULT_GOOGLE_MODEL = "gemini-3.5-flash"

SYSTEM = """You are the narrator of an automated root-cause analysis. The investigation is
already complete; the JSON evidence bundle you receive contains every number that exists.
Absolute rules:
- You compute nothing and infer nothing. Cite figures digit-for-digit as they appear in
  the bundle (same decimals, e.g. -3.455 may be written as 3.455 pp with a direction
  word). A number not present in the bundle must not appear in your text.
- First line: a headline of at most 120 characters naming the metric, the move, the
  window, and the confirmed cause segment if any. Plain text, no markdown syntax.
- Then a blank line, then one or two short paragraphs (at most 180 words total): the
  cause with magnitudes first, then what was checked and ruled out (dimension names and
  their residuals).
- The bundle's verdict.code is the conclusion. Never soften, hedge, or overrule it.
- For NO_MOVEMENT / DISAGREEMENT / NO_DATA verdicts, state plainly what was (not) found
  and list what was checked.
- Emit the narrative and nothing else: no preamble or restatement of these rules (never
  open with "Headline:", "Two short paragraphs:" or similar), no markdown headings or
  bullet lists, no closing commentary. First character is the first word of the
  headline. (Small models leak the instruction shape into the text without this.)"""


_DEFAULTS = {"anthropic": DEFAULT_ANTHROPIC_MODEL, "openai": DEFAULT_OPENAI_MODEL,
             "google": DEFAULT_GOOGLE_MODEL}


def _api_key(provider: str) -> str | None:
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY") or None
    if provider == "google":
        return os.environ.get("GOOGLE_KEY") or os.environ.get("GEMINI_API_KEY") or None
    return os.environ.get("OPENAI_API_KEY") or None


def _openai_reasoning(model: str) -> bool:
    """gpt-5*/o-series take reasoning_effort; gpt-4o, gpt-4.1 and the *-chat-latest
    aliases are not reasoning models and reject the field."""
    if "chat" in model:
        return False
    return model.startswith("gpt-5") or (model.startswith("o") and model[1:2].isdigit())


def _provider_of(model: str) -> str:
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith(("gemini", "gemma")):   # gemma serves via the same Gemini API
        return "google"
    return "openai"


def _resolve() -> tuple[str, str] | None:
    """(provider, model) from NARRATOR_MODEL and whichever API keys exist."""
    m = os.environ.get("NARRATOR_MODEL", "")
    if m.lower() in ("template", "none", "off"):
        return None          # explicit opt-out: deterministic template, zero LLM calls
    if m and _api_key(_provider_of(m)):
        return _provider_of(m), m
    # model names a provider we have no key for (or is unset): use what we have
    for provider in ("anthropic", "openai", "google"):
        if _api_key(provider):
            return provider, _DEFAULTS[provider]
    return None


def llm_available() -> bool:
    return _resolve() is not None


def model_name() -> str:
    r = _resolve()
    return r[1] if r else os.environ.get("NARRATOR_MODEL", DEFAULT_ANTHROPIC_MODEL)


def _post(url: str, payload: dict, headers: dict) -> dict | None:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        print(f"[narrator] LLM call failed (HTTP {e.code}: {detail}); "
              "falling back to template")
        return None
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"[narrator] LLM call failed ({e}); falling back to template")
        return None


def call_llm(bundle: dict, prior_draft: str | None = None,
             misses: list | None = None) -> dict | None:
    """One LLM call. Returns {text, model, usage, duration_ms} or None on error."""
    resolved = _resolve()
    if resolved is None:
        return None
    provider, model = resolved
    turns = [{"role": "user", "content":
              "Evidence bundle:\n" + json.dumps(bundle, default=str)}]
    if prior_draft is not None:
        bad = ", ".join(m["token"] for m in (misses or [])) or "(unknown)"
        turns += [
            {"role": "assistant", "content": prior_draft},
            {"role": "user", "content":
             f"Your draft cited numbers that do not exist in the bundle: {bad}. "
             "Rewrite it citing only numbers present in the bundle, digit-for-digit."},
        ]
    t0 = time.monotonic()

    if provider == "anthropic":
        body = _post(
            os.environ.get("ANTHROPIC_API_URL", "https://api.anthropic.com/v1/messages"),
            {"model": model, "max_tokens": 700, "system": SYSTEM, "messages": turns},
            {"x-api-key": os.environ["ANTHROPIC_API_KEY"],
             "anthropic-version": "2023-06-01"})
        if body is None:
            return None
        text = "".join(b.get("text", "") for b in body.get("content", []))
        usage = body.get("usage", {})
        in_tok, out_tok = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    elif provider == "google":
        base = os.environ.get("GOOGLE_API_URL",
                              "https://generativelanguage.googleapis.com/v1beta")
        contents = [{"role": "model" if t["role"] == "assistant" else "user",
                     "parts": [{"text": t["content"]}]} for t in turns]
        # gemini-2.5 counts internal "thinking" against maxOutputTokens; narration
        # needs none of it — disable on flash (pro can't go to 0), keep headroom
        # temperature 0: narration must copy figures digit-for-digit — sampling
        # variety only produces rounded/derived numbers the guardrail rejects
        # (gemma-31b at default temp burned 2×40s attempts per incident on this)
        gen_cfg: dict = {"maxOutputTokens": 2048, "temperature": 0}
        if "flash" in model:
            gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}
        body = _post(
            f"{base}/models/{model}:generateContent",
            {"system_instruction": {"parts": [{"text": SYSTEM}]},
             "contents": contents,
             "generationConfig": gen_cfg},
            {"x-goog-api-key": _api_key("google")})
        if body is None:
            return None
        cands = body.get("candidates") or [{}]
        text = "".join(p.get("text", "")
                       for p in (cands[0].get("content") or {}).get("parts", []))
        usage = body.get("usageMetadata", {})
        in_tok = usage.get("promptTokenCount", 0)
        out_tok = usage.get("candidatesTokenCount", 0)
    else:
        payload: dict = {"model": model, "max_completion_tokens": 700,
                         "messages": [{"role": "system", "content": SYSTEM}] + turns}
        if _openai_reasoning(model):
            # reasoning tokens are billed and counted against max_completion_tokens,
            # and narration invents nothing — every figure is already in the bundle.
            # "minimal" is the floor gpt-5-nano accepts ("none" is 5.1+ only) and
            # measures 0 reasoning tokens. Leave temperature alone: reasoning models
            # reject anything but the default.
            payload["reasoning_effort"] = os.environ.get("NARRATOR_EFFORT", "minimal")
            payload["max_completion_tokens"] = 2048   # headroom if effort is raised
        body = _post(
            os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions"),
            payload,
            {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
        if body is None:
            return None
        choices = body.get("choices") or [{}]
        text = (choices[0].get("message") or {}).get("content") or ""
        usage = body.get("usage", {})
        in_tok, out_tok = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)

    return {"text": text.strip(), "model": body.get("model", model),
            "usage": {"input": in_tok, "output": out_tok},
            "duration_ms": int((time.monotonic() - t0) * 1000)}


def split_headline(text: str) -> tuple[str, str]:
    lines = text.strip().splitlines()
    head = lines[0].strip().lstrip("# ").strip() if lines else ""
    rest = "\n".join(lines[1:]).strip()
    return head[:200], rest or head


# ── deterministic template (guardrail-safe by construction) ──────────────────

_LABEL = {"fill_rate": "Fill rate", "render_rate": "Render rate", "ctr": "CTR",
          "ecpm": "eCPM", "requests": "Requests", "fills": "Fills",
          "impressions": "Impressions", "clicks": "Clicks", "revenue": "Revenue"}


def _win(inc: dict) -> str:
    return f"{inc['window_start']} → {inc['window_end']} UTC"


def _dir(x) -> str:
    return "fell" if (x or 0) < 0 else "rose"


def _q1_move(bundle: dict) -> str:
    """The global move sentence fragment for the primary lever, from q1 numbers."""
    q1 = bundle.get("q1") or {}
    lever = (bundle["verdict"].get("primary_lever") or bundle["incident"]["metric"])
    if lever == "requests" and q1.get("requests_pct") is not None:
        return f"requests {_dir(q1['requests_pct'])} {abs(q1['requests_pct'])}%"
    field = {"fill_rate": "fill_rate_delta_pp", "render_rate": "render_rate_delta_pp"}.get(lever)
    if field and q1.get(field) is not None:
        return f"{_LABEL[lever]} {_dir(q1[field])} {abs(q1[field])} pp"
    if lever == "ecpm" and q1.get("ecpm_delta") is not None:
        return f"eCPM {_dir(q1['ecpm_delta'])} ${abs(q1['ecpm_delta'])}"
    m = bundle["incident"]["metric"]
    if q1.get("revenue_pct") is not None and m == "revenue":
        return f"revenue {_dir(q1['revenue_pct'])} {abs(q1['revenue_pct'])}%"
    return f"{_LABEL.get(m, m)} moved"


def _ruled_out_sentence(v: dict) -> str:
    ro = v.get("ruled_out") or []
    if not ro:
        return ""
    return " Checked and ruled out: " + "; ".join(ro) + "."


def _baseline_note(bundle: dict) -> str:
    b = bundle.get("baseline") or {}
    n = len(b.get("base_days_used") or [])
    if not n:
        return ""
    excl = b.get("excluded_dates") or []
    note = f" Baseline: same-weekday medians over {n} clean days"
    if excl:
        note += f" ({len(excl)} previously-diagnosed date(s) excluded)"
    return note + "."


def template(bundle: dict) -> tuple[str, str]:
    """Deterministic narrative from the bundle. Every figure is a bundle value."""
    v = bundle["verdict"]
    inc = bundle["incident"]
    code = v["code"]
    metric = inc["metric"]
    label = _LABEL.get(metric, metric)
    win = _win(inc)
    cause = v.get("cause")

    if code in ("CAUSE_CONFIRMED", "DEMAND_PULLOUT", "VOLUME_CANDIDATE"):
        seg, dim = cause["seg"], cause["dim"]
        head = f"{_q1_move(bundle).capitalize()} ({inc['window_start'][:10]}): {seg} ({dim})"
        if code == "CAUSE_CONFIRMED":
            body = (f"{_q1_move(bundle).capitalize()} over {win} vs the same-weekday "
                    f"baseline. The move concentrates in {seg} ({dim}): "
                    f"{cause['val_base']} → {cause['val_inc']} (delta {cause['delta']}), "
                    f"contributing {cause['contribution_pp']} pp of the global move")
            if cause.get("share_of_move_pct") is not None:
                body += f" — {cause['share_of_move_pct']}% of it"
            body += "."
        elif code == "DEMAND_PULLOUT":
            body = (f"{_q1_move(bundle).capitalize()} over {win}. Fill rate is undefined "
                    f"across advertiser attributes, so fills themselves were swept: "
                    f"{seg} ({dim}) delivered {cause['vol_inc']} fills vs "
                    f"{cause['vol_expected']} expected ({cause['pct_change']}%), "
                    f"{cause['share_of_total_change']}% of the total fills change — "
                    f"a demand-side pullout.")
        else:
            body = (f"{_q1_move(bundle).capitalize()} over {win}. The change concentrates "
                    f"in {seg} ({dim}): {cause['vol_inc']} vs {cause['vol_expected']} "
                    f"expected ({cause['pct_change']}%), {cause['share_of_total_change']}% "
                    f"of the total change.")
        return head, body + _ruled_out_sentence(v) + _baseline_note(bundle)

    if code == "INTERACTION":
        ix = cause
        head = (f"{_q1_move(bundle).capitalize()}: interaction segment "
                f"{ix['seg1']} × {ix['seg2']}")
        body = (f"{_q1_move(bundle).capitalize()} over {win}. Excluding {ix['seg1']} "
                f"({ix['dim1']}) shrinks but does not clear the {ix['dim2']} residual "
                f"({ix['residual']}), so the cross was drilled: {ix['seg1']} × "
                f"{ix['seg2']} ({ix['dim2']}) moved {ix['cross_delta']} "
                f"({ix['cross_val_base']} → {ix['cross_val_inc']}) — the cause is the "
                f"interaction of both, not either alone.")
        return head, body + _ruled_out_sentence(v) + _baseline_note(bundle)

    if code == "MIX_SHIFT":
        mx = cause
        head = f"{label} moved on {mx['dim']} mix shift, not segment rates ({inc['window_start'][:10]})"
        body = (f"{_q1_move(bundle).capitalize()} over {win}, but every segment's own "
                f"rate is flat. Kitagawa split on {mx['dim']}: within "
                f"{mx['within_effect_pp']} pp, mix {mx['mix_effect_pp']} pp, interaction "
                f"{mx['interaction_pp']} pp of a {mx['total_delta_pp']} pp total — the "
                f"mix term dominates: traffic reshuffled between segments.")
        if mx.get("top_mover"):
            t = mx["top_mover"]
            body += (f" Largest share mover: {t['seg']} volume {t['vol_inc']} vs "
                     f"{t['vol_expected']} expected ({t['pct_change']}%).")
        return head, body + _ruled_out_sentence(v) + _baseline_note(bundle)

    if code == "MIX_INTERACTION":
        mx = cause
        head = (f"{label} moved on {mx['dim']}: a segment shifted share AND changed "
                f"rate ({inc['window_start'][:10]})")
        body = (f"{_q1_move(bundle).capitalize()} over {win}. Kitagawa split on "
                f"{mx['dim']}: within {mx['within_effect_pp']} pp, mix "
                f"{mx['mix_effect_pp']} pp, interaction {mx['interaction_pp']} pp of a "
                f"{mx['total_delta_pp']} pp total — the interaction term dominates: a "
                f"segment both shifted its traffic share and changed its own rate.")
        sr = mx.get("segment_row")
        if sr and mx.get("seg"):
            body += (f" Leading segment: {mx['seg']} ({sr.get('val_base')} → "
                     f"{sr.get('val_inc')}, delta {sr.get('delta')}).")
        return head, body + _ruled_out_sentence(v) + _baseline_note(bundle)

    if code == "SEASONAL_CONFIRMED":
        head = (f"{label} ({inc['window_start'][:10]}): expected seasonality — "
                f"measurement agrees with the classifier")
        body = (f"The detector classified this window as seasonal, and the "
                f"weekday-corrected measurement agrees: over {win} vs a same-weekday "
                f"baseline, no lever crosses its threshold")
        gm = v.get("gate_misses")
        if gm:
            body += ": " + "; ".join(gm)
        body += ". The window stays in future baselines as a clean seasonal day."
        return head, body + _baseline_note(bundle)

    if code == "GLOBAL_MOVEMENT":
        head = (f"{_q1_move(bundle).capitalize()} ({inc['window_start'][:10]}) — "
                f"global, no single segment")
        body = (f"{_q1_move(bundle).capitalize()} over {win}, uniformly: no segment in "
                f"any swept dimension explains 50% or more of the move")
        g = v.get("global_evidence") or {}
        if g.get("max_contribution_pp") is not None:
            body += f" (largest single contribution {g['max_contribution_pp']} pp)"
        if g.get("pct_range"):
            body += (f"; per-segment changes run {g['pct_range'][0]}% to "
                     f"{g['pct_range'][1]}%")
        body += "."
        mx = v.get("mix_check")
        if mx:
            body += (f" Kitagawa split confirms within-segment movement dominates "
                     f"(within {mx['within_effect_pp']} pp vs mix {mx['mix_effect_pp']} pp).")
        return head, body + _ruled_out_sentence(v) + _baseline_note(bundle)

    if code == "PEER_OUTLIER":
        seg, dim = cause["seg"], cause["dim"]
        head = f"{label}: {seg} ({dim}) runs {cause['val']} vs peer median {cause['peer_median']}"
        body = (f"Too little clean history for a weekday baseline "
                f"(min_clean_days={bundle['baseline']['min_clean_days']}), so segments "
                f"were compared against sibling medians inside {win}. {seg} ({dim}) runs "
                f"{cause['val']} against a peer median of {cause['peer_median']} "
                f"(deviation {cause['vs_peer']}). Rerunning the other dimensions with "
                f"{seg} excluded returns them to peer-normal. Caveat of the "
                f"history-free path: a peer deviation can be a segment's steady state, "
                f"not a change — treat this as the leading candidate, confirmed only "
                f"against history.")
        return head, body + _ruled_out_sentence(v)

    if code == "NO_PEER_OUTLIER":
        head = f"{label}: no peer outlier found in {inc['window_start'][:10]} window (short history)"
        body = (f"Too little clean history for a weekday baseline "
                f"(min_clean_days={bundle['baseline']['min_clean_days']}); peer "
                f"comparison across segments inside {win} finds no outlier beyond "
                f"threshold. A global-level verdict needs detection's own models.")
        return head, body + _ruled_out_sentence(v)

    if code == "DISAGREEMENT":
        d = (inc.get("detection") or {})
        head = f"{label} ({inc['window_start'][:10]}): detection and measurement disagree — needs human review"
        body = (f"Detection flagged this window (z={d.get('z_score')}, "
                f"change {d.get('pct_change_pct')}%), but the scoped decomposition over "
                f"{win} measures no lever beyond its threshold")
        gm = v.get("gate_misses")
        if gm:
            body += ": " + "; ".join(gm)
        body += (". Both sides' numbers are logged; this is flagged for human eyes, "
                 "not silently closed.")
        return head, body + _baseline_note(bundle)

    if code == "NO_MOVEMENT":
        head = f"{label} ({inc['window_start'][:10]}): nothing moved beyond noise"
        body = (f"Measured over {win} vs the same-weekday baseline, no lever crosses "
                f"its threshold")
        gm = v.get("gate_misses")
        if gm:
            body += ": " + "; ".join(gm)
        body += ". Nothing moved beyond noise; the checked levers and numbers are logged."
        return head, body + _baseline_note(bundle)

    if code == "NO_DATA":
        head = f"{label}: no events in {inc['window_start'][:10]} window for scope {inc['scope']}"
        body = (f"The window {win} (scope {inc['scope']}, dataset "
                f"{inc['dataset']}) contains no events — nothing to measure. If this "
                f"window should have traffic, that absence is itself the finding "
                f"(ingestion gap).")
        return head, body

    if code == "SHORT_HISTORY_VOLUME":
        head = f"{label} ({inc['window_start'][:10]}): volume anomaly on a short slice — baseline unavailable"
        body = (f"min_clean_days={bundle['baseline']['min_clean_days']}: no usable "
                f"same-weekday baseline exists, and peer comparison applies to ratio "
                f"metrics only. Detection's numbers stand; the trace records what was "
                f"measured.")
        return head, body

    head = f"{label}: verdict {code} ({inc['window_start'][:10]})"
    return head, f"Verdict {code} over {win}. See the evidence bundle and trace."
