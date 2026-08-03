package main

import (
	"database/sql"
	"errors"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

func main() {
	port := os.Getenv("RCA_ENGINE_PORT")
	if port == "" {
		port = "8081"
	}

	conn, err := ConnectClickHouse()
	if err != nil {
		log.Fatalf("Failed to connect to ClickHouse: %v", err)
	}

	engine := NewRCAEngine(conn)

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"status":     "ok",
			"engine":     "go-rca-engine",
			"clickhouse": "connected",
		})
	})

	http.HandleFunc("/analyze", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.Method != http.MethodPost && r.Method != http.MethodGet {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		var req AnalyzeRequest
		if r.Method == http.MethodPost {
			json.NewDecoder(r.Body).Decode(&req)
		} else {
			req.Metric = r.URL.Query().Get("metric")
			req.WindowStart = r.URL.Query().Get("window_start")
			req.WindowEnd = r.URL.Query().Get("window_end")
		}

		evidence, err := engine.PerformAnalysis(r.Context(), req)
		if err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				w.WriteHeader(http.StatusNotFound)
			} else {
				w.WriteHeader(http.StatusInternalServerError)
			}
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}

		json.NewEncoder(w).Encode(evidence)
	})

	http.HandleFunc("/detect", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		metric := r.URL.Query().Get("metric")
		if metric == "" {
			anomalies, err := engine.FindAllAnomalies(r.Context())
			if err != nil {
				w.WriteHeader(http.StatusInternalServerError)
				json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
				return
			}
			json.NewEncoder(w).Encode(anomalies)
			return
		}

		anomaly, err := engine.FindTopAnomaly(r.Context(), metric)
		if err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				w.WriteHeader(http.StatusNotFound)
			} else {
				w.WriteHeader(http.StatusInternalServerError)
			}
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}

		json.NewEncoder(w).Encode(anomaly)
	})

	addr := fmt.Sprintf(":%s", port)
	log.Printf("🚀 Go RCA Engine listening on http://localhost%s", addr)
	server := &http.Server{
		Addr:         addr,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
	}

	if err := server.ListenAndServe(); err != nil {
		log.Fatalf("Server exited with error: %v", err)
	}
}
