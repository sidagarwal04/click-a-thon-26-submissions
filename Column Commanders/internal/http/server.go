package httpserver

import (
	"log/slog"
	"net/http"

	"github.com/gin-gonic/gin"
	"go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin"
	"go.uber.org/zap"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/db"
	"clickhouse-go-service/internal/handler"
	"clickhouse-go-service/services/alertmanager"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/detectionv2"
)

// Server wraps gin.Engine with all routes registered.
type Server struct {
	router     *gin.Engine
	db         *db.Client
	cfg        *config.Config
	detEngine  *anomalydetector.DetectionEngine
	alertMgr   *alertmanager.Manager
	pipelineV2 *detectionv2.Pipeline
	logger     *zap.Logger  // used by upload handler (OTel trace metadata)
	slogger    *slog.Logger // used by core and anomaly handlers
}

// New creates a Server with all routes registered.
// Multipart files up to 32 MB are buffered in memory; larger files are spilled to disk.
func New(
	client *db.Client,
	cfg *config.Config,
	logger *zap.Logger,
	detEngine *anomalydetector.DetectionEngine,
	alertMgr *alertmanager.Manager,
	pipelineV2 *detectionv2.Pipeline,
	slogger *slog.Logger,
) *Server {
	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(corsMiddleware())
	r.Use(otelgin.Middleware("clickhouse-go-service")) // auto-instrument every request with a trace span
	r.MaxMultipartMemory = 32 << 20                    // 32 MB

	s := &Server{
		router:     r,
		db:         client,
		cfg:        cfg,
		detEngine:  detEngine,
		alertMgr:   alertMgr,
		pipelineV2: pipelineV2,
		logger:     logger,
		slogger:    slogger,
	}
	s.registerRoutes()
	return s
}

func (s *Server) registerRoutes() {
	h := handler.New(s.db, s.cfg, s.slogger)
	ah := handler.NewAnomalyHandler(s.detEngine, s.alertMgr)
	v2h := handler.NewDetectionV2Handler(s.pipelineV2)

	// Core routes
	s.router.GET("/health", gin.WrapF(h.Health))
	s.router.POST("/insert", gin.WrapF(h.Insert))
	s.router.POST("/batch", gin.WrapF(h.BatchInsert))
	s.router.POST("/upload", s.upload)

	// Anomaly detection routes
	api := s.router.Group("/api/v1")
	api.POST("/detect", gin.WrapF(ah.Detect))
	api.POST("/detect/auto", gin.WrapF(ah.DetectAuto))
	api.GET("/incidents", gin.WrapF(ah.ListIncidents))
	// gin.WrapF alone can't be used here: ah.GetIncident reads the id via the
	// stdlib r.PathValue("id"), which only gin's own c.Param("id") populates —
	// WrapF never bridges the two, so the id was always "" and every lookup
	// silently 404'd regardless of the URL. Bridge it explicitly.
	api.GET("/incidents/:id", func(c *gin.Context) {
		c.Request.SetPathValue("id", c.Param("id"))
		ah.GetIncident(c.Writer, c.Request)
	})
	api.GET("/incidents/:id/trace", func(c *gin.Context) {
		c.Request.SetPathValue("id", c.Param("id"))
		ah.GetIncidentTrace(c.Writer, c.Request)
	})

	v2 := s.router.Group("/api/v2")
	v2.POST("/detect/historical", gin.WrapF(v2h.Historical))
	v2.POST("/detect/realtime", gin.WrapF(v2h.RealTime))
	v2.GET("/episodes", gin.WrapF(v2h.ListEpisodes))
	v2.GET("/episodes/:id", gin.WrapF(v2h.GetEpisode))
}

// Handler returns the http.Handler for use with http.Server.
func (s *Server) Handler() http.Handler {
	return s.router
}

// corsMiddleware allows the frontend to call this service from a browser.
//
// The UI is served from a different origin, and its JSON POSTs are not "simple"
// requests, so the browser sends an OPTIONS preflight first. Without these
// headers every call from the page fails regardless of what the API returns.
//
// Wide open by design: authentication is out of scope and the service holds no
// user data. Restrict the origin before exposing this anywhere real.
func corsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		if origin == "" {
			origin = "*"
		}
		c.Header("Access-Control-Allow-Origin", origin)
		c.Header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type, Authorization, Traceparent, Tracestate, Baggage")
		c.Header("Access-Control-Max-Age", "86400")
		c.Writer.Header().Add("Vary", "Origin")
		c.Writer.Header().Add("Vary", "Access-Control-Request-Headers")
		if c.GetHeader("Access-Control-Request-Private-Network") == "true" {
			c.Header("Access-Control-Allow-Private-Network", "true")
		}

		if c.Request.Method == http.MethodOptions {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	}
}
