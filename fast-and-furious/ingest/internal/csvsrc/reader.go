// Package csvsrc streams the supplied CSV extracts into typed rows.
//
// Two properties matter more than speed here:
//
//   - Columns are resolved by header name, never by position. The unseen-day
//     file comes from the same universe but nothing promises the same column
//     order, and a positional reader would fail silently by writing user ids
//     into the platform column.
//
//   - A row that cannot be parsed is quarantined with its line number and the
//     verbatim text, never dropped. "We excluded 12 rows, here they are" is a
//     defensible answer; a row count that quietly differs from the source is
//     not.
package csvsrc

import (
	"bufio"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// Reject reasons, kept as constants so the quarantine table stays groupable.
const (
	ReasonBadSessionID = "bad_session_id"
	ReasonBadUserID    = "bad_user_id"
	ReasonBadContentID = "bad_content_id"
	ReasonBadTimestamp = "bad_timestamp"
	ReasonBadRow       = "bad_column_count"
)

// rawColumns are the columns required by the raw-event schema.
var rawColumns = []string{
	"video_session_id", "user_id", "content_id", "event_type", "event",
	"event_timestamp", "platform", "app_version", "country",
	"audio_language", "subtitle_language", "player_version", "session_start_epoch",
}

// contentColumns are the columns required by the content catalogue.
var contentColumns = []string{"content_id", "title", "video_type", "category"}

// RowReject describes a source row that failed validation.
type RowReject struct {
	Line   uint64
	Reason string
	Detail string
	Raw    string
}

// EventReader streams raw events from the event CSV.
type EventReader struct {
	f    *os.File
	r    *csv.Reader
	idx  map[string]int
	line uint64
}

// OpenEvents opens the event CSV and validates its header.
func OpenEvents(path string) (*EventReader, error) {
	f, r, idx, err := openCSV(path, rawColumns)
	if err != nil {
		return nil, err
	}
	return &EventReader{f: f, r: r, idx: idx, line: 1}, nil
}

// Close releases the file.
func (er *EventReader) Close() error { return er.f.Close() }

// Next returns the next parsed event.
//
// It returns (nil, reject, nil) for a row that failed validation, and
// (nil, nil, io.EOF) at end of file.
func (er *EventReader) Next() (*model.RawEvent, *RowReject, error) {
	rec, err := er.r.Read()
	if err != nil {
		if err == io.EOF {
			return nil, nil, io.EOF
		}
		er.line++
		// A structurally broken line (bad quoting, wrong field count) still gets
		// quarantined rather than aborting the load.
		var pe *csv.ParseError
		if ok := asParseError(err, &pe); ok {
			return nil, &RowReject{
				Line:   uint64(pe.Line),
				Reason: ReasonBadRow,
				Detail: pe.Err.Error(),
			}, nil
		}
		return nil, nil, fmt.Errorf("read csv at line %d: %w", er.line, err)
	}
	er.line++

	get := func(col string) string { return strings.TrimSpace(rec[er.idx[col]]) }
	// getOpt is for columns that may be absent from the header entirely.
	// get() would index rec[0] on a missing column -- er.idx returns the zero
	// value for an absent key -- and silently return content_id's value for
	// video_resolution. That is a wrong value, not an error, so the optional
	// lookup has to be explicit.
	getOpt := func(col string) string {
		i, ok := er.idx[col]
		if !ok || i >= len(rec) {
			return ""
		}
		return strings.TrimSpace(rec[i])
	}
	reject := func(reason, detail string) *RowReject {
		return &RowReject{Line: er.line, Reason: reason, Detail: detail, Raw: strings.Join(rec, ",")}
	}

	sessionID, err := NormalizeHexID(get("video_session_id"))
	if err != nil {
		return nil, reject(ReasonBadSessionID, err.Error()), nil
	}
	userID, err := NormalizeHexID(get("user_id"))
	if err != nil {
		return nil, reject(ReasonBadUserID, err.Error()), nil
	}
	contentID, err := ParseContentID(get("content_id"))
	if err != nil {
		return nil, reject(ReasonBadContentID, err.Error()), nil
	}
	eventTime, err := ParseEpochMillis(get("event_timestamp"))
	if err != nil {
		return nil, reject(ReasonBadTimestamp, "event_timestamp: "+err.Error()), nil
	}
	sessionStart, err := ParseEpochMillis(get("session_start_epoch"))
	if err != nil {
		return nil, reject(ReasonBadTimestamp, "session_start_epoch: "+err.Error()), nil
	}

	ev := &model.RawEvent{
		VideoSessionID:    sessionID,
		UserID:            userID,
		ContentID:         contentID,
		EventType:         get("event_type"),
		Event:             get("event"),
		EventTimestamp:    eventTime,
		SessionStartEpoch: sessionStart,
		Platform:          get("platform"),
		AppVersion:        get("app_version"),
		Country:           get("country"),
		AudioLanguage:     get("audio_language"),
		SubtitleLanguage:  get("subtitle_language"),
		PlayerVersion:     get("player_version"),
		VideoResolution:   getOpt("video_resolution"),
	}
	return ev, nil, nil
}

// ContentReader streams the content catalogue.
type ContentReader struct {
	f    *os.File
	r    *csv.Reader
	idx  map[string]int
	line uint64
}

// OpenContent opens the content CSV and validates its header.
func OpenContent(path string) (*ContentReader, error) {
	f, r, idx, err := openCSV(path, contentColumns)
	if err != nil {
		return nil, err
	}
	return &ContentReader{f: f, r: r, idx: idx, line: 1}, nil
}

// Close releases the file.
func (cr *ContentReader) Close() error { return cr.f.Close() }

// Next returns the next catalogue row, or io.EOF.
func (cr *ContentReader) Next() (*model.Content, *RowReject, error) {
	rec, err := cr.r.Read()
	if err != nil {
		if err == io.EOF {
			return nil, nil, io.EOF
		}
		cr.line++
		// Same contract as EventReader: a structurally broken line is
		// quarantined, not fatal. One malformed catalogue row must not abort
		// the load and leave the rest of the catalogue — and the enrichment
		// dictionary built from it — unrefreshed.
		var pe *csv.ParseError
		if ok := asParseError(err, &pe); ok {
			return nil, &RowReject{
				Line:   uint64(pe.Line),
				Reason: ReasonBadRow,
				Detail: pe.Err.Error(),
			}, nil
		}
		return nil, nil, fmt.Errorf("read content csv at line %d: %w", cr.line, err)
	}
	cr.line++

	get := func(col string) string { return strings.TrimSpace(rec[cr.idx[col]]) }
	// Optional column; see the note on getOpt in the event reader for why a
	// missing key cannot go through get().
	getOpt := func(col string) string {
		i, ok := cr.idx[col]
		if !ok || i >= len(rec) {
			return ""
		}
		return strings.TrimSpace(rec[i])
	}

	contentID, err := ParseContentID(get("content_id"))
	if err != nil {
		return nil, &RowReject{
			Line: cr.line, Reason: ReasonBadContentID,
			Detail: err.Error(), Raw: strings.Join(rec, ","),
		}, nil
	}

	// Empty video_type is real (1,089 catalogue rows, 142 of them played) and
	// means "unclassified", not "missing". Mapping it here keeps every GROUP BY
	// from producing a nameless bucket.
	videoType := get("video_type")
	if videoType == "" {
		videoType = "unknown"
	}
	category := get("category")
	if category == "" {
		category = "unknown"
	}
	// show_name arrives with the unseen dataset and is absent from the original
	// extract. Left as the empty string rather than mapped to 'unknown': unlike
	// video_type and category, there is no evidence an empty show_name means
	// "unclassified" here, and inventing a value would make "this catalogue has
	// no show names at all" indistinguishable from "this title has none".
	showName := getOpt("show_name")

	return &model.Content{
		ContentID: contentID,
		Title:     get("title"),
		ShowName:  showName,
		VideoType: videoType,
		Category:  category,
	}, nil, nil
}

// openCSV opens a file, reads the header, and maps the required columns.
func openCSV(path string, required []string) (*os.File, *csv.Reader, map[string]int, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("open %s: %w", path, err)
	}
	// 4 MiB read buffer: the event file is ~233 MB and the default 4 KiB buffer
	// turns the load into a syscall benchmark.
	r := csv.NewReader(bufio.NewReaderSize(f, 4<<20))
	r.ReuseRecord = true
	r.FieldsPerRecord = -1 // validated per row instead of aborting the file

	header, err := r.Read()
	if err != nil {
		_ = f.Close()
		return nil, nil, nil, fmt.Errorf("read header of %s: %w", path, err)
	}

	// Strip a UTF-8 BOM if the exporter wrote one, or the first column name
	// silently fails to match.
	idx := make(map[string]int, len(header))
	for i, h := range header {
		idx[strings.ToLower(strings.TrimSpace(strings.TrimPrefix(h, "\uFEFF")))] = i
	}

	var missing []string
	for _, col := range required {
		if _, ok := idx[col]; !ok {
			missing = append(missing, col)
		}
	}
	if len(missing) > 0 {
		_ = f.Close()
		return nil, nil, nil, fmt.Errorf("%s is missing required column(s): %s (header was: %s)",
			path, strings.Join(missing, ", "), strings.Join(header, ", "))
	}

	// Now that the header is known good, enforce the field count on data rows.
	r.FieldsPerRecord = len(header)
	return f, r, idx, nil
}

