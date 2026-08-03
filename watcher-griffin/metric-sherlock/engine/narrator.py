"""Step 7: Narrate findings. The ONLY module in this codebase that calls an
LLM. Per CLAUDE.md's Guardrails: the LLM restates numbers already present in
the EvidenceBundle, never computes or invents one, and on any failure this
degrades to an explicit "narration unavailable" result rather than a guessed
or templated sentence -- the deterministic evidence is still returned either
way, since that's the part that must always be trustworthy.
"""

import json
from dataclasses import dataclass
from typing import Optional

from engine.evidence import EvidenceBundle
from engine.llm import get_provider

SYSTEM_PROMPT = """You are a root-cause narration assistant for an ad-tech analytics system.

You will be given a JSON evidence bundle already computed by a deterministic ClickHouse-backed pipeline: \
a metric's current value vs its baseline, which factor (requests/fill_rate/ecpm) moved, "drilldown_levels" \
(level 0 = the initial ranking across all dimensions, level 1+ = each recursive drill-down into whichever \
segment kept concentrating the deviation), and a list of checks that were explicitly ruled out with the \
numbers that cleared them. Every segment in drilldown_levels carries a "source_step" field naming the exact \
query that number came from (e.g. "rank:hourly_by_region:current" or "drilldown_raw_fallback:region:current").

Hard rules, non-negotiable:
1. Restate ONLY numbers that appear in the evidence JSON. Never compute a new number, never round in a way \
that changes the value, never estimate or infer a figure that isn't present.
2. If the evidence doesn't contain enough information to explain something, say so plainly instead of guessing.
3. Name the specific segment(s) responsible using the "dimension" and "value" fields given, not a vague \
"something changed."
4. Lead every sentence with what happened and why, in words a non-technical reader would say out loud. Never \
surface internal analysis vocabulary as the explanation itself -- no "sibling values/entities", no "breadth", \
no raw rollup/step names, no bare thresholds standing in for meaning. Translate them: "only 4 of 111 sibling \
values moved, breadth 0.036" becomes "only a handful of similar apps moved, well within normal day-to-day \
noise". A reader with no technical background must be able to read the first clause of every sentence and \
understand what happened without needing to know what a rollup, a query, or a "sibling" is.
5. Still name the source_step behind the key number(s) driving your conclusion -- every claim must trace to a \
real query -- but place it as a short trailing citation AFTER the plain-language claim, never interleaved \
mid-sentence or standing in for the explanation (e.g. "...in the North region (per the \
rank:hourly_by_region:current query)."). The citation is supporting detail for a reader who wants it, not the \
subject of the sentence.
6. Explicitly mention what was checked and ruled out, using the "ruled_out" entries' own reasons and numbers, \
translated into plain language the same way (see rule 4).
7. Style: 2-4 sentences, plain language first, matching this shape: "Revenue fell 12%, mostly because fewer \
ads were showing on Device X in the North region (per the rank:hourly_by_region:current query). Normal \
traffic volume and click-through rates ruled out other explanations. This isn't a broader trend either -- \
only a few similar apps moved, well within normal variation, so day-of-week seasonality was ruled out (per \
the sweep:ad_format:15h:windows query)."
8. If is_anomalous is false, say plainly that this window does not look anomalous rather than inventing a story.

Output only the narration text, nothing else (no preamble, no markdown headers).
"""


@dataclass
class NarrationResult:
    narration: Optional[str]
    available: bool
    provider: str
    error: Optional[str] = None


def narrate(evidence: EvidenceBundle) -> NarrationResult:
    from engine.config import settings
    from engine.tracing import traced_generation

    provider_name = settings.llm_provider.value
    evidence_payload = evidence.to_llm_json()
    # Span wraps the ACTUAL provider call, so the Langfuse timeline shows the
    # real LLM latency -- usually the single slowest step in an investigation.
    with traced_generation("narrator", provider_name, evidence_payload) as span:
        try:
            provider = get_provider(settings)
            text = provider.generate(SYSTEM_PROMPT, json.dumps(evidence_payload, default=str))
            # An empty answer is a FAILED narration, not an available one.
            #
            # `available=True` used to be unconditional on "no exception raised", but a
            # provider can return nothing without erroring: google-genai's
            # `response.text` is None when a response carries no text part (thinking
            # tokens exhausting max_output_tokens, or a safety/recitation stop), and it
            # can equally come back as a bare '\n'. Observed exactly that -- an incident
            # persisted with narration_available=1 and a 1-character narration, which the
            # console then renders as an empty explanation that claims to be one.
            #
            # That inverts the guardrail this module exists to enforce: a failure must be
            # explicit ("narration unavailable") rather than an empty box the reader has to
            # interpret. The deterministic mechanism sentence is unaffected either way --
            # it is computed, not generated -- so saying so costs nothing and hiding it
            # costs trust.
            if text is None or not text.strip():
                reason = "provider returned an empty response (no text part)"
                if span is not None:
                    span.update(output=None, level="ERROR", status_message=reason)
                return NarrationResult(
                    narration=None, available=False, provider=provider_name, error=reason
                )
            if span is not None:
                span.update(output=text)
            return NarrationResult(narration=text, available=True, provider=provider_name)
        except Exception as e:
            # Degrade, never fabricate -- and record WHY on the span so a judge
            # can see narration was attempted and why it didn't happen.
            if span is not None:
                span.update(output=None, level="ERROR", status_message=str(e)[:500])
            return NarrationResult(narration=None, available=False, provider=provider_name, error=str(e))
