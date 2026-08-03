-- Human triage workflow (detected/investigating/resolved/false) was removed
-- from the Baseline dashboard. Drops the table for databases that already
-- ran the old 002_incident_triage migration; a no-op on fresh databases.

DROP TABLE IF EXISTS incident_triage;
