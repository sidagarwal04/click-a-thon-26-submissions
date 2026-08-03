# InsightIQ — Pitch deck (draft)

Export this to **`pitch-deck.pdf`** before submission (Google Slides / Keynote / LibreOffice → PDF).

---

## Slide 1 — Title
**InsightIQ** · Team **404Duos**  
From alert to answer — automated root-cause analysis inside ClickHouse  
*Click-a-thon 2026 · InMobi track*  
Vishnu Bhagwat · Sethukumar J

---

## Slide 2 — Problem
- Alerts say *what* moved — teams still spend hours asking *why*
- Manual slice-and-dice across app / device / geo / advertiser
- At InMobi scale, the bottleneck is investigation, not data

---

## Slide 3 — Solution
**Detect → Drill down → Diagnose in seconds**
- ClickHouse-native cascade (baseline → Z-score → multi-dim attribution)
- Deterministic diagnosis + citations
- LLM narrates evidence only (Gemini)
- Langfuse traces for trust

---

## Slide 4 — How it works
1. Seasonality-aware baseline (same hour × 4 weeks)
2. Noise-floored Z-score → high-signal alerts
3. Contribution analysis across 7+ dimensions
4. Ruled-out / seasonality honesty
5. Plain-English diagnosis + chat

---

## Slide 5 — Architecture
ClickHouse Cloud = analytical engine  
Node API = package evidence  
Gemini = narrate  
Langfuse = prove the run  
*(diagram from ARCHITECTURE.md)*

---

## Slide 6 — Demo
Hosted: https://insight-iq-woad.vercel.app  
Alert wall → investigation → diagnosis → chat → Langfuse

---

## Slide 7 — Why us / impact
- Analysis in the warehouse → low egress, high trust
- Explainability over black-box ML
- Built for the **unseen incident** (export + evidence hash + traces)

---

## Slide 8 — Team & ask
**404Duos** — Vishnu Bhagwat · Sethukumar J  
Demo · video · thanks
