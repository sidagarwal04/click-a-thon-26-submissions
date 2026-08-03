package anomalydetector

import (
	"testing"
	"time"
)

func TestWindowGrainUsesResolution(t *testing.T) {
	tests := []struct {
		window Window
		want   string
	}{
		{window: Window{Duration: 5 * time.Minute, Resolution: Resolution5m}, want: "minute"},
		{window: Window{Duration: 10 * time.Minute, Resolution: Resolution10m}, want: "minute"},
		{window: Window{Duration: time.Hour, Resolution: Resolution1h}, want: "hourly"},
		{window: Window{Duration: 24 * time.Hour}, want: "daily"},
	}

	for _, test := range tests {
		if got := test.window.Grain(); got != test.want {
			t.Errorf("grain = %q, want %q for %+v", got, test.want, test.window)
		}
	}
}

func TestWindowTargetIsInclusiveStart(t *testing.T) {
	start := time.Date(2026, 6, 23, 0, 0, 0, 0, time.UTC)
	window := Window{Start: start, End: start.Add(24 * time.Hour), Duration: 24 * time.Hour}
	if got := window.Target(); !got.Equal(start) {
		t.Fatalf("window target = %s, want inclusive start %s", got, start)
	}
}
