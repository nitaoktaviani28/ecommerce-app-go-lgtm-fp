module github.com/ecommerce/observability

go 1.21

require (
	go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp v0.49.0
	go.opentelemetry.io/otel v1.24.0
	go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp v1.24.0
	go.opentelemetry.io/otel/propagation v1.24.0
	go.opentelemetry.io/otel/sdk v1.24.0
)
