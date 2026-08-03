package otelemit_test

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/d-cryptic/clickathon/internal/otelemit"
)

// TestAttrConstructorsEncodeTheTaggedUnion pins that each constructor sets
// exactly one arm of the OTLP AnyValue union — a value that sets none (or two)
// ingests as an empty attribute in ClickStack with no error anywhere.
func TestAttrConstructorsEncodeTheTaggedUnion(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name string
		attr otelemit.KeyValue
		want string
	}{
		{"string", otelemit.StringAttr("stage", "session_intervals"), `{"key":"stage","value":{"stringValue":"session_intervals"}}`},
		{"bool", otelemit.BoolAttr("healthy", true), `{"key":"healthy","value":{"boolValue":true}}`},
		{"bool false survives omitempty", otelemit.BoolAttr("pass", false), `{"key":"pass","value":{"boolValue":false}}`},
		{"float", otelemit.FloatAttr("lag_s", -90.5), `{"key":"lag_s","value":{"doubleValue":-90.5}}`},
		{"int is a string", otelemit.IntAttr("rows", 121492), `{"key":"rows","value":{"intValue":"121492"}}`},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			b, err := json.Marshal(tc.attr)
			if err != nil {
				t.Fatalf("Marshal error = %v", err)
			}
			if string(b) != tc.want {
				t.Errorf("encoded attr = %s, want %s", b, tc.want)
			}
		})
	}
}

func TestSeverityNumberMapsPerOTLPSpec(t *testing.T) {
	t.Parallel()
	cases := []struct {
		text string
		want int
	}{
		{otelemit.SeverityInfo, 9},
		{otelemit.SeverityWarn, 13},
		{otelemit.SeverityError, 17},
		// Anything unrecognized degrades to info rather than 0 ("unspecified"),
		// which HyperDX renders as a blank severity.
		{"debug", 9},
		{"", 9},
	}
	for _, tc := range cases {
		if got := otelemit.SeverityNumber(tc.text); got != tc.want {
			t.Errorf("SeverityNumber(%q) = %d, want %d", tc.text, got, tc.want)
		}
	}
}

func TestLogRecordCarriesBodySeverityAndTraceCorrelation(t *testing.T) {
	t.Parallel()
	attrs := []otelemit.KeyValue{otelemit.BoolAttr("pass", false)}
	rec := otelemit.Log("1785063360000000000", otelemit.SeverityError, "reconcile gate: FAIL", attrs, "0123456789abcdef0123456789abcdef", "0123456789abcdef")

	if rec.SeverityNumber != 17 {
		t.Errorf("SeverityNumber = %d, want 17 — Log must derive it from the text", rec.SeverityNumber)
	}
	if rec.Body.StringValue == nil || *rec.Body.StringValue != "reconcile gate: FAIL" {
		t.Errorf("Body = %+v, want the message as a stringValue", rec.Body)
	}
	if rec.TraceID == "" || rec.SpanID == "" {
		t.Error("trace correlation ids dropped — logs must join to the observe run's trace")
	}

	b, err := json.Marshal(rec)
	if err != nil {
		t.Fatalf("Marshal error = %v", err)
	}
	for _, field := range []string{`"timeUnixNano":"1785063360000000000"`, `"severityText":"error"`, `"severityNumber":17`, `"traceId":`, `"spanId":`} {
		if !strings.Contains(string(b), field) {
			t.Errorf("encoded log record missing %s:\n%s", field, b)
		}
	}
}

// TestGaugeMetricShape: the only metric shape this package emits is a gauge;
// a Metric with a nil Gauge would serialize as a named metric with no data.
func TestGaugeMetricShape(t *testing.T) {
	t.Parallel()
	p1 := otelemit.Point("1", 1, otelemit.StringAttr("stage", "session_intervals"))
	p2 := otelemit.Point("2", 2, otelemit.StringAttr("stage", "cc_minute_delta"))
	m := otelemit.GaugeMetric("sonyliv.build.stage_duration_seconds", "desc", "s", p1, p2)

	if m.Gauge == nil {
		t.Fatal("Gauge is nil — GaugeMetric must always attach the gauge arm")
	}
	if len(m.Gauge.DataPoints) != 2 {
		t.Fatalf("len(DataPoints) = %d, want 2", len(m.Gauge.DataPoints))
	}
	if m.Name != "sonyliv.build.stage_duration_seconds" || m.Unit != "s" {
		t.Errorf("metric name/unit = %q/%q, want name and unit preserved", m.Name, m.Unit)
	}
	if got := m.Gauge.DataPoints[0]; got.AsDouble == nil || *got.AsDouble != 1 || len(got.Attributes) != 1 {
		t.Errorf("first point = %+v, want asDouble=1 with its stage attribute", got)
	}
}
