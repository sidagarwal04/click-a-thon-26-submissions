package chx

import (
	"context"
	"fmt"

	"github.com/ClickHouse/clickhouse-go/v2"

	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// InsertContent writes catalogue rows in one native batch.
//
// sourceVersion is the ReplacingMergeTree version. Using a monotonically
// increasing value (the loader passes the wall-clock nanosecond of the run)
// means re-loading a corrected catalogue converges to the new rows without a
// mutation and without a DROP.
// [official: insert-mutation-avoid-update]
func (c *Client) InsertContent(ctx context.Context, rows []model.Content, sourceVersion uint64, dedupToken string) error {
	if len(rows) == 0 {
		return nil
	}
	settings := clickhouse.Settings{"insert_deduplication_token": dedupToken}
	bctx := clickhouse.Context(ctx, clickhouse.WithSettings(settings))

	stmt := insertStatement(c.Database, "content_dim", model.ContentInsertColumns)
	batch, err := c.Conn.PrepareBatch(bctx, stmt)
	if err != nil {
		return fmt.Errorf("prepare content batch: %w", err)
	}
	for i := range rows {
		if err := batch.Append(rows[i].Values(sourceVersion)...); err != nil {
			_ = batch.Abort()
			return fmt.Errorf("append content row %d: %w", i, err)
		}
	}
	if err := batch.Send(); err != nil {
		return fmt.Errorf("send content batch: %w", err)
	}
	return nil
}

// ReloadContentDictionary forces the enrichment dictionary to pick up a fresh
// catalogue immediately instead of waiting out its LIFETIME.
//
// Reminder that this does NOT retract anything already enriched from the old
// values: rows denormalized from the dictionary must be re-derived by
// re-dirtying the affected sessions.
func (c *Client) ReloadContentDictionary(ctx context.Context) error {
	q := fmt.Sprintf("SYSTEM RELOAD DICTIONARY %s.content_dict", c.Database)
	if err := c.Conn.Exec(ctx, q); err != nil {
		return fmt.Errorf("reload content dictionary: %w", err)
	}
	return nil
}

// ContentRef is the minimum a generated event needs to be joinable.
type ContentRef struct {
	ContentID int64
	VideoType string
}

// SampleContent reads content ids from the catalogue.
//
// The generator draws from real catalogue rows rather than inventing ids, so
// generated traffic exercises the same dictionary join as replayed traffic. A
// generator that made up content ids would produce a 0% join rate and hide
// exactly the enrichment bug it should be catching.
func (c *Client) SampleContent(ctx context.Context, limit int) ([]ContentRef, error) {
	q := fmt.Sprintf(
		"SELECT content_id, video_type FROM %s.content_current ORDER BY content_id LIMIT %d",
		c.Database, limit)

	rowsIter, err := c.Conn.Query(ctx, q)
	if err != nil {
		return nil, fmt.Errorf("sample content: %w", err)
	}
	defer rowsIter.Close()

	var out []ContentRef
	for rowsIter.Next() {
		var ref ContentRef
		if err := rowsIter.Scan(&ref.ContentID, &ref.VideoType); err != nil {
			return nil, fmt.Errorf("scan content sample: %w", err)
		}
		out = append(out, ref)
	}
	if err := rowsIter.Err(); err != nil {
		return nil, fmt.Errorf("iterate content sample: %w", err)
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("content catalogue is empty — load it first: sonyliv-ingest content --file <ch-hackathon-content-data.csv>")
	}
	return out, nil
}
