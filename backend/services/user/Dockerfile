# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /app

COPY observability/ ./observability/
COPY services/user/go.mod services/user/go.sum* ./services/user/

WORKDIR /app/services/user
RUN go mod download

COPY services/user/ ./

RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o user-service .

# Final stage
FROM alpine:3.18

RUN apk --no-cache add ca-certificates

WORKDIR /root/

COPY --from=builder /app/services/user/user-service .

EXPOSE 8080

CMD ["./user-service"]
