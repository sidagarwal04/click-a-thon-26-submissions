# schema

One DDL file per table, numbered in dependency order: `init_db.sh` applies them in filename
order, and `03_event_state` is a view over `01_raw_events`.
Each file is idempotent (`CREATE TABLE IF NOT EXISTS`) so anyone can re-run the whole dir.
Ordering key choices get a comment saying why, and a line in `docs/assumptions.md`.
