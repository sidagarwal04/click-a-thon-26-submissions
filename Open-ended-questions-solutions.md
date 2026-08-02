###Agent Input Questions:
"Analyze the existing funnel and surface the most important issues, with the why."
"Where are we losing conversions, and for which segments (device / geo / destination)?"
"Are there any regressions or trends over the last quarter?"
"Is anything in the base context wrong, stale, or self-contradictory?"

###Agent Output from context store:
**Short answer:** The context doesn’t contain actual funnel data, so I can’t quantify losses or confirm regressions.

**Main hypotheses:**
- **iOS payment drop-off:** OTP autofill issue, especially Gulf/payment-heavy users.
- **Android document-upload drop-off:** passport model update may have increased failures.
- **Non-Latin passports:** more OCR retries.
- **Schengen:** Apr–Jun softness may be seasonal slot scarcity, not a bug.

**Context issues:**
- Conversion is defined two ways: purchases ÷ sessions vs. purchases ÷ applications started.
- `visa_issuance_eta_days` is documented but missing from the listed event schema.
- User-level and application-level funnel grains are mixed.

**Evidence:** context version `1`; chunks `4a901821` (`0.5809`), `c223b6cc` (`0.5079`), `eba26400` (`0.7724`).
 
