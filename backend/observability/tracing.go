package observability

import (
	"context"
	"log"
	"net/http"
	"os"
	"time"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetrichttp"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
)

func InitTracing(serviceName string) func() {
	endpoint := getEnv("OTEL_EXPORTER_OTLP_ENDPOINT", "alloy.monitoring.svc.cluster.local:4318")

	ctx := context.Background()

	res, err := resource.New(
		ctx,
		resource.WithAttributes(
			semconv.ServiceName(serviceName),
			semconv.DeploymentEnvironment(getEnv("APP_ENV", "production")),
		),
	)
	if err != nil {
		log.Printf("[OTEL] Failed to create resource: %v", err)
		return func() {}
	}

	// --- Tracing ---
	traceExporter, err := otlptracehttp.New(
		ctx,
		otlptracehttp.WithEndpoint(endpoint),
		otlptracehttp.WithInsecure(),
	)
	if err != nil {
		log.Printf("[OTEL] Failed to create trace exporter: %v", err)
		return func() {}
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(traceExporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)

	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	// --- Metrics ---
	metricExporter, err := otlpmetrichttp.New(
		ctx,
		otlpmetrichttp.WithEndpoint(endpoint),
		otlpmetrichttp.WithInsecure(),
	)
	if err != nil {
		log.Printf("[OTEL] Failed to create metric exporter: %v", err)
	} else {
		mp := metric.NewMeterProvider(
			metric.WithResource(res),
			metric.WithReader(metric.NewPeriodicReader(metricExporter, metric.WithInterval(15*time.Second))),
		)
		otel.SetMeterProvider(mp)
		log.Printf("[OTEL] Metrics initialized for service=%s endpoint=%s", serviceName, endpoint)
	}

	log.Printf("[OTEL] Tracing initialized for service=%s endpoint=%s", serviceName, endpoint)

	return func() {
		if err := tp.Shutdown(ctx); err != nil {
			log.Printf("[OTEL] Trace shutdown error: %v", err)
		}
	}
}

func TracingMiddleware(serviceName string, next http.Handler) http.Handler {
	return otelhttp.NewHandler(next, serviceName)
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
