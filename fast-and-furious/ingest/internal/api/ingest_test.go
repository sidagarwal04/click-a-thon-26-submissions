package api

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/model"
)

const testToken = "test-token"

// recorder stands in for the ClickHouse write path so the handler is testable
// without a server. It captures what WOULD have been inserted.
type recorder struct {
	mu           sync.Mutex
	fingerprints []string
	asyncFlags   []bool
	chunks       [][]*chx.Chunk
	err          error
}

func (r *recorder) Write(_ context.Context, fingerprint string, async bool, chunks []*chx.Chunk) (chx.Stats, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.fingerprints = append(r.fingerprints, fingerprint)
	r.asyncFlags = append(r.asyncFlags, async)
	r.chunks = append(r.chunks, chunks)
	if r.err != nil {
		return chx.Stats{}, r.err
	}
	var rows uint64
	for _, c := range chunks {
		rows += uint64(len(c.Rows))
	}
	return chx.Stats{Rows: rows, Batches: uint64(len(chunks))}, nil
}

func (r *recorder) rowsWritten() int {
	r.mu.Lock()
	defer r.mu.Unlock()
	n := 0
	for _, cs := range r.chunks {
		for _, c := range cs {
			n += len(c.Rows)
		}
	}
	return n
}

type rejectSink struct {
	mu   sync.Mutex
	list []model.Reject
}

func (s *rejectSink) AddReject(r model.Reject) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.list = append(s.list, r)
}

func newTestServer(t *testing.T, opts Options) (*httptest.Server, *recorder, *rejectSink) {
	t.Helper()
	rec := &recorder{}
	sink := &rejectSink{}
	opts.Token = testToken
	srv, err := NewServer(rec, sink, func(context.Context) error { return nil }, opts)
	if err != nil {
		t.Fatalf("NewServer: %v", err)
	}
	ts := httptest.NewServer(srv.Handler())
	t.Cleanup(ts.Close)
	return ts, rec, sink
}

// validEvent renders one well-formed NDJSON event. id is used to vary the ids so
// a caller can build a batch of distinct rows.
func validEvent(id int) string {
	sess := strings.Repeat("A", 63) + string(rune('A'+id%6))
	user := strings.Repeat("B", 63) + string(rune('A'+id%6))
	return fmt.Sprintf(`{"video_session_id":%q,"user_id":%q,"content_id":21311522,`+
		`"event_type":"VideoHeartbeat","event":"network-activity",`+
		`"event_timestamp":178506201%d289,"session_start_epoch":1785062007336,`+
		`"platform":"JIO_ANDROID_TV","app_version":"3.9.4","country":"india",`+
		`"audio_language":"hin","subtitle_language":"UNK","player_version":"1.8.2"}`,
		sess, user, id%10)
}

func post(t *testing.T, ts *httptest.Server, contentType, body string, hdr map[string]string) (*http.Response, ingestResponse) {
	t.Helper()
	req, err := http.NewRequest(http.MethodPost, ts.URL+"/v1/events", strings.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Authorization", "Bearer "+testToken)
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	for k, v := range hdr {
		req.Header.Set(k, v)
	}
	resp, err := ts.Client().Do(req)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { resp.Body.Close() })
	raw, _ := io.ReadAll(resp.Body)
	var out ingestResponse
	_ = json.Unmarshal(raw, &out)
	return resp, out
}

func TestAuthRequired(t *testing.T) {
	ts, _, _ := newTestServer(t, Options{})

	for _, tc := range []struct{ name, header string }{
		{"missing", ""},
		{"wrong token", "Bearer nope"},
		{"not bearer", "Basic " + testToken},
		{"token without scheme", testToken},
	} {
		t.Run(tc.name, func(t *testing.T) {
			req, _ := http.NewRequest(http.MethodPost, ts.URL+"/v1/events", strings.NewReader(validEvent(0)))
			if tc.header != "" {
				req.Header.Set("Authorization", tc.header)
			}
			resp, err := ts.Client().Do(req)
			if err != nil {
				t.Fatal(err)
			}
			defer resp.Body.Close()
			if resp.StatusCode != http.StatusUnauthorized {
				t.Fatalf("status = %d, want 401", resp.StatusCode)
			}
		})
	}
}

