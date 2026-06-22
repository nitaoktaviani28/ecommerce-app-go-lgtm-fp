# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /app

COPY observability/ ./observability/
COPY services/product/go.mod services/product/go.sum* ./services/product/

WORKDIR /app/services/product
RUN go mod download

COPY services/product/ ./

RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o product-service .

# Final stage
FROM alpine:3.18

RUN apk --no-cache add ca-certificates

WORKDIR /root/

COPY --from=builder /app/services/product/product-service .

EXPOSE 8080

CMD ["./product-service"]
