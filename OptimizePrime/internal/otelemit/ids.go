package otelemit

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
)

// NewTraceID returns a random 16-byte trace id, lower-case hex — the shape
// OTLP/HTTP JSON expects and the same shape a Langfuse emitter sharing this
// trace_id would need (docs/OBSERVABILITY.md — not built here, but the id
// format is chosen so it would not need to change if it were).
func NewTraceID() (string, error) {
	return randomHex(16)
}

// NewSpanID returns a random 8-byte span id, lower-case hex.
func NewSpanID() (string, error) {
	return randomHex(8)
}

func randomHex(n int) (string, error) {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return "", fmt.Errorf("read %d random bytes for otlp id: %w", n, err)
	}
	return hex.EncodeToString(b), nil
}
