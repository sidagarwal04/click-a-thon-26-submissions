package investigation

import (
	"testing"
	"time"
)

func TestFormatWindowParameterWorksForDateTimeAndDateTime64(t *testing.T) {
	value := time.Date(2026, time.July, 4, 17, 0, 0, 123000000, time.FixedZone("offset", 5*60*60+30*60))
	if got, want := formatWindowParameter(value), "2026-07-04 11:30:00"; got != want {
		t.Fatalf("formatWindowParameter() = %q, want %q", got, want)
	}
}
