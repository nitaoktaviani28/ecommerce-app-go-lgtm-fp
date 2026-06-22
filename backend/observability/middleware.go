package observability

import (
	"log"
	"net/http"
	"time"
)

func loggingMiddleware(serviceName string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		log.Printf("[%s] [REQUEST] method=%s path=%s remote=%s", serviceName, r.Method, r.URL.Path, r.RemoteAddr)
		next.ServeHTTP(w, r)
		log.Printf("[%s] [RESPONSE] method=%s path=%s duration=%s", serviceName, r.Method, r.URL.Path, time.Since(start))
	})
}

func WrapHandler(serviceName string, handler http.Handler) http.Handler {
	h := loggingMiddleware(serviceName, handler)
	h = TracingMiddleware(serviceName, h)
	return h
}
