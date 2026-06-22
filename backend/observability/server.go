package observability

import (
	"log"
	"net/http"
	"os"
)

func Run(serviceName string, handler http.Handler) {
	shutdown := InitTracing(serviceName)
	defer shutdown()

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	wrapped := WrapHandler(serviceName, handler)

	log.Printf("%s running on :%s", serviceName, port)
	if err := http.ListenAndServe(":"+port, wrapped); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
