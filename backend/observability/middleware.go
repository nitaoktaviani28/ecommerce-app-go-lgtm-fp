package observability

import (
	"log"
	"net/http"
	"time"
)

// statusRecorder captures the response status code so it can be logged (default 200 if WriteHeader is never called).
type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *statusRecorder) WriteHeader(status int) {
	r.status = status
	r.ResponseWriter.WriteHeader(status)
}

func loggingMiddleware(serviceName string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		log.Printf("[%s] [REQUEST] method=%s path=%s remote=%s", serviceName, r.Method, r.URL.Path, r.RemoteAddr)
		next.ServeHTTP(rec, r)
		log.Printf("[%s] [RESPONSE] method=%s path=%s status=%d duration=%s", serviceName, r.Method, r.URL.Path, rec.status, time.Since(start))
	})
}

func WrapHandler(serviceName string, handler http.Handler) http.Handler {
	h := loggingMiddleware(serviceName, handler)
	h = TracingMiddleware(serviceName, h)
	return h
}
