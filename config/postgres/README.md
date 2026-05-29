# PostgreSQL Config

- `master-postgresql.conf` and `master-pg_hba.conf` configure the single PostgreSQL instance.
- No slave configuration is used in the single-instance setup.
- Live production uses the self-managed PostgreSQL container defined in `docker-compose.server.yml`.
- The production container name follows `quantmind-PostgreSQL-<version>`, and services reach it via the `quantmind-postgresql` network alias.
