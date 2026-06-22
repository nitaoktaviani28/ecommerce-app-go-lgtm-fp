# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /app

COPY observability/ ./observability/
COPY services/payment/go.mod services/payment/go.sum* ./services/payment/

WORKDIR /app/services/payment
RUN go mod download

COPY services/payment/ ./

RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o payment-service .

# Final stage
FROM alpine:3.18

RUN apk --no-cache add ca-certificates

WORKDIR /root/

COPY --from=builder /app/services/payment/payment-service .

EXPOSE 8080

CMD ["./payment-service"]