// The service must refuse to start unauthenticated rather than default to open.
func TestNewServerRequiresToken(t *testing.T) {
	_, err := NewServer(&recorder{}, &rejectSink{}, func(context.Context) error { return nil }, Options{})
	if err == nil {
		t.Fatal("NewServer with no token should fail")
	}
}

func TestIngestNDJSON(t *testing.T) {
	ts, rec, _ := newTestServer(t, Options{})
	body := validEvent(0) + "\n" + validEvent(1) + "\n" + validEvent(2) + "\n"

	resp, out := post(t, ts, "application/x-ndjson", body, nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", resp.StatusCode)
	}
	if out.Accepted != 3 || out.Rejected != 0 {
		t.Fatalf("accepted=%d rejected=%d, want 3/0", out.Accepted, out.Rejected)
	}
	if rec.rowsWritten() != 3 {
		t.Fatalf("rows written = %d, want 3", rec.rowsWritten())
	}
}

func TestIngestJSONArray(t *testing.T) {
	ts, rec, _ := newTestServer(t, Options{})
	body := "[" + validEvent(0) + "," + validEvent(1) + "]"

	resp, out := post(t, ts, "application/json", body, nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", resp.StatusCode)
	}
	if out.Accepted != 2 {
		t.Fatalf("accepted = %d, want 2", out.Accepted)
	}
	if rec.rowsWritten() != 2 {
		t.Fatalf("rows written = %d, want 2", rec.rowsWritten())
	}
}

// The ids are upper-cased on the way in. A lower-case id from one producer and an
// upper-case one from another must not become two sessions.
func TestHexIDsAreUpperCased(t *testing.T) {
	ts, rec, _ := newTestServer(t, Options{})
	lower := strings.Repeat("a", 64)
	body := fmt.Sprintf(`{"video_session_id":%q,"user_id":%q,"content_id":1,`+
		`"event_type":"VideoPlay","event":"Play","event_timestamp":1785062011289,`+
		`"session_start_epoch":1785062007336}`, lower, lower)

	if resp, out := post(t, ts, "application/x-ndjson", body, nil); resp.StatusCode != 200 || out.Accepted != 1 {
		t.Fatalf("status=%d accepted=%d", resp.StatusCode, out.Accepted)
	}
	got := rec.chunks[0][0].Rows[0].VideoSessionID
	if want := strings.Repeat("A", 64); got != want {
		t.Fatalf("session id = %q, want upper-cased", got)
	}
}

// content_id 18446744072721897294 is -987654322 written unsigned by the source
// system. It must survive as the negative id, not become a phantom catalogue row.
func TestUnsignedNegativeContentID(t *testing.T) {
	ts, rec, _ := newTestServer(t, Options{})
	id := strings.Repeat("C", 64)
	body := fmt.Sprintf(`{"video_session_id":%q,"user_id":%q,`+
		`"content_id":18446744072721897294,"event_type":"VideoPlay","event":"Play",`+
		`"event_timestamp":1785062011289,"session_start_epoch":1785062007336}`, id, id)

	resp, out := post(t, ts, "application/x-ndjson", body, nil)
	if resp.StatusCode != 200 || out.Accepted != 1 {
		t.Fatalf("status=%d accepted=%d rejects=%v", resp.StatusCode, out.Accepted, out.Rejects)
	}
	if got := rec.chunks[0][0].Rows[0].ContentID; got != -987654322 {
		t.Fatalf("content_id = %d, want -987654322", got)
	}
}

