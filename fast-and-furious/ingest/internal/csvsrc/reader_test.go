package csvsrc

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestParseContentID(t *testing.T) {
	tests := []struct {
		name  string
		in    string
		want  int64
		isErr bool
	}{
		{"ordinary id", "21311522", 21311522, false},
		{"largest observed", "2078177474", 2078177474, false},
		// The catalogue stores -987654322 as an unsigned 64-bit value. Reading
		// it as a huge positive number would create a catalogue entry no event
		// can ever join to.
		{"negative cast to unsigned", "18446744072721897294", -987654322, false},
		{"already negative", "-987654322", -987654322, false},
		{"empty", "", 0, true},
		{"not a number", "abc", 0, true},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ParseContentID(tc.in)
			if tc.isErr {
				if err == nil {
					t.Fatalf("ParseContentID(%q) = %d, want error", tc.in, got)
				}
				return
			}
			if err != nil {
				t.Fatalf("ParseContentID(%q): unexpected error %v", tc.in, err)
			}
			if got != tc.want {
				t.Errorf("ParseContentID(%q) = %d, want %d", tc.in, got, tc.want)
			}
		})
	}
}

func TestParseEpochMillis(t *testing.T) {
	// A real timestamp from the extract.
	got, err := ParseEpochMillis("1785062007336")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if want := int64(1785062007336); got.UnixMilli() != want {
		t.Errorf("UnixMilli = %d, want %d", got.UnixMilli(), want)
	}
	if got.Location() != time.UTC {
		t.Errorf("location = %v, want UTC", got.Location())
	}

	// A producer rendering epochs as floats is tolerated when the fraction is
	// zero, and rejected when it would silently lose precision.
	if _, err := ParseEpochMillis("1785062007336.0"); err != nil {
		t.Errorf("trailing .0 should be accepted: %v", err)
	}
	if _, err := ParseEpochMillis("1785062007336.5"); err == nil {
		t.Error("sub-millisecond precision should be rejected, not truncated")
	}

	// Wrong-unit detection. A seconds-scale value would land the row in 1970
	// and quietly corrupt every concurrency bucket.
	for _, bad := range []string{"1785062007", "1785062007336000", "0", "-5", ""} {
		if _, err := ParseEpochMillis(bad); err == nil {
			t.Errorf("ParseEpochMillis(%q) should have failed", bad)
		}
	}
}

func TestNormalizeHexID(t *testing.T) {
	const lower = "94d660e9f4d438a91a80a351320be2b344b81faffe23a5be677f93a6684f8dac"
	const upper = "94D660E9F4D438A91A80A351320BE2B344B81FAFFE23A5BE677F93A6684F8DAC"

	// Case must normalize: the id is the session key, so 'a1b2' and 'A1B2' from
	// two producers must not become two different sessions.
	got, err := NormalizeHexID(lower)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != upper {
		t.Errorf("NormalizeHexID(lower) = %s, want %s", got, upper)
	}

	for _, bad := range []string{"", "ABC", upper + "0", upper[:63] + "Z"} {
		if _, err := NormalizeHexID(bad); err == nil {
			t.Errorf("NormalizeHexID(%q) should have failed", bad)
		}
	}
}

