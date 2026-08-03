package mock

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/fleet"
)

// fleetStore persists fleet sessions into {{db}}.fleet_sessions.
//
// This is bookkeeping, not pipeline data. Nothing here feeds events_clean or the
// serving layer — it exists so a restart does not lose the simulator's ground
// truth while the events those sessions wrote stay in events_raw. Losing one side
// and not the other is what would make the comparison graph lie.
//
// It rides the connection the process already has, with the credentials already in
// /etc/sonyliv/sonyliv.env. No second user, no second secret.
type fleetStore struct {
	client *chx.Client
}

// fleetColumns is the INSERT column list, in the order Save appends values.
// Kept next to the query so the two cannot drift.
var fleetColumns = []string{
	"video_session_id", "user_id", "content_id", "content_title", "video_type",
	"platform", "app_version", "country",
	"start_epoch", "cadence_seconds", "expires_at", "mode", "ends_at", "next_behaviour",
	"started", "ended", "foreground", "playing", "heartbeating",
	"last_eligible", "open_since", "intervals",
	"events_sent", "next_tick", "removed", "updated_at", "version",
}

// zeroTS is what a nil time becomes. ClickHouse DateTime64 has no null, and the
// registry already treats the epoch as "unset" for open_since and last_eligible.
var zeroTS = time.Unix(0, 0).UTC()

func nz(t time.Time) time.Time {
	if t.IsZero() {
		return zeroTS
	}
	return t.UTC()
}

// Save upserts one row per session.
//
// Plain synchronous insert, not the async path the event loader uses: these
// batches are small and infrequent (only changed sessions, every five seconds),
// and the caller wants to know the state landed. async_insert exists for the
// opposite shape.
//
// No deduplication token either, and that is deliberate. The event path needs one
// because a retried insert must not double-count; here a retry writes the same
// (id, version) pair and ReplacingMergeTree collapses it on merge. Idempotency
// comes from the engine rather than from a token.
// saveChunk bounds one insert. Clearing a 100,000-session fleet handed Save every
// tombstone in one call; the insert did not fully land and the caller was told it
// had, so the sessions came back on the next restart.
const saveChunk = 10000

func (s *fleetStore) Save(ctx context.Context, rows []fleet.Persisted) error {
	for len(rows) > saveChunk {
		if err := s.save(ctx, rows[:saveChunk]); err != nil {
			return err
		}
		rows = rows[saveChunk:]
	}
	return s.save(ctx, rows)
}

func (s *fleetStore) save(ctx context.Context, rows []fleet.Persisted) error {
	if len(rows) == 0 {
		return nil
	}
	// Synchronous, matching the shape: chx's loader path turns async_insert on for
	// the event stream, which is the opposite case.
	ctx = clickhouse.Context(ctx, clickhouse.WithSettings(clickhouse.Settings{
		"async_insert": 0,
	}))

	stmt := fmt.Sprintf("INSERT INTO %s.fleet_sessions (%s)",
		s.client.Database, joinCols(fleetColumns))
	batch, err := s.client.Conn.PrepareBatch(ctx, stmt)
	if err != nil {
		return fmt.Errorf("prepare fleet_sessions batch: %w", err)
	}

	for _, p := range rows {
		// The array is a tuple-of-two per interval, matching the column's named
		// tuple. Built even for tombstones, where it is empty.
		intervals := make([][]any, 0, len(p.Intervals))
		for _, iv := range p.Intervals {
			intervals = append(intervals, []any{nz(iv.Start), nz(iv.End)})
		}
		updated := nz(p.UpdatedAt)

		if err := batch.Append(
			p.ID, p.UserID, p.ContentID, p.ContentTitle, p.VideoType,
			p.Platform, p.AppVersion, p.Country,
			nz(p.StartEpoch), uint16(p.CadenceSeconds), nz(p.ExpiresAt),
			p.Mode, nz(p.EndsAt), nz(p.NextBehaviour),
			p.Started, p.Ended, p.Foreground, p.Playing, p.Heartbeating,
			nz(p.LastEligible), nz(p.OpenSince), intervals,
			uint32(p.EventsSent), nz(p.NextTick), p.Removed, updated,
			// version is the update time in millis: monotonic per session because
			// the registry stamps it under one mutex, so the newest write always
			// wins the merge regardless of insert or retry order.
			uint64(updated.UnixMilli()),
		); err != nil {
			return fmt.Errorf("append fleet session %s: %w", p.ID, err)
		}
	}
	if err := batch.Send(); err != nil {
		return fmt.Errorf("send fleet_sessions batch: %w", err)
	}
	return nil
}