// Reason codes must match the CSV path so ingest_rejects stays groupable across
// producers.
func TestRejectReasons(t *testing.T) {
	valid := strings.Repeat("A", 64)
	cases := []struct {
		name, body, wantReason string
	}{
		{"short session id",
			fmt.Sprintf(`{"video_session_id":"abc","user_id":%q,"content_id":1,"event_timestamp":1785062011289,"session_start_epoch":1785062007336}`, valid),
			"bad_session_id"},
		{"non-hex user id",
			fmt.Sprintf(`{"video_session_id":%q,"user_id":%q,"content_id":1,"event_timestamp":1785062011289,"session_start_epoch":1785062007336}`, valid, strings.Repeat("z", 64)),
			"bad_user_id"},
		{"empty content id",
			fmt.Sprintf(`{"video_session_id":%q,"user_id":%q,"event_timestamp":1785062011289,"session_start_epoch":1785062007336}`, valid, valid),
			"bad_content_id"},
		{"timestamp in seconds not millis",
			fmt.Sprintf(`{"video_session_id":%q,"user_id":%q,"content_id":1,"event_timestamp":1785062011,"session_start_epoch":1785062007336}`, valid, valid),
			"bad_timestamp"},
		{"missing session_start_epoch",
			fmt.Sprintf(`{"video_session_id":%q,"user_id":%q,"content_id":1,"event_timestamp":1785062011289}`, valid, valid),
			"bad_timestamp"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			ts, rec, sink := newTestServer(t, Options{})
			resp, out := post(t, ts, "application/x-ndjson", tc.body, nil)
			if resp.StatusCode != http.StatusOK {
				t.Fatalf("status = %d, want 200 (a reject is a handled request)", resp.StatusCode)
			}
			if out.Rejected != 1 || out.Accepted != 0 {
				t.Fatalf("accepted=%d rejected=%d, want 0/1", out.Accepted, out.Rejected)
			}
			if out.Rejects[0].Reason != tc.wantReason {
				t.Fatalf("reason = %q, want %q", out.Rejects[0].Reason, tc.wantReason)
			}
			if out.Rejects[0].Index != 1 {
				t.Fatalf("index = %d, want 1-based", out.Rejects[0].Index)
			}
			// Nothing insertable, so the write path must not be touched at all.
			if rec.rowsWritten() != 0 {
				t.Fatalf("rows written = %d, want 0", rec.rowsWritten())
			}
			// The bad row is quarantined under the api source label.
			if len(sink.list) != 1 || sink.list[0].Source != SourceLabel {
				t.Fatalf("rejects = %+v", sink.list)
			}
		})
	}
}

// A partly-bad request inserts the good rows and quarantines the rest.
func TestPartialAcceptance(t *testing.T) {
	ts, rec, sink := newTestServer(t, Options{})
	body := validEvent(0) + "\n" + `{"video_session_id":"nope","user_id":"nope"}` + "\n" + validEvent(1) + "\n"

	resp, out := post(t, ts, "application/x-ndjson", body, nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", resp.StatusCode)
	}
	if out.Accepted != 2 || out.Rejected != 1 {
		t.Fatalf("accepted=%d rejected=%d, want 2/1", out.Accepted, out.Rejected)
	}
	if rec.rowsWritten() != 2 {
		t.Fatalf("rows written = %d, want 2", rec.rowsWritten())
	}
	if got := sink.list[0].SourceLine; got != 2 {
		t.Fatalf("reject line = %d, want 2 (the middle event)", got)
	}
}

// The same body must produce the same dedup fingerprint, and a different body a
// different one. This is what makes a retry exactly-once rather than a duplicate,
// and what stops two unrelated requests colliding on one token.
func TestFingerprintFromBody(t *testing.T) {
	ts, rec, _ := newTestServer(t, Options{})
	body := validEvent(0) + "\n"

	post(t, ts, "application/x-ndjson", body, nil)
	post(t, ts, "application/x-ndjson", body, nil)
	post(t, ts, "application/x-ndjson", validEvent(1)+"\n", nil)

	if len(rec.fingerprints) != 3 {
		t.Fatalf("writes = %d, want 3", len(rec.fingerprints))
	}
	if rec.fingerprints[0] != rec.fingerprints[1] {
		t.Fatal("identical bodies must share a fingerprint, else a retry duplicates")
	}
	if rec.fingerprints[0] == rec.fingerprints[2] {
		t.Fatal("different bodies must NOT share a fingerprint, else one is silently dropped")
	}
}

