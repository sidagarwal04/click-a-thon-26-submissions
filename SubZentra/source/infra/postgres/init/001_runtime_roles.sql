DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zentra_runtime') THEN
    CREATE ROLE zentra_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zentra_app') THEN
    CREATE ROLE zentra_app LOGIN PASSWORD 'zentra_app' NOSUPERUSER NOBYPASSRLS;
    GRANT zentra_runtime TO zentra_app;
  END IF;
END
$$;
