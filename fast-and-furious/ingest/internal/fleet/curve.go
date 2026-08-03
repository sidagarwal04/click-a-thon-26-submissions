package fleet

import (
	"time"
)

// CurvePoint is one minute of the fleet's own activity record.
type CurvePoint struct {
	Minute time.Time `json:"minute"`
	// Sessions is the any-overlap count: sessions active for at least one
	// millisecond of the minute. This is peak-style concurrency, and it is what
	// "concurrent viewers" normally means.
	Sessions uint64 `json:"sessions"`
	// ActiveMS is the summed active milliseconds inside the minute. Dividing by
	// 60,000 gives average concurrency, which is always ≤ Sessions.
	//
	// Carried alongside the count rather than instead of it because it is the
	// measure that can be conserved: Σ ActiveMS across the curve must equal Σ
	// interval durations clipped to the window. That equality is a total-function
	// check on the fold, and a presence-only count cannot provide it.
	ActiveMS int64 `json:"active_ms"`
}

// Curve reports per-minute activity from the intervals the fleet recorded.
//
// This is ground truth, not an estimate. The fleet does not infer activity from an
// event stream — it decided the activity and wrote down the interval at the moment
// of transition. That is exactly what makes it usable as an oracle for the
// ClickHouse line: the two are computed from independent inputs, so agreement is
// evidence and disagreement is a defect in one of them.
//
// Recomputed from intervals on every call rather than sampled into a ring buffer.
// A ring buffer of counts would be cheaper per call but cannot answer a filtered
// question: pre-aggregating every combination of platform × app_version × country ×
// content_id explodes on content_id, and sampling after filtering is impossible
// because the filter is not known when the sample is taken. At MaxLive sessions
// this walk is a few hundred thousand minute-bumps — microseconds.
func (r *Registry) Curve(f Filter, from, to, now time.Time) []CurvePoint {
	from = from.UTC().Truncate(time.Minute)
	to = to.UTC().Truncate(time.Minute).Add(time.Minute)
	if !to.After(from) {
		return []CurvePoint{}
	}

	type bucket struct {
		sessions uint64
		activeMS int64
	}
	buckets := make(map[int64]*bucket)
	// Minutes the current session touches. A session can have several active
	// islands inside one minute — pause and resume within the same minute produces
	// two — and Sessions counts SESSIONS, not islands. Bumping per interval would
	// report 21 for a fleet of 20, which is how this was found.
	touched := make(map[int64]struct{})

	r.mu.Lock()
	for _, id := range r.order {
		s, ok := r.sessions[id]
		if !ok {
			continue
		}
		if !r.selects(s, f, now) {
			continue
		}
		clear(touched)
		for _, iv := range s.activeIntervals(now, r.timeout) {
			// Clip to the window before bucketing, so a session that started hours
			// ago contributes only its visible tail.
			start, end := iv.Start, iv.End
			if start.Before(from) {
				start = from
			}
			if end.After(to) {
				end = to
			}
			if !end.After(start) {
				continue
			}
			for m := start.Truncate(time.Minute); m.Before(end); m = m.Add(time.Minute) {
				lo, hi := m, m.Add(time.Minute)
				if start.After(lo) {
					lo = start
				}
				if end.Before(hi) {
					hi = end
				}
				b := buckets[m.Unix()]
				if b == nil {
					b = &bucket{}
					buckets[m.Unix()] = b
				}
				// Milliseconds accumulate across every island; the session count is
				// deferred so it lands once per minute however many islands there were.
				b.activeMS += hi.Sub(lo).Milliseconds()
				touched[m.Unix()] = struct{}{}
			}
		}
		for k := range touched {
			buckets[k].sessions++
		}
	}
	r.mu.Unlock()

	// Emit every minute in the window, including empty ones. A chart handed a
	// sparse series draws a straight line across the gap, which reads as sustained
	// activity that did not happen.
	out := make([]CurvePoint, 0, int(to.Sub(from)/time.Minute))
	for m := from; m.Before(to); m = m.Add(time.Minute) {
		p := CurvePoint{Minute: m}
		if b := buckets[m.Unix()]; b != nil {
			p.Sessions, p.ActiveMS = b.sessions, b.activeMS
		}
		out = append(out, p)
	}
	return out
}
