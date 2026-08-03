// Package pipelinehealth answers one question for the H7 self-observation
// path: is OUR concurrency pipeline fresh and correct right now? It queries
// v_cc_watermark (built by another agent — read only, never altered here),
// system.query_log (for build-stage timing, ClickHouse's own record of what
// tools/build-model.sh actually ran), and the reconcile-gate evidence file
// tools/reconcile.sh writes. Nothing here mutates a table, a view, or an MV.
package pipelinehealth

import (
	"context"
	"fmt"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
)

// Watermark is one row of sql/85_windows.sql's v_cc_watermark, typed.
//
// SIGN CONVENTION (per that view's own comment, load-bearing — do not invert
// it): the sealed tier legitimately LEADS raw by up to ~2 minutes because of
// the 60s tail grace, so a NEGATIVE SealedLagSeconds is the HEALTHY steady
// state. Healthy is defined here as SealedLagSeconds <= 0 — only a POSITIVE
// lag means the finalizer is genuinely behind. An alert or a "healthy" gauge
// built on `lag < 0` (as if any negative number were suspicious) would fire
// on the normal case every single time; that is exactly the trap the brief
// calls out.
type Watermark struct {
	RawWatermark             time.Time
	SealedWatermark          time.Time
	SealedLagSeconds         int64
	HourTierLastHour         time.Time
	HourFinalThrough         time.Time
	HourTierLastHourComplete bool
	TrendWatermark           time.Time
}

// Healthy reports whether the finalizer is caught up. See the sign-convention
// note on Watermark. Pointer receiver: Watermark is 136 bytes and copying it
// per call buys nothing (same convention as config.ClickHouse.Addr).
func (w *Watermark) Healthy() bool { return w.SealedLagSeconds <= 0 }

// QueryWatermark reads v_cc_watermark. It is a single-row view over
// system.one, so this is cheap and safe to call on every observe run.
func QueryWatermark(ctx context.Context, conn driver.Conn) (Watermark, error) {
	const q = `
		SELECT raw_watermark, sealed_watermark, sealed_lag_s,
		       hour_tier_last_hour, hour_final_through,
		       hour_tier_last_hour_complete, trend_watermark
		FROM v_cc_watermark`

	row := conn.QueryRow(ctx, q)

	var (
		rawWM, sealedWM, hourLast, hourFinal, trendWM *time.Time
		sealedLag                                     *int64
		hourComplete                                  *uint8
	)
	if err := row.Scan(&rawWM, &sealedWM, &sealedLag, &hourLast, &hourFinal, &hourComplete, &trendWM); err != nil {
		return Watermark{}, fmt.Errorf("scan v_cc_watermark: %w", err)
	}

	w := Watermark{}
	if rawWM != nil {
		w.RawWatermark = *rawWM
	}
	if sealedWM != nil {
		w.SealedWatermark = *sealedWM
	}
	if sealedLag != nil {
		w.SealedLagSeconds = *sealedLag
	}
	if hourLast != nil {
		w.HourTierLastHour = *hourLast
	}
	if hourFinal != nil {
		w.HourFinalThrough = *hourFinal
	}
	if hourComplete != nil {
		w.HourTierLastHourComplete = *hourComplete != 0
	}
	if trendWM != nil {
		w.TrendWatermark = *trendWM
	}
	return w, nil
}
