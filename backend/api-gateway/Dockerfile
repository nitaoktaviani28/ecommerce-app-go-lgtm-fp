# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /app

# Copy observability package first
COPY observability/ ./observability/

# Copy api-gateway module
COPY api-gateway/go.mod api-gateway/go.sum* ./api-gateway/

WORKDIR /app/api-gateway
RUN go mod download

COPY api-gateway/ ./

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o api-gateway .

# Final stage
FROM alpine:3.18

RUN apk --no-cache add ca-certificates

WORKDIR /root/

# Copy binary from builder
COPY --from=builder /app/api-gateway/api-gateway .

EXPOSE 8080

CMD ["./api-gateway"]