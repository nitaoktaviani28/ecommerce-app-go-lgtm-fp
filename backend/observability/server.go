package observability

import (
	"log"
	"net/http"
	_ "net/http/pprof"
	"os"
)

func Run(serviceName string, handler http.Handler) {
	shutdown := InitTracing(serviceName)
	defer shutdown()

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	go func() {
		log.Printf("%s pprof on :6060", serviceName)
		http.ListenAndServe(":6060", nil)
	}()

	wrapped := WrapHandler(serviceName, handler)

	log.Printf("%s running on :%s", serviceName, port)
	if err := http.ListenAndServe(":"+port, wrapped); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
