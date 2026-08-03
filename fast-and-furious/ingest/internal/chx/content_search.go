package chx

import (
	"context"
	"fmt"
	"strings"

	"github.com/ClickHouse/clickhouse-go/v2"
)

// ContentInfo is a catalogue row as a human picks it: the id the generator needs
// plus the title and type that make it recognisable in a UI.
//
// Deliberately distinct from ContentRef, which is the minimum a generated event
// needs to be joinable. Nothing in the write path should depend on a title.
type ContentInfo struct {
	ContentID int64  `json:"content_id"`
	Title     string `json:"title"`
	VideoType string `json:"video_type"`
	Category  string `json:"category"`
}

// Ref narrows a picked catalogue row to what the generator consumes.
func (c ContentInfo) Ref() ContentRef {
	return ContentRef{ContentID: c.ContentID, VideoType: c.VideoType}
}

// SearchContent finds catalogue rows by title or category substring, or by exact
// content id, for a content picker.
//
// Reads content_current (the argMax view) rather than content_dim, so a
// re-uploaded catalogue shows its newest version without waiting on a merge.
//
// The predicate is parameterised rather than interpolated. A title box is
// untrusted input, and this is the one query in the module where a naive
// fmt.Sprintf of the user's string would be an injection.
func (c *Client) SearchContent(ctx context.Context, query string, limit int) ([]ContentInfo, error) {
	if limit <= 0 || limit > 500 {
		limit = 50
	}
	query = strings.TrimSpace(query)

	// An empty query lists the head of the catalogue, so the picker is useful
	// before anything has been typed. Ordering by title length first surfaces
	// short, recognisable titles ahead of long ones.
	sql := fmt.Sprintf(`
		SELECT content_id, title, video_type, category
		FROM %s.content_current
		WHERE {q:String} = ''
		   OR positionCaseInsensitive(title, {q:String}) > 0
		   OR positionCaseInsensitive(category, {q:String}) > 0
		   OR toString(content_id) = {q:String}
		ORDER BY length(title), content_id
		LIMIT %d`, c.Database, limit)

	rows, err := c.Conn.Query(ctx, sql, clickhouse.Named("q", query))
	if err != nil {
		return nil, fmt.Errorf("search content: %w", err)
	}
	defer rows.Close()

	out := make([]ContentInfo, 0, limit)
	for rows.Next() {
		var ci ContentInfo
		if err := rows.Scan(&ci.ContentID, &ci.Title, &ci.VideoType, &ci.Category); err != nil {
			return nil, fmt.Errorf("scan content row: %w", err)
		}
		out = append(out, ci)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate content search: %w", err)
	}
	return out, nil
}

// ContentRefsByID resolves an explicit id list to the refs the generator needs.
//
// Ids absent from the catalogue are dropped, and the caller compares len(out)
// against len(ids) to report what was ignored. Dropping rather than failing is
// deliberate: a stale id pinned in a dashboard should not block a run. But it
// must be *reported*, because generating traffic for an id with no catalogue row
// yields a 0% dictionary join rate and hides exactly the enrichment bug the join
// exists to catch.
func (c *Client) ContentRefsByID(ctx context.Context, ids []int64) ([]ContentRef, error) {
	if len(ids) == 0 {
		return nil, nil
	}
	sql := fmt.Sprintf(
		"SELECT content_id, video_type FROM %s.content_current WHERE content_id IN {ids:Array(Int64)} ORDER BY content_id",
		c.Database)

	rows, err := c.Conn.Query(ctx, sql, clickhouse.Named("ids", ids))
	if err != nil {
		return nil, fmt.Errorf("resolve content ids: %w", err)
	}
	defer rows.Close()

	out := make([]ContentRef, 0, len(ids))
	for rows.Next() {
		var ref ContentRef
		if err := rows.Scan(&ref.ContentID, &ref.VideoType); err != nil {
			return nil, fmt.Errorf("scan content ref: %w", err)
		}
		out = append(out, ref)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate content refs: %w", err)
	}
	return out, nil
}
