package mock

import (
	"net/http/httptest"
	"reflect"
	"testing"
)

// Every field of fleet.Filter must be reachable from the query string.
//
// This exists because it was not. Mode was added to the struct and to the
// matcher, but fleetFilter is a hand-written mapping and did not learn about it —
// so `POST /api/fleet/bulk?mode=manual` silently ignored the filter and ended
// 103,470 sessions instead of 3,470. A bulk endpoint that quietly widens its own
// scope is the worst shape that bug could have taken.
//
// Reflection rather than a field-by-field list, because a hand-written assertion
// is the same kind of thing that failed in the first place: it would have needed
// updating by the same person who forgot to update the parser.
func TestFleetFilterParsesEveryField(t *testing.T) {
	// One distinctive value per field. Ints get digits, strings get text.
	values := map[string]string{
		"content_id":  "4242",
		"video_type":  "LIVE",
		"platform":    "FIRETV",
		"app_version": "9.9.9",
		"country":     "india",
		"phase":       "paused",
		"mode":        "autonomous",
	}

	qs := ""
	for k, v := range values {
		if qs != "" {
			qs += "&"
		}
		qs += k + "=" + v
	}
	r := httptest.NewRequest("GET", "/api/fleet/sessions?"+qs, nil)

	got := fleetFilter(r)
	rv := reflect.ValueOf(got)
	rt := rv.Type()

	if rt.NumField() != len(values) {
		t.Fatalf("fleet.Filter has %d fields but this test supplies %d query values — "+
			"a field was added without a query parameter, or vice versa",
			rt.NumField(), len(values))
	}
	for i := 0; i < rt.NumField(); i++ {
		if rv.Field(i).IsZero() {
			t.Errorf("filter field %s stayed zero: fleetFilter does not read it from the query",
				rt.Field(i).Name)
		}
	}
}
