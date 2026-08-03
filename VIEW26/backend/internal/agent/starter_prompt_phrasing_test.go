package agent

import "testing"

// Mirrors app/product-workspace.tsx pmPromptByIntent: each generated starter
// prompt must classify back to the intent it was generated from.
func TestStarterPromptPhrasingsClassifyToIntent(t *testing.T) {
	feature := "Express Checkout"
	cases := map[string]string{
		"conversion_comparison":     "Is " + feature + " actually lifting end-to-end conversion versus the standard flow, and how many percentage points is it worth?",
		"platform_failure":          "Where are " + feature + " users failing at OTP or payment, and which device and OS cohorts should engineering prioritise first?",
		"completion_trend":          "How has " + feature + " completion trended week over week since launch — is momentum building or flattening out?",
		"segment_comparison":        "Which cities and devices show the strongest " + feature + " completion, and how wide is the gap between the best and weakest segments?",
		"feature_adoption":          "Which traveller segments are adopting " + feature + " the most, and where is adoption still lagging behind?",
		"funnel_diagnosis":          "Where in the " + feature + " funnel are we losing the most users before payment, and which drop should we fix first?",
		"latency_performance":       "Is " + feature + " actually faster for returning travellers, and how much time does it save at checkout?",
		"customer_geography":        "Where are our " + feature + " customers coming from — which cities and locations drive the most volume?",
		"group_size_completion":     "Which group sizes complete best for " + feature + ", and where do larger groups fall off before payment?",
		"group_traveller_churn":     "How often are travellers removed from " + feature + " applications before completion, and what is that churn costing us?",
		"group_document_bottleneck": "Is document completion the biggest bottleneck for " + feature + " groups, and which step stalls them the longest?",
		"group_segments":            "Which destinations drive the most group demand for " + feature + ", and how do those segments differ in completion?",
	}
	for intent, prompt := range cases {
		if got := ClassifyIntent(prompt); got != intent {
			t.Errorf("prompt for %s classified as %s: %q", intent, got, prompt)
		}
	}

	recoveryFeature := "Abandoned Checkout Recovery"
	recoveryCases := map[string]string{
		"recovery_channel":  "Which channels recover the most abandoned checkouts for " + recoveryFeature + ", and how strong is their open → click follow-through?",
		"recovery_timing":   "Which reminder timing recovers the most " + recoveryFeature + " checkouts — within 1h, 24h, or 48h of drop-off?",
		"recovery_drop_step": "Which checkout step is the largest recoverable revenue opportunity for " + recoveryFeature + "?",
		"recovery_segments": "Which device and geo segments respond best to " + recoveryFeature + " outreach, and where is it wasted?",
	}
	for intent, prompt := range recoveryCases {
		if got := recoveryIntent(prompt); got != intent {
			t.Errorf("recovery prompt for %s classified as %s: %q", intent, got, prompt)
		}
	}
}
