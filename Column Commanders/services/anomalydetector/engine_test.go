package anomalydetector

import (
	"testing"
	"time"
)

func TestParseDataAnchor(t *testing.T) {
	tests := []struct {
		input string
		want  time.Time
	}{
		{
			input: "2026-07-05 23:59:59",
			want:  time.Date(2026, 7, 5, 23, 59, 59, 0, time.UTC),
		},
		{
			input: "2026-07-05 23:59:59.123",
			want:  time.Date(2026, 7, 5, 23, 59, 59, 123000000, time.UTC),
		},
		{
			input: "2026-07-05",
			want:  time.Date(2026, 7, 5, 0, 0, 0, 0, time.UTC),
		},
	}
	for _, test := range tests {
		got, err := parseDataAnchor(test.input)
		if err != nil {
			t.Fatalf("parse %q: %v", test.input, err)
		}
		if !got.Equal(test.want) {
			t.Errorf("parse %q = %s, want %s", test.input, got, test.want)
		}
	}
}
