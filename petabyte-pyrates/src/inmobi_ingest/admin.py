"""Admin role setup and schema migrations for ClickPipes compatibility."""

from __future__ import annotations

from psycopg import Connection

from inmobi_ingest.ddl import SCHEMA_NAME, TABLES

ADMIN_ROLE = "clickathon_admin"
REPLICATION_ROLE = "ubi_replication"
CONSOLE_ADMIN_ROLE = "chpg_console_admin"

ADD_AD_EVENTS_PK_SQL = f"""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = '{SCHEMA_NAME}.ad_events'::regclass
          AND contype = 'p'
    ) THEN
        ALTER TABLE {SCHEMA_NAME}.ad_events
            ADD COLUMN id BIGSERIAL PRIMARY KEY;
    END IF;
END
$$;
"""


def _role_exists(cur, role: str) -> bool:
    cur.execute("SELECT EXISTS (SELECT FROM pg_roles WHERE rolname = %s)", (role,))
    return bool(cur.fetchone()[0])


def setup_admin(conn: Connection) -> list[str]:
    """Create clickathon_admin, transfer ownership, and grant replication access."""
    actions: list[str] = []

    with conn.cursor() as cur:
        if not _role_exists(cur, ADMIN_ROLE):
            cur.execute(f"CREATE ROLE {ADMIN_ROLE}")
            actions.append(f"Created role {ADMIN_ROLE}")

        cur.execute(f"GRANT USAGE, CREATE ON SCHEMA {SCHEMA_NAME} TO {ADMIN_ROLE}")
        cur.execute(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {SCHEMA_NAME} TO {ADMIN_ROLE}")
        cur.execute(
            f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {SCHEMA_NAME} TO {ADMIN_ROLE}"
        )
        cur.execute(
            f"""
            ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA {SCHEMA_NAME}
                GRANT ALL PRIVILEGES ON TABLES TO {ADMIN_ROLE}
            """
        )
        cur.execute(
            f"""
            ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA {SCHEMA_NAME}
                GRANT ALL PRIVILEGES ON SEQUENCES TO {ADMIN_ROLE}
            """
        )

        cur.execute(f"ALTER SCHEMA {SCHEMA_NAME} OWNER TO {ADMIN_ROLE}")
        actions.append(f"Transferred schema {SCHEMA_NAME} ownership to {ADMIN_ROLE}")

        for table in TABLES:
            cur.execute(f"ALTER TABLE {SCHEMA_NAME}.{table} OWNER TO {ADMIN_ROLE}")
            actions.append(f"Transferred {SCHEMA_NAME}.{table} ownership to {ADMIN_ROLE}")

        cur.execute(f"GRANT {ADMIN_ROLE} TO postgres")
        actions.append(f"Granted {ADMIN_ROLE} to postgres")

        for member in (CONSOLE_ADMIN_ROLE, REPLICATION_ROLE):
            if _role_exists(cur, member):
                cur.execute(f"GRANT {ADMIN_ROLE} TO {member}")
                actions.append(f"Granted {ADMIN_ROLE} to {member}")

        if _role_exists(cur, REPLICATION_ROLE):
            cur.execute(f"GRANT USAGE ON SCHEMA {SCHEMA_NAME} TO {REPLICATION_ROLE}")
            cur.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {SCHEMA_NAME} TO {REPLICATION_ROLE}")
            cur.execute(
                f"""
                ALTER DEFAULT PRIVILEGES IN SCHEMA {SCHEMA_NAME}
                    GRANT SELECT ON TABLES TO {REPLICATION_ROLE}
                """
            )
            actions.append(f"Granted replication SELECT on {SCHEMA_NAME} to {REPLICATION_ROLE}")

    conn.commit()
    return actions


def add_ad_events_primary_key(conn: Connection) -> bool:
    """Add surrogate primary key to ad_events if missing. Returns True if added."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = '{SCHEMA_NAME}.ad_events'::regclass
                  AND contype = 'p'
            )
            """
        )
        has_pk = bool(cur.fetchone()[0])
        if has_pk:
            return False

        cur.execute(ADD_AD_EVENTS_PK_SQL)
    conn.commit()
    return True