// NormalizeHexID validates a 64-character hex identifier and upper-cases it.
//
// Exported because internal/api validates the same two ids on the HTTP path, and
// a second copy of this function is exactly the cross-producer drift that
// model.RawEvent's shared contract exists to prevent. (Re-applied after a merge
// took main's copy of this file, which predates the export.)
//
// Case is normalized because the id is the session key: 'a1b2' and 'A1B2' from
// two different producers must not become two different sessions.
func NormalizeHexID(s string) (string, error) {
	if len(s) != 64 {
		return "", fmt.Errorf("expected 64 hex chars, got %d", len(s))
	}
	out := make([]byte, 64)
	for i := 0; i < 64; i++ {
		c := s[i]
		switch {
		case c >= '0' && c <= '9', c >= 'A' && c <= 'F':
			out[i] = c
		case c >= 'a' && c <= 'f':
			out[i] = c - 'a' + 'A'
		default:
			return "", fmt.Errorf("non-hex character %q at position %d", c, i)
		}
	}
	return string(out), nil
}

// ParseContentID parses a content id into the signed domain the schema uses.
//
// The catalogue contains 18446744072721897294, which is -987654322 written as
// an unsigned 64-bit value by the source system. Parsing that as unsigned and
// reinterpreting the bits recovers the intended negative id; treating it as a
// huge positive number would create a phantom catalogue entry that no event can
// ever join to.
func ParseContentID(s string) (int64, error) {
	if s == "" {
		return 0, fmt.Errorf("empty content_id")
	}
	if v, err := strconv.ParseInt(s, 10, 64); err == nil {
		return v, nil
	}
	u, err := strconv.ParseUint(s, 10, 64)
	if err != nil {
		return 0, fmt.Errorf("content_id %q is not an integer", s)
	}
	return int64(u), nil
}

