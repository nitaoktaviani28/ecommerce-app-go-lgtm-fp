# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /app

COPY observability/ ./observability/
COPY services/order/go.mod services/order/go.sum* ./services/order/

WORKDIR /app/services/order
RUN go mod download

COPY services/order/ ./

RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o order-service .

# Final stage
FROM alpine:3.18

RUN apk --no-cache add ca-certificates

WORKDIR /root/

COPY --from=builder /app/services/order/order-service .

EXPOSE 8080

CMD ["./order-service"]