// TestEventReaderMapsColumnsByName is the property that protects the unseen
// day: the evaluation file comes from the same universe but nothing promises
// the same column order.
func TestEventReaderMapsColumnsByName(t *testing.T) {
	const sessionID = "94D660E9F4D438A91A80A351320BE2B344B81FAFFE23A5BE677F93A6684F8DAC"
	const userID = "7C7D3C62725140B3E15072BBD0166D5EA6C6811F0061AB2F53CA2179DF43858D"

	// Same data, columns in a deliberately different order from the source file.
	body := "user_id,video_session_id,event,event_type,platform,content_id," +
		"session_start_epoch,event_timestamp,app_version,country,audio_language," +
		"subtitle_language,player_version\n" +
		userID + "," + sessionID + ",Play,VideoPlay,JIO_ANDROID_TV,21311522," +
		"1785062007336,1785062009028,3.9.4,india,hin,OFF,1.8.2\n"

	path := filepath.Join(t.TempDir(), "shuffled.csv")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}

	r, err := OpenEvents(path)
	if err != nil {
		t.Fatalf("OpenEvents: %v", err)
	}
	defer r.Close()

	ev, reject, err := r.Next()
	if err != nil || reject != nil {
		t.Fatalf("Next: err=%v reject=%+v", err, reject)
	}
	if ev.VideoSessionID != sessionID {
		t.Errorf("session id = %q", ev.VideoSessionID)
	}
	if ev.UserID != userID {
		t.Errorf("user id = %q", ev.UserID)
	}
	if ev.Platform != "JIO_ANDROID_TV" {
		t.Errorf("platform = %q", ev.Platform)
	}
	if ev.ContentID != 21311522 {
		t.Errorf("content id = %d", ev.ContentID)
	}
	if ev.EventTimestamp.UnixMilli() != 1785062009028 {
		t.Errorf("event time = %d", ev.EventTimestamp.UnixMilli())
	}
	if ev.SessionStartEpoch.UnixMilli() != 1785062007336 {
		t.Errorf("session start = %d", ev.SessionStartEpoch.UnixMilli())
	}

	if _, _, err := r.Next(); err != io.EOF {
		t.Errorf("expected EOF, got %v", err)
	}
}