func TestIdempotencyKeyOverridesBodyHash(t *testing.T) {
	ts, rec, _ := newTestServer(t, Options{})
	hdr := map[string]string{"Idempotency-Key": "client-supplied-key"}

	post(t, ts, "application/x-ndjson", validEvent(0)+"\n", hdr)
	post(t, ts, "application/x-ndjson", validEvent(1)+"\n", hdr)

	if rec.fingerprints[0] != "client-supplied-key" {
		t.Fatalf("fingerprint = %q, want the header value", rec.fingerprints[0])
	}
	if rec.fingerprints[0] != rec.fingerprints[1] {
		t.Fatal("same Idempotency-Key must win over differing bodies")
	}
}

// Small requests use the server-side buffer; large ones bypass it.
func TestSyncThreshold(t *testing.T) {
	ts, rec, _ := newTestServer(t, Options{SyncThreshold: 3, BatchSize: 2, MaxRows: 100})

	var small strings.Builder
	for i := 0; i < 2; i++ {
		small.WriteString(validEvent(i) + "\n")
	}
	var large strings.Builder
	for i := 0; i < 5; i++ {
		large.WriteString(validEvent(i) + "\n")
	}

	if _, out := post(t, ts, "application/x-ndjson", small.String(), nil); out.Mode != "async" {
		t.Fatalf("mode = %q for 2 rows under threshold 3, want async", out.Mode)
	}
	if _, out := post(t, ts, "application/x-ndjson", large.String(), nil); out.Mode != "sync" {
		t.Fatalf("mode = %q for 5 rows over threshold 3, want sync", out.Mode)
	}
	if rec.asyncFlags[0] != true || rec.asyncFlags[1] != false {
		t.Fatalf("async flags = %v, want [true false]", rec.asyncFlags)
	}
}

// Chunks must be cut at BatchSize, in order, with sequential ordinals. Both the
// dedup token and the 20-bit _batch_row_seq budget depend on it.
func TestChunkingAtBatchSize(t *testing.T) {
	ts, rec, _ := newTestServer(t, Options{BatchSize: 2, MaxRows: 100, SyncThreshold: 1})

	var b strings.Builder
	for i := 0; i < 5; i++ {
		b.WriteString(validEvent(i) + "\n")
	}
	if _, out := post(t, ts, "application/x-ndjson", b.String(), nil); out.Batches != 3 {
		t.Fatalf("batches = %d, want 3 (2+2+1)", out.Batches)
	}
	chunks := rec.chunks[0]
	for i, c := range chunks {
		if c.Ordinal != uint32(i) {
			t.Fatalf("chunk %d ordinal = %d, want %d", i, c.Ordinal, i)
		}
	}
	if len(chunks[0].Rows) != 2 || len(chunks[2].Rows) != 1 {
		t.Fatalf("chunk sizes = %d,%d,%d, want 2,2,1",
			len(chunks[0].Rows), len(chunks[1].Rows), len(chunks[2].Rows))
	}
}

// No chunk may exceed the sequence space row_version allots _batch_row_seq.
func TestChunkNeverExceedsSeqBudget(t *testing.T) {
	const seqBudget = 1 << 20
	rows := make([]model.RawEvent, 3*DefaultBatchSize+7)
	for _, c := range chunk(rows, DefaultBatchSize) {
		if len(c.Rows) >= seqBudget {
			t.Fatalf("chunk of %d rows overflows the 20-bit _batch_row_seq budget", len(c.Rows))
		}
	}
}

func TestMaxRowsRejected(t *testing.T) {
	ts, rec, _ := newTestServer(t, Options{MaxRows: 2, BatchSize: 2})

	var b strings.Builder
	for i := 0; i < 4; i++ {
		b.WriteString(validEvent(i) + "\n")
	}
	resp, _ := post(t, ts, "application/x-ndjson", b.String(), nil)
	if resp.StatusCode != http.StatusRequestEntityTooLarge {
		t.Fatalf("status = %d, want 413", resp.StatusCode)
	}
	// Rejected outright, not truncated: nothing may be written.
	if rec.rowsWritten() != 0 {
		t.Fatalf("rows written = %d, want 0 — an oversized request must not be partially stored", rec.rowsWritten())
	}
}

