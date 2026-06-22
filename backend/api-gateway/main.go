package main

import (
	"fmt"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"

	"github.com/ecommerce/observability"
)

func corsMiddleware(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, PATCH")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, traceparent, tracestate")
		w.Header().Set("Access-Control-Max-Age", "3600")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}

		h.ServeHTTP(w, r)
	})
}

func proxyHandler(targetURL *url.URL, pathPrefix string) http.HandlerFunc {
	proxy := httputil.NewSingleHostReverseProxy(targetURL)
	return func(w http.ResponseWriter, r *http.Request) {
		r.URL.Path = strings.TrimPrefix(r.URL.Path, "/api")
		r.URL.RawPath = strings.TrimPrefix(r.URL.RawPath, "/api")
		r.RequestURI = ""
		r.Host = targetURL.Host
		proxy.ServeHTTP(w, r)
	}
}

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"status":"healthy","service":"api-gateway"}`)
	})

	productURL, _ := url.Parse("http://product-service.ecommerce.svc.cluster.local:8080")
	mux.HandleFunc("/api/products/", proxyHandler(productURL, "/api"))
	mux.HandleFunc("/api/products", proxyHandler(productURL, "/api"))

	orderURL, _ := url.Parse("http://order-service.ecommerce.svc.cluster.local:8080")
	mux.HandleFunc("/api/orders/", proxyHandler(orderURL, "/api"))
	mux.HandleFunc("/api/orders", proxyHandler(orderURL, "/api"))

	userURL, _ := url.Parse("http://user-service.ecommerce.svc.cluster.local:8080")
	mux.HandleFunc("/api/users/", proxyHandler(userURL, "/api"))
	mux.HandleFunc("/api/users", proxyHandler(userURL, "/api"))
	mux.HandleFunc("/api/auth/", proxyHandler(userURL, "/api"))
	mux.HandleFunc("/api/auth", proxyHandler(userURL, "/api"))

	paymentURL, _ := url.Parse("http://payment-service.ecommerce.svc.cluster.local:8080")
	mux.HandleFunc("/api/payments/", proxyHandler(paymentURL, "/api"))
	mux.HandleFunc("/api/payments", proxyHandler(paymentURL, "/api"))

	observability.Run("api-gateway", corsMiddleware(mux))
}