// TestEventReaderMissingColumnFailsFast: a missing required column must abort
// the load, not produce 905K silently-wrong rows.
func TestEventReaderMissingColumnFailsFast(t *testing.T) {
	path := filepath.Join(t.TempDir(), "truncated.csv")
	if err := os.WriteFile(path, []byte("video_session_id,user_id\nA,B\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := OpenEvents(path); err == nil {
		t.Fatal("expected an error naming the missing columns")
	}
}

// TestEventReaderQuarantinesBadRows: a malformed row is held with its line
// number, and the rest of the file still loads.
func TestEventReaderQuarantinesBadRows(t *testing.T) {
	const good = "94D660E9F4D438A91A80A351320BE2B344B81FAFFE23A5BE677F93A6684F8DAC"
	const user = "7C7D3C62725140B3E15072BBD0166D5EA6C6811F0061AB2F53CA2179DF43858D"
	header := "video_session_id,user_id,content_id,event_type,event,event_timestamp," +
		"platform,app_version,country,audio_language,subtitle_language,player_version,session_start_epoch\n"
	rowFmt := func(sid, ts string) string {
		return sid + "," + user + ",21311522,VideoPlay,Play," + ts +
			",IPHONE,6.34.8,india,hin,OFF,1.8.2,1785062007336\n"
	}
	body := header +
		rowFmt(good, "1785062009028") + // ok
		rowFmt("TOOSHORT", "1785062009028") + // bad session id
		rowFmt(good, "17") + // bad timestamp
		rowFmt(good, "1785062009030") // ok

	path := filepath.Join(t.TempDir(), "dirty.csv")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	r, err := OpenEvents(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()

	var accepted int
	var reasons []string
	for {
		ev, reject, err := r.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatalf("Next: %v", err)
		}
		if reject != nil {
			reasons = append(reasons, reject.Reason)
			if reject.Line == 0 {
				t.Error("reject is missing its source line number")
			}
			continue
		}
		if ev != nil {
			accepted++
		}
	}
	if accepted != 2 {
		t.Errorf("accepted %d rows, want 2", accepted)
	}
	if len(reasons) != 2 {
		t.Fatalf("quarantined %d rows (%v), want 2", len(reasons), reasons)
	}
	if reasons[0] != ReasonBadSessionID || reasons[1] != ReasonBadTimestamp {
		t.Errorf("reasons = %v, want [%s %s]", reasons, ReasonBadSessionID, ReasonBadTimestamp)
	}
}

func TestContentReaderMapsEmptyToUnknown(t *testing.T) {
	// 1,089 catalogue rows have an empty video_type, 142 of them actually
	// played. Left empty, every GROUP BY grows a nameless bucket.
	body := "content_id,title,video_type,category\n2049025011,cirar fac,,\n"
	path := filepath.Join(t.TempDir(), "content.csv")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	r, err := OpenContent(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()

	c, reject, err := r.Next()
	if err != nil || reject != nil {
		t.Fatalf("Next: err=%v reject=%+v", err, reject)
	}
	if c.VideoType != "unknown" || c.Category != "unknown" {
		t.Errorf("video_type=%q category=%q, want both %q", c.VideoType, c.Category, "unknown")
	}
}

// TestContentReaderQuarantinesBadRows: the catalogue reader must honour the
// same contract as the event reader. One malformed row aborting the load would
// leave the whole catalogue — and the enrichment dictionary built from it —
// stale, which is a far worse outcome than one quarantined title.
func TestContentReaderQuarantinesBadRows(t *testing.T) {
	body := "content_id,title,video_type,category\n" +
		"2049025011,cirar fac,vod,drama\n" +
		"1,too,many,fields,here\n" + // structural: wrong field count
		"notanumber,bad id,vod,drama\n" + // semantic: unparseable id
		"2078177474,late fac,live,sport\n"

	path := filepath.Join(t.TempDir(), "dirty-content.csv")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	r, err := OpenContent(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()

	var accepted int
	var reasons []string
	for {
		c, reject, err := r.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatalf("a bad catalogue row aborted the load: %v", err)
		}
		if reject != nil {
			reasons = append(reasons, reject.Reason)
			if reject.Line == 0 {
				t.Error("reject is missing its source line number")
			}
			continue
		}
		if c != nil {
			accepted++
		}
	}

	if accepted != 2 {
		t.Errorf("accepted %d rows, want the 2 good ones", accepted)
	}
	if len(reasons) != 2 {
		t.Fatalf("quarantined %d rows (%v), want 2", len(reasons), reasons)
	}
	if reasons[0] != ReasonBadRow || reasons[1] != ReasonBadContentID {
		t.Errorf("reasons = %v, want [%s %s]", reasons, ReasonBadRow, ReasonBadContentID)
	}
}

// The unseen dataset (data/surprise_spec.md) adds video_resolution to the raw
// events and show_name to the catalogue. Both are read OPTIONALLY: present ->
// carried through, absent -> empty string, so the original 13-column extract and
// the 14-column surprise extract both load through one code path.
//
// The failure this guards against is not a crash. er.idx is a map, so a missing
// key yields the zero value and rec[0] would be returned -- silently handing back
// the FIRST column's value for the absent one. On the raw file column 0 is
// content_id, so video_resolution would have read as "21311522" for every row.

func TestEventReaderReadsOptionalVideoResolution(t *testing.T) {
	const sessionID = "94D660E9F4D438A91A80A351320BE2B344B81FAFFE23A5BE677F93A6684F8DAC"
	const userID = "7C7D3C62725140B3E15072BBD0166D5EA6C6811F0061AB2F53CA2179DF43858D"

	// content_id deliberately FIRST, matching the real surprise header, so that a
	// regression to rec[0] indexing shows up as the content id in the assertion.
	header := "content_id,video_session_id,user_id,event_type,event,event_timestamp," +
		"platform,app_version,country,audio_language,subtitle_language," +
		"player_version,session_start_epoch,video_resolution\n"
	row := "21311522," + sessionID + "," + userID + ",VideoPlay,Play,1785062009028," +
		"JIO_ANDROID_TV,3.9.4,india,hin,OFF,1.8.2,1785062007336,%s\n"

	for _, tc := range []struct{ name, raw, want string }{
		{"plain", "1920*1080", "1920*1080"},
		{"spaced kept verbatim at this layer", "1920 * 1080", "1920 * 1080"},
		{"ladder prefix", "Auto-1280*720", "Auto-1280*720"},
		{"na", "NA", "NA"},
		{"empty", "", ""},
	} {
		t.Run(tc.name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "surprise.csv")
			body := header + fmt.Sprintf(row, tc.raw)
			if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
				t.Fatal(err)
			}
			r, err := OpenEvents(path)
			if err != nil {
				t.Fatalf("OpenEvents: %v", err)
			}
			defer r.Close()

			ev, reject, err := r.Next()
			if err != nil || reject != nil {
				t.Fatalf("Next: err=%v reject=%+v", err, reject)
			}
			if ev.VideoResolution != tc.want {
				t.Errorf("VideoResolution = %q, want %q", ev.VideoResolution, tc.want)
			}
			// Normalization belongs to events_raw_to_clean_mv, not here: the
			// landing table is source-faithful.
			if ev.ContentID != 21311522 {
				t.Errorf("content id = %d — column mapping drifted", ev.ContentID)
			}
		})
	}
}

