FROM postgres:16-alpine

LABEL org.opencontainers.image.title="quantmind-postgres-base" \
      org.opencontainers.image.description="QuantMind PostgreSQL base image with core schema bootstrap" \
      org.opencontainers.image.source="https://local/quantmind"

# SQL files are executed in lexical order by the postgres entrypoint.
COPY docker/postgres-base/initdb/ /docker-entrypoint-initdb.d/
COPY db/20260303.sql /docker-entrypoint-initdb.d/900-backup-20260303.sql
