FROM alpine:3.22

RUN apk add --no-cache \
      bash \
      ca-certificates \
      coreutils \
      curl \
      gawk \
      grep \
      python3 \
      sed \
    && addgroup -S publisher \
    && adduser -S -G publisher publisher

WORKDIR /app

COPY policy ./policy
COPY sql ./sql
COPY tools/ch ./tools/ch
COPY tools/policy.sh ./tools/policy.sh
COPY tools/publish.sh ./tools/publish.sh
COPY tools/refresh-dashboard-fact.sh ./tools/refresh-dashboard-fact.sh
COPY tools/lib ./tools/lib
COPY deploy/publisher/entrypoint.sh /usr/local/bin/publisher-entrypoint
COPY deploy/publisher/healthcheck.sh /usr/local/bin/publisher-healthcheck

RUN chmod +x \
      /usr/local/bin/publisher-entrypoint \
      /usr/local/bin/publisher-healthcheck \
      tools/ch \
      tools/policy.sh \
      tools/publish.sh \
      tools/refresh-dashboard-fact.sh \
    && chown -R publisher:publisher /app

USER publisher

HEALTHCHECK --interval=20s --timeout=10s --start-period=10s --retries=3 \
  CMD ["publisher-healthcheck"]

ENTRYPOINT ["publisher-entrypoint"]