// ParseEpochMillis converts epoch-milliseconds to a UTC time.
//
// The bounds reject a value that is really seconds or microseconds: a
// mis-scaled timestamp would land the row in 1970 or the year 56000 and quietly
// corrupt every concurrency bucket rather than failing loudly.
func ParseEpochMillis(s string) (time.Time, error) {
	if s == "" {
		return time.Time{}, fmt.Errorf("empty timestamp")
	}
	// Tolerate a trailing ".0" from producers that render epochs as floats.
	if dot := strings.IndexByte(s, '.'); dot >= 0 {
		frac := s[dot+1:]
		if strings.Trim(frac, "0") != "" {
			return time.Time{}, fmt.Errorf("timestamp %q has sub-millisecond precision", s)
		}
		s = s[:dot]
	}
	ms, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return time.Time{}, fmt.Errorf("timestamp %q is not an integer", s)
	}
	const (
		minMillis = int64(946_684_800_000)   // 2000-01-01
		maxMillis = int64(4_102_444_800_000) // 2100-01-01
	)
	if ms < minMillis || ms > maxMillis {
		return time.Time{}, fmt.Errorf("timestamp %d ms is outside 2000-2100; wrong unit?", ms)
	}
	return time.UnixMilli(ms).UTC(), nil
}

// FileSHA256 fingerprints a source file. The fingerprint feeds the insert
// deduplication token, so replaying the same file is a no-op while loading a
// different file under the same name is not.
func FileSHA256(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", fmt.Errorf("open %s: %w", path, err)
	}
	defer f.Close()

	h := sha256.New()
	if _, err := io.Copy(h, bufio.NewReaderSize(f, 1<<20)); err != nil {
		return "", fmt.Errorf("hash %s: %w", path, err)
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// FileSize returns the size of a file in bytes, for progress reporting.
func FileSize(path string) int64 {
	st, err := os.Stat(path)
	if err != nil {
		return 0
	}
	return st.Size()
}

// asParseError unwraps a *csv.ParseError without importing errors twice.
func asParseError(err error, target **csv.ParseError) bool {
	pe, ok := err.(*csv.ParseError)
	if ok {
		*target = pe
	}
	return ok
}
