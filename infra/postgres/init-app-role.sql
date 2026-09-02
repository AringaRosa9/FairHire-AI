DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fairhire_app') THEN
    CREATE ROLE fairhire_app
      LOGIN
      PASSWORD 'fairhire_app_local_only'
      NOSUPERUSER
      NOCREATEDB
      NOCREATEROLE
      NOINHERIT;
  END IF;
END
$$;

