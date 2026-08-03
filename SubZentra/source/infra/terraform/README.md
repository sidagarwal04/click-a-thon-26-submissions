# ZentraOS managed foundation

This stack provisions the Phase 0 Neon control plane and ClickHouse Cloud audit
service in US East. Terraform reads credentials from provider environment
variables:

- `NEON_API_KEY`
- `CLICKHOUSE_ORG_ID`
- `CLICKHOUSE_CLOUD_API_KEY`
- `CLICKHOUSE_CLOUD_API_SECRET`
- `TF_VAR_clickhouse_owner_password`
- `TF_VAR_clickhouse_allowed_cidr`

Use a remote backend configured by the operator. Terraform state and generated
plans may contain sensitive connection data and must not be committed.

After provisioning, apply the Postgres Alembic migration with the Neon owner URL.
Apply `infra/clickhouse/init/001_audit_entries.sql` to the managed ClickHouse
service as its owner, replacing the local runtime password with a secret-manager
value. The runtime identities receive only the grants established by those
migrations.
