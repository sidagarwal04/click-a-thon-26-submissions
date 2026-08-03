# Probe 2 — Conversion loss by segment

**Prompt (paste verbatim into the Analytics Agent, new conversation):**

> Where are we losing conversions, and for which segments (device / geo / destination)?

**Langfuse trace:** `<PASTE LINK>`

**Model:** opus-4.x via LiteLLM  ·  **Context version at run time:** `<vN>`

---

## Agent output (paste the PM-ready response below)

<!-- Paste the Analytics Agent's full answer here. It should include, per insight:
Headline / Evidence (numbers + window + metric def) / Why (context-linked, hedged) /
Confidence (H·M·L + reason) / Suggested next step. Expect device/geo/destination cuts. -->

```
{
  "spec": "02_group_family",
  "context_version": 8,
  "generated_at": "2026-08-07T00:00:00Z",
  "trace_url": null,
  "trace_url_note": "Langfuse trace URL not programmatically obtainable from this agent runtime; set to null per protocol.",
  "insights": [
    {
      "id": "GF-I1",
      "headline": "Group completion rate drops from 69% (pairs) to 31% (6-person groups) — larger groups need a streamlined submission flow.",
      "evidence": "Across 1,200 groups (Jun 8–28 2026): size-2 groups complete at 69.5% (330/475), size-3 at 58.7%, size-4 at 50.4%, size-5 at 38.6%, size-6 at 31.1% (28/90). The decline is monotonic and steep — each additional traveller costs roughly 10 pp of completion.",
      "why": "Larger groups amplify per-traveller friction (docs, data entry) multiplicatively. The docs-incomplete share rises only modestly with size (18.9%→21.6%), so the bottleneck is likely coordination overhead — managing multiple travellers within one session — rather than any single traveller's document readiness. This is consistent with K7 (app 7.45 rollout) which introduced minor timing shifts but did not specifically address multi-traveller UX.",
      "confidence": 0.90,
      "confidence_label": "High",
      "confidence_reason": "Strong monotonic pattern across 5 size buckets with adequate sample sizes (smallest bucket: 90 groups at size-6). Weekly trend is stable (completion 56–61%), ruling out a temporal artifact.",
      "related_known_issues": ["K7"],
      "related_metrics": ["group_completion_rate", "docs_incomplete_share"],
      "suggested_next_step": "Prioritize a 'group progress tracker' UX for groups ≥ 4 (where completion drops below 50%) — e.g. a checklist showing each traveller's doc status — and A/B test its impact on size-4+ completion."
    },
    {
      "id": "GF-I2",
      "headline": "Document incompleteness is a steady ~20% friction across all group sizes — not the driver of the size-dependent completion drop.",
      "evidence": "Docs-incomplete share by group_size: 18.9% (size-2), 19.5% (size-3), 19.7% (size-4), 22.2% (size-5), 21.6% (size-6). Flat within ±3 pp. Groups that did NOT submit had avg 0.65 incomplete travellers vs 0.53 for submitted groups — a modest gap, not a cliff. Non-submitted groups also averaged 3.21 travellers vs 2.69 for submitted ones, confirming size matters more than per-traveller doc friction.",
      "why": "Per-traveller document completion is a constant background friction (~1 in 5 travellers has incomplete docs at add-time) rather than a size-scaling bottleneck. The real size-dependent factor appears to be group coordination complexity. By destination, AE has the highest docs-incomplete share (24.2%) and TH the lowest (16.5%), possibly reflecting destination-specific document requirements (K3: non-Latin passport OCR issues may contribute for some corridors).",
      "confidence": 0.85,
      "confidence_label": "High",
      "confidence_reason": "Consistent pattern across 5 group sizes and 10 destinations. The submitted-vs-not comparison on 1,200 groups provides a clear signal. Mild caveat: docs_complete reflects state at add-time and may change before submission.",
      "related_known_issues": ["K3"],
      "related_metrics": ["docs_incomplete_share", "group_completion_rate"],
      "suggested_next_step": "Investigate whether docs_complete status updates after traveller-add (i.e., do users fix docs before submitting?). If many travellers remain incomplete at submission, build a 'complete docs for all travellers' nudge before the submit button activates."
    },
    {
      "id": "GF-I3",
      "headline": "Traveller churn is negligible overall (2%) but 20× higher in size-5+ groups — a signal of group-composition uncertainty in large parties.",
      "evidence": "Overall 70 removals across 3,495 adds (2.0%). By size: size-2 churn 0.2%, size-3 2.1%, size-4 1.6%, size-5 4.4%, size-6 3.5%. Groups of 5+ have churn rates 16–22× that of pairs. By OS, churn is uniform (iOS 2.0%, Android 2.0%, macOS 2.7%), so this is not a platform UX issue.",
      "why": "Larger travel parties likely face more uncertainty about who is actually joining the trip. The add-then-remove pattern in size-5/6 groups suggests users are 'trying out' group compositions. This friction compounds the coordination overhead that already depresses completion rates for large groups.",
      "confidence": 0.70,
      "confidence_label": "Medium",
      "confidence_reason": "The relative difference is clear (20×), but absolute removal counts are small (22 removals at size-5, 16 at size-6), limiting statistical power. The pattern is directionally consistent with the completion-rate finding.",
      "related_known_issues": [],
      "related_metrics": ["traveller_churn", "group_completion_rate"],
      "suggested_next_step": "For groups ≥ 5, consider a 'confirm your group' step before entering traveller details — let users finalize who is travelling first, reducing wasted data-entry on travellers who get removed."
    },
    {
      "id": "GF-I4",
      "headline": "Top 3 group-application destinations (TH, MY, US) account for 26% of volume but show divergent completion rates — ID and GB outperform on conversion.",
      "evidence": "Top destinations by groups started: TH 112 (50.9% completion), MY 103 (55.3%), US 100 (52.0%), TR 89 (56.2%), AE 88 (53.4%). Meanwhile ID (82 groups) converts at 64.6% and GB (87 groups) at 60.9% — 10–15 pp above the top-3 destinations. Across destinations, completion is uniformly distributed (range 50.9%–64.6%), with no severe outlier, but the gap between best and worst is meaningful at ~14 pp.",
      "why": "Destination-specific factors likely drive the gap: visa complexity, required document count, and processing time expectations all vary. TH's below-average completion despite highest volume may reflect the K4 Schengen-summer-slots effect indirectly — while TH is not Schengen, summer leisure destinations see demand spikes that stress the application flow. ID and GB may have simpler group-visa requirements. AE's high docs-incomplete share (24.2%) coincides with its mid-tier completion rate.",
      "confidence": 0.65,
      "confidence_label": "Medium",
      "confidence_reason": "Completion-rate differences across destinations are moderate (14 pp range) and per-destination sample sizes are 70–112 groups — sufficient for directional insight but not for statistical significance testing. Causal attribution to visa complexity is informed conjecture.",
      "related_known_issues": ["K4"],
      "related_metrics": ["group_apps_by_destination", "group_completion_rate", "docs_incomplete_share"],
      "suggested_next_step": "For TH (highest volume, below-avg completion): investigate whether the group flow surfaces destination-specific document requirements early enough. Consider destination-aware onboarding that sets expectations for required docs per traveller before group creation."
    }
  ]
}
```
