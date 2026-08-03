package model

import "time"

// Event is the primary record type stored in ClickHouse.
type Event struct {
	// ID is optional. When omitted, ClickHouse generates a UUID via DEFAULT.
	ID        string    `json:"id,omitempty"`
	Source    string    `json:"source"`
	EventType string    `json:"event_type"`
	Payload   string    `json:"payload"`
	Timestamp time.Time `json:"timestamp,omitempty"`
}

type InsertRequest struct {
	Event Event `json:"event"`
}

type BatchInsertRequest struct {
	Events []Event `json:"events"`
}

type InsertResponse struct {
	Inserted int    `json:"inserted"`
	Message  string `json:"message"`
}
