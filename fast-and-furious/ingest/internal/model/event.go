// Package model defines the wire shape of a raw event row and the canonical
// row fingerprint every producer must agree on.
package model

import (
	"time"

	"github.com/google/uuid"
)

// RawEvent mirrors the writable columns of the events_raw landing table, in the
// order the INSERT statement declares them. Field names track the source CSV
// header, which is also what events_raw calls them — the rename into the
// analytical vocabulary happens once, server-side, at the boundary into
// events_clean.
//
// Values are source-faithful: the producer parses and validates but never
// corrects. There is deliberately NO normalization here — no case folding, no
// event classification, no empty-to-unknown mapping. Every such rule lives in
// the events_raw_to_clean_mv SELECT so that this loader, the generator and a
// future Kafka consumer get identical results by construction, rather than by
// three clients agreeing to implement the same thing.
//
// Not written here, on purpose: _ingested_at. It defaults to now64(3) so it is
// the server's receive time rather than the producer's clock, which is what
// makes lateness (_ingested_at - event_timestamp) measurable across producers
// on different machines. session_key/user_key are MATERIALIZED for the same
// reason — one definition, server-side.
type RawEvent struct {
	IngestBatchID uuid.UUID
	BatchRowSeq   uint32
	SourceFile    string

	VideoSessionID string // 64-char uppercase hex
	UserID         string // 64-char uppercase hex
	ContentID      int64

	EventType         string
	Event             string
	EventTimestamp    time.Time
	SessionStartEpoch time.Time

	Platform         string
	AppVersion       string
	Country          string
	AudioLanguage    string
	SubtitleLanguage string
	PlayerVersion    string

	// Added by the unseen dataset (data/surprise_spec.md): "Video resolution
	// during video playback — used as a filter dimension".
	//
	// OPTIONAL, not required. The reader fills it when the header carries it and
	// leaves it empty otherwise, so both CSV generations load through the same
	// code path. Making it required would have made the original 13-column
	// extract unloadable, which is the wrong trade for a dimension that is
	// legitimately absent from it rather than missing from it.
	VideoResolution string
}

// InsertColumns is the column list of the raw-event INSERT, matching the field
// order of Values. Kept next to the struct so the two cannot drift.
var InsertColumns = []string{
	"_ingest_batch_id",
	"_batch_row_seq",
	"_source_file",
	"video_session_id",
	"user_id",
	"content_id",
	"event_type",
	"event",
	"event_timestamp",
	"session_start_epoch",
	"platform",
	"app_version",
	"country",
	"audio_language",
	"subtitle_language",
	"player_version",
	"video_resolution",
}

// Values returns the row as positional arguments for a driver batch Append.
func (e *RawEvent) Values() []any {
	return []any{
		e.IngestBatchID,
		e.BatchRowSeq,
		e.SourceFile,
		e.VideoSessionID,
		e.UserID,
		e.ContentID,
		e.EventType,
		e.Event,
		e.EventTimestamp,
		e.SessionStartEpoch,
		e.Platform,
		e.AppVersion,
		e.Country,
		e.AudioLanguage,
		e.SubtitleLanguage,
		e.PlayerVersion,
		e.VideoResolution,
	}
}

// Content is one row of the content catalogue.
type Content struct {
	ContentID int64
	Title     string
	VideoType string
	Category  string

	// Added by the unseen dataset (data/surprise_spec.md): "Name of the show —
	// used as a filter dimension". Optional for the same reason as
	// RawEvent.VideoResolution.
	ShowName string
}

// ContentInsertColumns matches Content.Values plus the load version.
var ContentInsertColumns = []string{
	"content_id",
	"title",
	"video_type",
	"category",
	"show_name",
	"source_version",
}

// Values returns the catalogue row plus its load version.
func (c *Content) Values(sourceVersion uint64) []any {
	return []any{c.ContentID, c.Title, c.VideoType, c.Category, c.ShowName, sourceVersion}
}

// Reject is a row the producer refused to land, held for quarantine.
type Reject struct {
	RunID      uuid.UUID
	Source     string
	SourceLine uint64
	Reason     string
	Detail     string
	RawRow     string
}

// RejectInsertColumns matches Reject.Values.
var RejectInsertColumns = []string{
	"run_id", "source", "source_line", "reason", "detail", "raw_row",
}

// Values returns the reject as positional insert arguments.
func (r *Reject) Values() []any {
	return []any{r.RunID, r.Source, r.SourceLine, r.Reason, r.Detail, r.RawRow}
}

// BatchAudit is one row of default.ingest_batches.
type BatchAudit struct {
	IngestBatchID     uuid.UUID
	RunID             uuid.UUID
	Source            string
	SourceFingerprint string
	BatchOrdinal      uint32
	DedupToken        string
	RowCount          uint32
	RejectedCount     uint32
	BytesEstimate     uint64
	FirstEventTime    time.Time
	LastEventTime     time.Time
	StartedAt         time.Time
	CompletedAt       time.Time
	DurationMS        uint32
	Attempt           uint8
	Status            string
	Error             string
}

// BatchAuditInsertColumns matches BatchAudit.Values.
var BatchAuditInsertColumns = []string{
	"ingest_batch_id", "run_id", "source", "source_fingerprint", "batch_ordinal",
	"dedup_token", "row_count", "rejected_count", "bytes_estimate",
	"first_event_time", "last_event_time", "started_at", "completed_at",
	"duration_ms", "attempt", "status", "error",
}

// Values returns the audit row as positional insert arguments.
func (b *BatchAudit) Values() []any {
	return []any{
		b.IngestBatchID, b.RunID, b.Source, b.SourceFingerprint, b.BatchOrdinal,
		b.DedupToken, b.RowCount, b.RejectedCount, b.BytesEstimate,
		b.FirstEventTime, b.LastEventTime, b.StartedAt, b.CompletedAt,
		b.DurationMS, b.Attempt, b.Status, b.Error,
	}
}
