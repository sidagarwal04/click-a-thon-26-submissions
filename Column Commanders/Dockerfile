# ---- build stage ----
FROM golang:1.25-alpine AS builder

WORKDIR /app

# Install CA certificates in the builder so we can copy them to scratch
RUN apk --no-cache add ca-certificates

# Cache dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy source and build a statically linked binary
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /app/server ./main.go

# ---- runtime stage ----
FROM scratch

# Required for TLS connections to ClickHouse Cloud
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

COPY --from=builder /app/server /server

EXPOSE 8080

ENTRYPOINT ["/server"]