func TestMaxBodyRejected(t *testing.T) {
	ts, rec, _ := newTestServer(t, Options{MaxBodyBytes: 200, MaxRows: 100, BatchSize: 10})

	var b strings.Builder
	for i := 0; i < 20; i++ {
		b.WriteString(validEvent(i) + "\n")
	}
	resp, _ := post(t, ts, "application/x-ndjson", b.String(), nil)
	if resp.StatusCode != http.StatusRequestEntityTooLarge {
		t.Fatalf("status = %d, want 413", resp.StatusCode)
	}
	if rec.rowsWritten() != 0 {
		t.Fatalf("rows written = %d, want 0", rec.rowsWritten())
	}
}

func TestUnsupportedContentType(t *testing.T) {
	ts, _, _ := newTestServer(t, Options{})
	resp, _ := post(t, ts, "application/xml", validEvent(0), nil)
	if resp.StatusCode != http.StatusUnsupportedMediaType {
		t.Fatalf("status = %d, want 415", resp.StatusCode)
	}
}

func TestMalformedJSON(t *testing.T) {
	ts, rec, _ := newTestServer(t, Options{})
	resp, _ := post(t, ts, "application/x-ndjson", `{"video_session_id": `, nil)
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", resp.StatusCode)
	}
	if rec.rowsWritten() != 0 {
		t.Fatalf("rows written = %d, want 0", rec.rowsWritten())
	}
}

// An insert failure must surface, not be swallowed into a 200.
func TestInsertFailureSurfaces(t *testing.T) {
	rec := &recorder{err: fmt.Errorf("clickhouse unreachable")}
	srv, err := NewServer(rec, &rejectSink{}, func(context.Context) error { return nil },
		Options{Token: testToken})
	if err != nil {
		t.Fatal(err)
	}
	ts := httptest.NewServer(srv.Handler())
	defer ts.Close()

	resp, _ := post(t, ts, "application/x-ndjson", validEvent(0)+"\n", nil)
	if resp.StatusCode != http.StatusBadGateway {
		t.Fatalf("status = %d, want 502", resp.StatusCode)
	}
}

// Liveness must not depend on ClickHouse; readiness must.
func TestHealthAndReadiness(t *testing.T) {
	rec := &recorder{}
	pingErr := fmt.Errorf("down")
	srv, err := NewServer(rec, &rejectSink{}, func(context.Context) error { return pingErr },
		Options{Token: testToken})
	if err != nil {
		t.Fatal(err)
	}
	ts := httptest.NewServer(srv.Handler())
	defer ts.Close()

	// healthz stays 200 with ClickHouse down: restarting the process would not
	// fix the database and would only lengthen the outage.
	resp, err := ts.Client().Get(ts.URL + "/healthz")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("healthz = %d, want 200 even when CH is down", resp.StatusCode)
	}

	resp, err = ts.Client().Get(ts.URL + "/readyz")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusServiceUnavailable {
		t.Fatalf("readyz = %d, want 503 when CH is down", resp.StatusCode)
	}
}

func TestEmptyBodyIsHandled(t *testing.T) {
	ts, rec, _ := newTestServer(t, Options{})
	resp, out := post(t, ts, "application/x-ndjson", "", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", resp.StatusCode)
	}
	if out.Accepted != 0 || out.Mode != "none" {
		t.Fatalf("accepted=%d mode=%q, want 0/none", out.Accepted, out.Mode)
	}
	if rec.rowsWritten() != 0 {
		t.Fatalf("rows written = %d, want 0", rec.rowsWritten())
	}
}

func TestMaxRowsBelowBatchSizeIsRejectedAtConstruction(t *testing.T) {
	_, err := NewServer(&recorder{}, &rejectSink{}, func(context.Context) error { return nil },
		Options{Token: testToken, BatchSize: 100, MaxRows: 10})
	if err == nil {
		t.Fatal("MaxRows below BatchSize should be rejected: no request could fill a chunk")
	}
}
