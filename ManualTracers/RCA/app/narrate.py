import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.grounding import (
    allowed_numbers,
    check_grounding,
    fallback_summary,
    round_floats,
)
from app.settings import get_settings
from app.tracing import traced
from app.utils import content_to_text

logger = logging.getLogger("rca_agent.narrate")

SYSTEM_PROMPT = """You are the narrator stage of an automated root-cause analyst. You never
compute anything and never invent a number — every figure you write must already exist in
the JSON ledger you are given. Copy numbers verbatim; never round beyond the precision given.

Write exactly four sections, in this order, as plain prose paragraphs (no headers, no
bullet lists):

1. What happened — the alerted metric, its window, actual vs expected, and z-score.
2. Which factor — only if "decomposition" is present (revenue-level alerts). Walk the
   revenue identity: state every factor's contribution_rel and verdict
   (implicated/cleared). If decomposition.offsetting is true, say the factors partly
   offset each other and each figure is that factor's own move, not a share of a
   near-zero total. Skip this whole section if "decomposition" is null.
3. Which segment — one paragraph per entry in "findings". For verdict "localized", name
   the candidate dimension/value, its contribution, and that the holdout confirmed it as
   the sole cause (residual close to zero relative to the candidate's own move). For
   "inconclusive", name the top candidate but say the holdout did not confirm it as the
   sole cause — a lead, not a conclusion. For "broad_based", say plainly that factor's
   movement is uniform across every tested dimension — never name a culprit that wasn't
   confirmed. If "interaction" is present with verdict "interaction", the depth-1 cut alone
   did not explain the move: the culprit is the PAIR, so name both the parent cut and
   interaction.child_dim = interaction.top.child_value, give top_share and how many strata
   were tested, and report that pair's own holdout verdict. If "interaction" carries only
   "skipped", say the crossing step did not run and why, in plain words.
4. Checked and ruled out — for each finding, how many candidate dimensions were tested
   (the length of its "candidates" list) and name only the "ruled_out" entries as the
   notable near-misses. Never list every cleared candidate.

Hard rules:
- Never write a number that is not already present in the ledger JSON, at any rounding.
- Do not use thousands separators (write 27370, not 27,370).
- If the top-level "verdict" is "not_reproducible", ignore all the rules above and write
  exactly one sentence: the alert did not reproduce against current data, no finding to
  report.
"""


@traced("narrate")
async def narrate(ledger: dict) -> dict:
    if not ledger.get("findings"):
        return {
            "narrative": fallback_summary(ledger),
            "grounded": True,
            "source": "template",
        }

    settings = get_settings()
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY not set — falling back to templated summary")
        return {
            "narrative": fallback_summary(ledger),
            "grounded": True,
            "source": "template",
        }

    rounded = round_floats(ledger)
    allowed = allowed_numbers(rounded)
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,  # copy numbers verbatim, never embellish
    )
    response = await llm.ainvoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(rounded, default=str)),
        ]
    )
    text = content_to_text(response.content)

    ungrounded = check_grounding(text, allowed)
    if ungrounded:
        logger.warning(
            "ungrounded numbers %s — falling back to templated summary", ungrounded
        )
        return {
            "narrative": fallback_summary(ledger),
            "grounded": False,
            "ungrounded_numbers": ungrounded,
        }

    return {"narrative": text, "grounded": True, "source": "llm"}
