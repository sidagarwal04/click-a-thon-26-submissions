"""LLM narration — the only place an LLM touches this pipeline. It receives a
JSON object built entirely from ClickHouse aggregate results (see
pipeline._build_payload) and is instructed to narrate strictly from those
numbers, never to compute or invent new ones.

Bounded by a hard timeout (settings.narrate_timeout_seconds): free-tier rate-
limit retries can otherwise push this one call's tail latency to ~80s (see
rca/latency.py's measured p99), which would make the *diagnosis* dependent on
the one non-deterministic, rate-limited part of an otherwise fast, all-
ClickHouse pipeline. Past the timeout, narrate() falls back to a deterministic,
template-built summary from the same payload -- every number in it already
existed before the LLM was ever called, so a diagnosis is always returned
within the bound regardless of what the LLM does.
"""

import concurrent.futures
import json

from google import genai
from google.genai import types

from . import attribution
from .config import settings
from .tracing import Tracer

SYSTEM_PROMPT = """You are the narration layer of an automated root-cause analyst for ad-tech metrics.
You will receive a JSON object containing ONLY numbers and labels already computed by deterministic
ClickHouse queries: the anomaly that was detected, a decomposition of the revenue identity
(revenue = requests x fill_rate x render_rate x eCPM/1000) into its factors, and a ranked list of
dimension segments that were checked — split into ones that explain a meaningful share of the movement
and ones that were checked and ruled out (low explanatory power or too small a volume share to matter).

Each segment carries a `lift` value: lift = explanatory_power / volume_share, i.e. how much more of the
movement this segment explains than its size alone would predict. lift near 1 means the segment moved
exactly in proportion to everyone else (not a distinct cause, just following a broad/uniform effect);
lift well above 1 (the pipeline requires >= ~1.8 before calling a segment "primary") means it is
genuinely disproportionate and localized. `primary_segments` (a list, possibly empty) holds every
dimension per drill level that cleared that bar — usually one, but sometimes two independent dimensions
(e.g. a device-driven cause and a separate geography-driven cause) each disproportionately explain part
of the same movement. `deeper` is a list index-aligned with `primary_segments`: `deeper[i]` (if present)
is that branch's own further drill-down within `primary_segments[i]`'s filter.

Rules:
- Cite only numbers that literally appear in the JSON. Never invent, estimate, or extrapolate a figure.
- State the metric, the direction and size of the move, and which factor(s) drove it.
- If a drill level's primary_segments is non-empty, name EVERY segment in it (e.g. "device_model=iPhone
  13" and, separately, "country=DE" if both are present), each backed by its own lift and
  explanatory_power, and go one level deeper within each one that has a corresponding `deeper` entry
  (e.g. "...within iPhone 13, further concentrated in region=NAM"). Treat multiple entries as
  independent, coexisting causes, not alternatives to pick between.
- If primary_segments is empty at a level, say plainly that the movement was broad-based / proportional
  across segments at that level (cite one segment's lift near 1 as evidence), rather than forcing a cause.
- Explicitly name at least one dimension or segment that was checked and ruled out, citing its number.
- Plain language. No markdown headers, no bullet points. Under 150 words (if there are multiple
  independent causes to cover, prioritize naming all of them over elaborating on any single one).
"""


def _fallback_narrative(payload: dict) -> str:
    """Template-built summary from the same numbers the LLM would have
    narrated, used when narrate() times out or the call otherwise fails.
    Deliberately labeled as auto-generated rather than passed off as the
    LLM's own phrasing -- "Honest" applies to the system's own behavior,
    not just the numbers it cites."""
    anomaly = payload["anomaly"]
    decomp = payload["revenue_decomposition"]
    drill = payload["drill_down"]
    metric = anomaly["metric"]
    metric_label = metric.replace("_", " ")

    rel = attribution.metric_rel_delta(metric, decomp)
    if rel is None:
        lines = [f"{metric_label.capitalize()} moved outside its expected baseline "
                 f"({anomaly['current_window'][0]} to {anomaly['current_window'][1]})."]
    else:
        direction = "increased" if rel >= 0 else "decreased"
        lines = [f"{metric_label.capitalize()} {direction} by {abs(rel) * 100:.1f}% "
                 f"({anomaly['current_window'][0]} to {anomaly['current_window'][1]}, "
                 f"vs baseline {anomaly['baseline_window'][0]} to {anomaly['baseline_window'][1]})."]

    drill_factor = drill.get("factor")
    if drill_factor and drill_factor != metric:
        contributions = decomp.get("factor_contributions_to_revenue_delta") or {}
        revenue_delta = decomp.get("revenue_delta") or 0
        contrib = contributions.get(drill_factor)
        if contrib is not None and revenue_delta:
            pct_of_total = abs(contrib / revenue_delta) * 100
            lines.append(f"LMDI decomposition attributes {pct_of_total:.0f}% of the "
                         f"revenue movement to {drill_factor.replace('_', ' ')}.")

    chains = attribution.segment_chains(drill)
    if chains:
        for chain in chains:
            path = " -> ".join(f"{s['dimension']}={s['value']}" for s in chain)
            last = chain[-1]
            lines.append(
                f"Drill-down localizes part of this to {path}, explaining "
                f"{last['explanatory_power'] * 100:.0f}% of the movement at that level "
                f"with a lift of {last['lift']:.1f}x over its size."
            )
    else:
        lines.append(
            "Drill-down found no single segment disproportionately responsible -- "
            "the movement was broad-based, proportional to segment size across every dimension checked."
        )

    lines.append(
        "[Auto-generated summary — LLM narration was unavailable or timed out; every "
        "figure above is the same deterministic computation the full narrative would have used.]"
    )
    return " ".join(lines)


def narrate(payload: dict, tracer: Tracer) -> str:
    client = genai.Client(api_key=settings.gemini_api_key)
    user_content = json.dumps(payload, indent=2, default=str)

    def _call():
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=1024,
                # This step only narrates numbers ClickHouse already computed, not
                # a reasoning task — full thinking mode burned the whole token
                # budget on internal thought tokens (~40s latency) before writing
                # any answer. MINIMAL keeps latency down to a couple of seconds,
                # matching the "diagnosed in seconds" requirement.
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
            ),
        )

    with tracer.span("narrate", input=payload, as_type="generation", model=settings.gemini_model) as span:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_call)
        try:
            response = future.result(timeout=settings.narrate_timeout_seconds)
            text = response.text
            span.set_output(text)
            return text
        except Exception as e:
            text = _fallback_narrative(payload)
            span.set_output({"fallback_reason": str(e), "narrative": text})
            return text
        finally:
            # wait=False: don't block here on a call we've already given up on
            # (e.g. still retrying inside the SDK past our own timeout) -- that
            # would silently reintroduce the exact tail latency this is meant
            # to bound. The orphaned thread finishes or errors on its own;
            # nothing here depends on its result once we've moved on.
            executor.shutdown(wait=False)