// Load reads the current state of every session that has not been cleared.
//
// FINAL is correct and cheap here: the table is bounded by the registry's own
// MaxLive cap, so this is thousands of rows read once at startup. The usual
// objection to FINAL is scan cost on a large table, which this is not.
//
// Ended sessions are loaded too, not filtered out. The listing shows them until
// the operator clears them, and dropping them here would make a restart look like
// the clear button had been pressed.
func (s *fleetStore) Load(ctx context.Context) ([]fleet.Persisted, error) {
	// "Ever tombstoned" excludes, rather than "the newest row says removed".
	//
	// Version ordering is not enough here and the difference is not academic: a
	// process that restores a session and re-persists it writes a live row with a
	// newer version than the tombstone, so a cleared session comes back and then
	// stays back. Chasing that with timestamps means every future writer has to
	// keep the ordering invariant, and a restart is exactly when it breaks.
	//
	// Terminal is the honest semantics. Session ids are 64 random hex characters
	// and are never reused, so "this id was cleared once" can only ever mean the
	// operator cleared it — no ordering required, and no way for a later write to
	// undo it by accident.
	q := fmt.Sprintf(`
		SELECT %s
		FROM %%[1]s.fleet_sessions FINAL
		WHERE video_session_id NOT IN (
		    SELECT video_session_id FROM %%[1]s.fleet_sessions WHERE removed
		)
		ORDER BY start_epoch, video_session_id`, joinCols(fleetColumns))
	q = fmt.Sprintf(q, s.client.Database)

	rows, err := s.client.Conn.Query(ctx, q)
	if err != nil {
		return nil, fmt.Errorf("load fleet_sessions: %w", err)
	}
	defer rows.Close()

	out := make([]fleet.Persisted, 0, 128)
	for rows.Next() {
		var (
			p         fleet.Persisted
			cadence   uint16
			eventsInt uint32
			version   uint64
			intervals [][]any
		)
		if err := rows.Scan(
			&p.ID, &p.UserID, &p.ContentID, &p.ContentTitle, &p.VideoType,
			&p.Platform, &p.AppVersion, &p.Country,
			&p.StartEpoch, &cadence, &p.ExpiresAt, &p.Mode, &p.EndsAt, &p.NextBehaviour,
			&p.Started, &p.Ended, &p.Foreground, &p.Playing, &p.Heartbeating,
			&p.LastEligible, &p.OpenSince, &intervals,
			&eventsInt, &p.NextTick, &p.Removed, &p.UpdatedAt, &version,
		); err != nil {
			return nil, fmt.Errorf("scan fleet session: %w", err)
		}
		p.CadenceSeconds = int(cadence)
		p.EventsSent = int(eventsInt)

		// The epoch means "unset" on the way in, exactly as it meant on the way out.
		// Leaving 1970 in place would make an unset lease look like an ancient one.
		p.LastEligible = unzero(p.LastEligible)
		p.OpenSince = unzero(p.OpenSince)
		p.ExpiresAt = unzero(p.ExpiresAt)
		p.EndsAt = unzero(p.EndsAt)
		p.NextBehaviour = unzero(p.NextBehaviour)

		for _, iv := range intervals {
			if len(iv) != 2 {
				continue
			}
			start, ok1 := iv[0].(time.Time)
			end, ok2 := iv[1].(time.Time)
			if ok1 && ok2 {
				p.Intervals = append(p.Intervals,
					fleet.Interval{Start: start.UTC(), End: end.UTC()})
			}
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func unzero(t time.Time) time.Time {
	if t.UTC().Year() <= 1970 {
		return time.Time{}
	}
	return t.UTC()
}

func joinCols(cols []string) string { return strings.Join(cols, ", ") }
