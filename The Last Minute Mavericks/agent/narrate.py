"""agent/narrate.py — turn one investigation (from run_incident's bundle) into a plain-English
diagnosis. The LLM narrates ONLY from evidence: it must write every number as a {{ev_N}} placeholder,
we resolve those to the computed values, and a validator REJECTS any number the LLM invents. If the
LLM is unavailable or keeps hallucinating, a deterministic template writes the diagnosis from the
same evidence. Either way the diagnosis is always grounded — a fabricated figure is impossible.
"""
import re

def _seg_label(c):
    """Full segment label: '{dim}={value}' for 1-D, the interaction string as-is for 2-D."""
    return c["segment"] if "×" in c.get("dimension", "") else f"{c['dimension']}={c['segment']}"

def _facts(inv):
    """LLM-safe facts: labels + values only, never raw rows."""
    c = inv.get("culprit")
    lines = [f"metric: {inv['metric']}",
             f"window: {inv['window'][0]} to {inv['window'][1]}",
             f"verdict: {inv['verdict']}"]
    lines.append(f"culprit segment: {_seg_label(c)} (deviation {c['deviation_pct']}%)" if c
                 else "culprit: none — the move is uniform across segments (global/unlocalized)")
    lines.append("funnel factors checked:")
    for d in inv["decomposition"]:
        lines.append(f"  - {d['factor']}: {d['deviation_pct']}% ({d['verdict']})")
    if inv.get("ruled_out"):
        lines.append("look-alikes ruled out: " +
                     ", ".join(f"{r['segment']} {r['deviation_pct']}%" for r in inv["ruled_out"][:4]))
    evidence = "\n".join(f"  {{{{{e['id']}}}}} = {e['value']}   ({e['label']})" for e in inv["evidence"])
    return "\n".join(lines), evidence

PROMPT = """You are an ad-metrics root-cause analyst. Write a 2–3 sentence diagnosis of the incident below.
State ONLY: (1) which metric moved and by how much, in which segment — or that it is global with no
single segment; (2) which sibling factors were checked and found normal (ruled out).
Do NOT invent causal links between factors, and do NOT add any interpretation beyond the evidence.
HARD RULE: every metric NUMBER must be written as its {{ev_N}} placeholder, exactly as shown, with
the double braces — never write a raw number. Segment names (e.g. an OS version) are written normally.
Plain and precise. No preamble.

FACTS:
%%FACTS%%

EVIDENCE (use these exact placeholders for all metric numbers):
%%EVIDENCE%%

Diagnosis:"""

def _allowed_numbers(facts, evidence):
    """Numbers the narration is allowed to contain: everything in the facts/evidence (segment
    version numbers, deviations, evidence values). Anything else is a hallucination."""
    return set(re.findall(r"\d+\.?\d*", facts + "\n" + evidence))

def _resolve_and_validate(text, inv, facts, evidence):
    evmap = {e["id"]: str(e["value"]) for e in inv["evidence"]}
    out = text
    for eid, val in evmap.items():
        out = out.replace("{{" + eid + "}}", val)
    if re.search(r"\{\{?\s*ev_", out) or "{{" in out or "}}" in out:  # leaked/unresolved placeholder
        return None
    allowed = _allowed_numbers(facts, evidence) | set(evmap.values())
    for num in re.findall(r"\d+\.?\d*", out):
        if num not in allowed:            # a bare number not from evidence/facts = invented
            return None
    return out.strip()

def _template(inv):
    """Deterministic fallback — always grounded in the evidence."""
    c = inv.get("culprit")
    drv = next((d for d in inv["decomposition"] if d["verdict"] == "driver"), None)
    dev = f"{drv['deviation_pct']}%" if drv else "abnormally"
    ruled = [d["factor"] for d in inv["decomposition"] if "ruled out" in d["verdict"]]
    if not c:
        return (f"{inv['metric']} moved {dev} uniformly across all segments — there is no single "
                f"responsible segment; the change is global (unlocalized).")
    s = f"{inv['metric']} moved {dev} at {_seg_label(c)}, which is the primary driver."
    if ruled:
        verb = "was" if len(ruled) == 1 else "were"
        s += f" {', '.join(ruled)} {verb} normal over the same window — ruled out."
    return s

def narrate(inv, cfg, model="gpt-4o-mini"):
    """Return {diagnosis, citations, source}. LLM+validator if possible, else deterministic template."""
    facts, evidence = _facts(inv)
    # CLAUDE.md's connection block names the team-standard variable LLM_API_KEY; accept either, or
    # the LLM path stays dark and every diagnosis silently comes out of _template() instead.
    key = cfg.get("OPENAI_API_KEY") or cfg.get("LLM_API_KEY")
    if key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key)
            prompt = PROMPT.replace("%%FACTS%%", facts).replace("%%EVIDENCE%%", evidence)
            for _ in range(2):            # one retry on hallucination
                r = client.chat.completions.create(
                    model=model, temperature=0,
                    messages=[{"role": "user", "content": prompt}])
                final = _resolve_and_validate(r.choices[0].message.content, inv, facts, evidence)
                if final:
                    cites = re.findall(r"\{\{(ev_\d+)\}\}", r.choices[0].message.content)
                    return {"diagnosis": final, "citations": sorted(set(cites)), "source": "llm+validator"}
        except Exception:
            pass
    return {"diagnosis": _template(inv),
            "citations": [e["id"] for e in inv["evidence"]], "source": "deterministic"}