// The 13-column original extract must still load, with video_resolution empty
// rather than holding content_id's value.
func TestEventReaderToleratesAbsentVideoResolution(t *testing.T) {
	const sessionID = "94D660E9F4D438A91A80A351320BE2B344B81FAFFE23A5BE677F93A6684F8DAC"
	const userID = "7C7D3C62725140B3E15072BBD0166D5EA6C6811F0061AB2F53CA2179DF43858D"

	body := "content_id,video_session_id,user_id,event_type,event,event_timestamp," +
		"platform,app_version,country,audio_language,subtitle_language," +
		"player_version,session_start_epoch\n" +
		"21311522," + sessionID + "," + userID + ",VideoPlay,Play,1785062009028," +
		"JIO_ANDROID_TV,3.9.4,india,hin,OFF,1.8.2,1785062007336\n"

	path := filepath.Join(t.TempDir(), "original.csv")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	r, err := OpenEvents(path)
	if err != nil {
		t.Fatalf("OpenEvents on a 13-column file: %v", err)
	}
	defer r.Close()

	ev, reject, err := r.Next()
	if err != nil || reject != nil {
		t.Fatalf("Next: err=%v reject=%+v", err, reject)
	}
	if ev.VideoResolution != "" {
		t.Errorf("VideoResolution = %q, want empty — a missing column must not "+
			"fall through to another column's value", ev.VideoResolution)
	}
	if ev.ContentID != 21311522 {
		t.Errorf("content id = %d", ev.ContentID)
	}
}

func TestContentReaderReadsOptionalShowName(t *testing.T) {
	// With show_name, and without it. content_id is column 0 in both, so a
	// regression to rec[0] indexing surfaces as the id text in ShowName.
	for _, tc := range []struct{ name, body, want string }{
		{
			"present",
			"content_id,title,video_type,category,show_name\n7,T,movie,drama,fkcbb\n",
			"fkcbb",
		},
		{
			"absent",
			"content_id,title,video_type,category\n7,T,movie,drama\n",
			"",
		},
		{
			"present but empty",
			"content_id,title,video_type,category,show_name\n7,T,movie,drama,\n",
			"",
		},
	} {
		t.Run(tc.name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "content.csv")
			if err := os.WriteFile(path, []byte(tc.body), 0o600); err != nil {
				t.Fatal(err)
			}
			r, err := OpenContent(path)
			if err != nil {
				t.Fatalf("OpenContent: %v", err)
			}
			defer r.Close()

			c, reject, err := r.Next()
			if err != nil || reject != nil {
				t.Fatalf("Next: err=%v reject=%+v", err, reject)
			}
			if c.ShowName != tc.want {
				t.Errorf("ShowName = %q, want %q", c.ShowName, tc.want)
			}
			if c.ContentID != 7 {
				t.Errorf("content id = %d — column mapping drifted", c.ContentID)
			}
		})
	}
}
