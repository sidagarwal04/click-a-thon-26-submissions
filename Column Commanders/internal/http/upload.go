package httpserver

import (
	"bytes"
	"context"
	"encoding/csv"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/parquet-go/parquet-go"
	"go.uber.org/zap"

	"clickhouse-go-service/internal/telemetry"
)

// tableNameRe restricts table names to safe SQL identifiers.
var tableNameRe = regexp.MustCompile(`^[a-zA-Z][a-zA-Z0-9_]{0,63}$`)

// upload handles POST /upload
//
// Multipart form fields:
//   - table  string  required – target ClickHouse table name
//   - file   file    required – CSV (.csv) or Parquet (.parquet) file
//
// The response body is {"inserted": <n>, "table": "<name>"}.
func (s *Server) upload(c *gin.Context) {
	ctx := c.Request.Context()
	log := telemetry.WithTraceMetadata(ctx, s.logger)

	table := strings.TrimSpace(c.PostForm("table"))
	if !tableNameRe.MatchString(table) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "table must match [a-zA-Z][a-zA-Z0-9_]{0,63}"})
		return
	}

	fh, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "file field is required"})
		return
	}

	ext := strings.ToLower(filepath.Ext(fh.Filename))

	// Start an independent Langfuse trace rooted at context.Background() so it
	// is completely decoupled from the ClickStack HTTP span created by otelgin.
	lfCtx, lfSpan := telemetry.NewLangfuseTrace("file-upload")
	defer lfSpan.End()
	telemetry.SetTraceName(lfSpan, "file-upload")
	telemetry.SetSpanInput(lfSpan, map[string]any{
		"table":      table,
		"file":       fh.Filename,
		"format":     ext,
		"size_bytes": fh.Size,
	})

	log.Info("upload started",
		zap.String("table", table),
		zap.String("file", fh.Filename),
		zap.String("format", ext),
		zap.Int64("size_bytes", fh.Size),
	)

	var inserted int

	switch ext {
	case ".csv":
		inserted, err = s.ingestCSV(lfCtx, table, fh, log)
	case ".parquet":
		inserted, err = s.ingestParquet(lfCtx, table, fh, log)
	default:
		c.JSON(http.StatusBadRequest, gin.H{
			"error": fmt.Sprintf("unsupported file type %q: use .csv or .parquet", ext),
		})
		return
	}

	if err != nil {
		telemetry.RecordSpanError(lfSpan, err)
		log.Error("ingest failed",
			zap.Error(err),
			zap.String("table", table),
			zap.String("file", fh.Filename),
		)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "ingest failed"})
		return
	}

	telemetry.SetSpanOutput(lfSpan, map[string]any{
		"inserted": inserted,
		"table":    table,
	})
	log.Info("upload complete",
		zap.String("table", table),
		zap.String("file", fh.Filename),
		zap.Int("inserted", inserted),
	)
	c.JSON(http.StatusOK, gin.H{"inserted": inserted, "table": table})
}

