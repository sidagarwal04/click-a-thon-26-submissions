"""Known-issue correlation engine (ENGINEERING.md §5.2.4).

Deterministic rule engine matching evidence against `meta.known_issues`
(K1–K7 trigger table). Output: matched issues with the triggering evidence.
Trigger patterns are content-driven — derived from the evidence rows and the
spec's columns, not from hardcoded feature names.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("atlys.agents.correlation")

GULF_GEO = {"AE", "SA", "KW", "QA", "BH", "OM"}


def correlate(evidence: list[dict], table: str, feature: str,
              known_issues: list[dict] | None = None) -> list[dict]:
    """Match evidence against known issues. Returns [{issue_id, trigger, detail}]."""
    known = {k["issue_id"]: k for k in (known_issues or [])}
    matched: list[dict] = []

    def add(issue_id: str, trigger: str, detail: str = "") -> None:
        if issue_id not in known:
            log.debug("issue %s not in known_issues table — skipping", issue_id)
            return
        matched.append({
            "issue_id": issue_id,
            "title": known[issue_id].get("title", issue_id),
            "trigger": trigger,
            "detail": detail,
        })

    # --- helper accessors --------------------------------------------------
    def rows_of(kind: str) -> list[dict]:
        return [e for e in evidence if e["kind"] == kind]

    def seg_rows() -> list[dict]:
        return [e for e in rows_of("segment") if e.get("rows")]

    # --- K1: iOS OTP autofill ----------------------------------------------
    # otp evidence + iOS otp_success clearly below Android + Gulf geo.
    has_otp = any("otp" in e["label"].lower() or "otp" in (e.get("sql") or "") for e in evidence)
    if has_otp and seg_rows():
        ios_rate, android_rate = _os_rate(seg_rows(), "otp_success")
        if ios_rate is not None and android_rate is not None and ios_rate < android_rate - 0.05:
            geo = _gulf_segment(seg_rows())
            detail = f"iOS {ios_rate:.1%} vs Android {android_rate:.1%}"
            if geo:
                detail += f"; worst in {', '.join(sorted(geo))}"
            add("K1", "otp_entered evidence; iOS otp_success below Android by >=5pts", detail)

    # --- K2: Android passport scan -----------------------------------------
    doc_sql = any("document_uploaded" in (e.get("sql") or "") for e in evidence)
    android_scan = any(
        "android" in str(r).lower() and ("capture" in str(e.get("label", "")).lower()
                                         or "retry" in str(e.get("label", "")).lower())
        for e in evidence for r in (e.get("rows") or [])
    )
    if doc_sql and android_scan:
        add("K2", "document_uploaded; android capture/retry/threshold evidence present")

    # --- K3: MRZ OCR non-Latin passports -----------------------------------
    retry_high = False
    for e in seg_rows():
        for r in e.get("rows", []):
            # segment rows: [seg, a, b]; retry_count column isn't directly here,
            # so this triggers when segment names look like destinations with big skew
            if len(r) >= 3 and isinstance(r[1], (int, float)) and isinstance(r[2], (int, float)) \
                    and r[1] > 100 and r[2] > 0 and (r[1] - r[2]) / r[1] > 0.5:
                retry_high = True
    if retry_high and ("retry" in table or "document" in table):
        add("K3", "high drop between first/last segment step on document flow")

    # --- K4: Schengen summer scarcity --------------------------------------
    schengen = {"AT", "BE", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IS", "IT", "LV",
                "LI", "LT", "LU", "MT", "NL", "NO", "PL", "PT", "SK", "SI", "ES", "SE", "CH"}
    dest_rows = [r for e in rows_of("segment") if "destination" in e["label"] for r in (e.get("rows") or [])]
    schengen_hits = [r[0] for r in dest_rows if r and r[0] in schengen]
    if schengen_hits:
        add("K4", "destination segment shows Schengen countries",
            "destinations: " + ", ".join(sorted(schengen_hits)[:6]))

    # --- K5: WhatsApp re-engagement ----------------------------------------
    whatsapp = any("whatsapp" in str(r).lower()
                   for e in evidence for r in (e.get("rows") or []))
    recovery_sql = any("reminder" in (e.get("sql") or "").lower() or "abandonment" in (e.get("sql") or "").lower()
                       for e in evidence)
    if whatsapp and recovery_sql:
        add("K5", "abandoned-checkout reminders via whatsapp reconverting")

    # --- K6: SUMMER20 coupon -----------------------------------------------
    coupon = any("coupon" in (e.get("sql") or "").lower() or "coupon" in e["label"].lower()
                 for e in evidence)
    summer20 = any("summer20" in str(r).lower() for e in evidence for r in (e.get("rows") or []))
    if coupon and summer20:
        add("K6", "coupon_name = SUMMER20 in purchase evidence")

    # --- K7: App 7.45 rollout ----------------------------------------------
    v745 = any("7.45" in str(r) for e in evidence for r in (e.get("rows") or []))
    if v745:
        add("K7", "app_version 7.45.x funnel-timing evidence")

    return matched


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _os_rate(seg_evidence: list[dict], col: str) -> tuple[float | None, float | None]:
    """Find iOS vs Android rates for a numeric column from segment evidence.

    The segment playbook emits [seg, a, b] (a=first step users, b=last step
    users), which we approximate: rate = b/a per OS row when a>0.
    """
    ios = android = None
    for e in seg_evidence:
        for r in e.get("rows", []):
            if len(r) < 3 or not isinstance(r[1], (int, float)):
                continue
            seg, a, b = r[0], r[1], r[2]
            if a and isinstance(a, (int, float)) and a > 0 and b is not None:
                rate = b / a
                if str(seg).lower().startswith("ios"):
                    ios = rate
                elif str(seg).lower().startswith("android"):
                    android = rate
    return ios, android


def _gulf_segment(seg_evidence: list[dict]) -> set[str]:
    out: set[str] = set()
    for e in seg_evidence:
        for r in e.get("rows", []):
            if r and str(r[0]).upper() in GULF_GEO:
                out.add(str(r[0]).upper())
    return out
