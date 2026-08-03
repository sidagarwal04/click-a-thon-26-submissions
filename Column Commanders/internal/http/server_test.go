package httpserver

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestCORSMiddlewareAllowsFrontendTelemetryHeaders(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(corsMiddleware())
	router.POST("/api/v2/detect/historical", func(c *gin.Context) {
		c.Status(http.StatusOK)
	})

	request := httptest.NewRequest(http.MethodOptions, "/api/v2/detect/historical", nil)
	request.Header.Set("Origin", "http://127.0.0.1:5500")
	request.Header.Set("Access-Control-Request-Method", http.MethodPost)
	request.Header.Set("Access-Control-Request-Headers", "content-type,traceparent,tracestate,baggage")
	request.Header.Set("Access-Control-Request-Private-Network", "true")
	recorder := httptest.NewRecorder()

	router.ServeHTTP(recorder, request)

	if recorder.Code != http.StatusNoContent {
		t.Fatalf("preflight status = %d, want %d", recorder.Code, http.StatusNoContent)
	}
	allowed := strings.ToLower(recorder.Header().Get("Access-Control-Allow-Headers"))
	for _, header := range []string{"content-type", "traceparent", "tracestate", "baggage"} {
		if !strings.Contains(allowed, header) {
			t.Errorf("Access-Control-Allow-Headers %q does not include %q", allowed, header)
		}
	}
	if got := recorder.Header().Get("Access-Control-Allow-Origin"); got != "http://127.0.0.1:5500" {
		t.Errorf("Access-Control-Allow-Origin = %q", got)
	}
	if got := recorder.Header().Get("Access-Control-Allow-Private-Network"); got != "true" {
		t.Errorf("Access-Control-Allow-Private-Network = %q", got)
	}
}