// ingestCSV reads the CSV file in streaming batches and inserts each batch into ClickHouse.
// The first row is treated as the header (column names).
func (s *Server) ingestCSV(ctx context.Context, table string, fh *multipart.FileHeader, log *zap.Logger) (inserted int, retErr error) {
	ctx, span := telemetry.StartSpan(ctx, "ingest-csv")
	defer func() {
		if retErr != nil {
			telemetry.RecordSpanError(span, retErr)
		} else {
			telemetry.SetSpanOutput(span, map[string]any{"rows_inserted": inserted})
		}
		span.End()
	}()

	telemetry.SetSpanInput(span, map[string]any{
		"table":      table,
		"file":       fh.Filename,
		"size_bytes": fh.Size,
	})

	f, err := fh.Open()
	if err != nil {
		return 0, fmt.Errorf("open file: %w", err)
	}
	defer f.Close()

	r := csv.NewReader(f)
	r.TrimLeadingSpace = true
	r.ReuseRecord = true

	rawHeaders, err := r.Read()
	if err != nil {
		return 0, fmt.Errorf("read CSV header: %w", err)
	}
	// Detect Git LFS pointer files — their first line is the LFS version URL.
	if len(rawHeaders) > 0 && strings.HasPrefix(rawHeaders[0], "version https://git-lfs.github.com/") {
		return 0, fmt.Errorf("file %q is a Git LFS pointer, not real data — run `git lfs pull` in the repo first", fh.Filename)
	}
	// Copy because ReuseRecord will overwrite the backing array on the next Read.
	cols := make([]string, len(rawHeaders))
	copy(cols, rawHeaders)

	batch := make([]map[string]any, 0, s.cfg.BatchMaxSize)

	for {
		record, err := r.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return inserted, fmt.Errorf("read CSV row: %w", err)
		}

		row := make(map[string]any, len(cols))
		for i, h := range cols {
			if i < len(record) {
				row[h] = record[i]
			}
		}
		batch = append(batch, row)

		if len(batch) >= s.cfg.BatchMaxSize {
			if err := s.db.InsertRows(ctx, table, cols, batch); err != nil {
				return inserted, err
			}
			inserted += len(batch)
			log.Debug("batch inserted", zap.Int("batch_size", len(batch)), zap.Int("total", inserted))
			batch = batch[:0]
		}
	}

	// Flush the final partial batch.
	if len(batch) > 0 {
		if err := s.db.InsertRows(ctx, table, cols, batch); err != nil {
			return inserted, err
		}
		inserted += len(batch)
		log.Debug("batch inserted", zap.Int("batch_size", len(batch)), zap.Int("total", inserted))
	}

	return inserted, nil
}

// ingestParquet reads the Parquet file in streaming batches and inserts each batch into ClickHouse.
func (s *Server) ingestParquet(ctx context.Context, table string, fh *multipart.FileHeader, log *zap.Logger) (inserted int, retErr error) {
	ctx, span := telemetry.StartSpan(ctx, "ingest-parquet")
	defer func() {
		if retErr != nil {
			telemetry.RecordSpanError(span, retErr)
		} else {
			telemetry.SetSpanOutput(span, map[string]any{"rows_inserted": inserted})
		}
		span.End()
	}()

	telemetry.SetSpanInput(span, map[string]any{
		"table":      table,
		"file":       fh.Filename,
		"size_bytes": fh.Size,
	})

	f, err := fh.Open()
	if err != nil {
		return 0, fmt.Errorf("open file: %w", err)
	}
	defer f.Close()

	// parquet-go requires an io.ReaderAt + size; read the entire file into a buffer.
	data, err := io.ReadAll(f)
	if err != nil {
		return 0, fmt.Errorf("read parquet data: %w", err)
	}

	pf, err := parquet.OpenFile(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return 0, fmt.Errorf("open parquet file: %w", err)
	}

	// NewGenericReader requires its type parameter to be `any` (or a concrete
	// struct) — `map[string]any` itself is not a valid type parameter and
	// panics inside the library's schema reflection. Each row still decodes
	// to a map[string]any at runtime for a flat/group schema; type-assert it.
	reader := parquet.NewGenericReader[any](pf)
	defer reader.Close()

	raw := make([]any, s.cfg.BatchMaxSize)
	var cols []string

	for {
		n, err := reader.Read(raw)
		if n > 0 {
			batch := make([]map[string]any, n)
			for i := 0; i < n; i++ {
				row, ok := raw[i].(map[string]any)
				if !ok {
					return inserted, fmt.Errorf("unexpected parquet row type %T (expected a flat record)", raw[i])
				}
				batch[i] = row
			}
			// Derive column list once from the first successful batch.
			if cols == nil {
				cols = sortedKeys(batch[0])
			}
			if insertErr := s.db.InsertRows(ctx, table, cols, batch); insertErr != nil {
				return inserted, insertErr
			}
			inserted += n
			log.Debug("batch inserted", zap.Int("batch_size", n), zap.Int("total", inserted))
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			return inserted, fmt.Errorf("read parquet rows: %w", err)
		}
	}

	return inserted, nil
}

// sortedKeys returns the map keys in sorted order for consistent column ordering.
func sortedKeys(row map[string]any) []string {
	keys := make([]string, 0, len(row))
	for k := range row {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}
