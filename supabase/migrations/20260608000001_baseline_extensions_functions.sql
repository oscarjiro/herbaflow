-- Baseline (1/7): functions.
--
-- Clean ordered baseline regenerated from the live database, replacing the prior
-- incremental migration ledger. This set is schema-equivalent to production
-- (diff-verified on a throwaway Postgres). Replay order is 0001 -> 0007.
--
-- rls_auto_enable is an event-trigger function that turns on row-level security
-- for every new public table. The event trigger that invokes it is a
-- platform-global object (not part of the public schema) and is managed outside
-- this baseline; the function itself lives in public and is recreated here.

create or replace function public.rls_auto_enable() returns event_trigger
    language plpgsql security definer
    set search_path to 'pg_catalog'
    as $$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN
    SELECT *
    FROM pg_event_trigger_ddl_commands()
    WHERE command_tag IN ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
      AND object_type IN ('table','partitioned table')
  LOOP
     IF cmd.schema_name IS NOT NULL AND cmd.schema_name IN ('public') AND cmd.schema_name NOT IN ('pg_catalog','information_schema') AND cmd.schema_name NOT LIKE 'pg_toast%' AND cmd.schema_name NOT LIKE 'pg_temp%' THEN
      BEGIN
        EXECUTE format('alter table if exists %s enable row level security', cmd.object_identity);
        RAISE LOG 'rls_auto_enable: enabled RLS on %', cmd.object_identity;
      EXCEPTION
        WHEN OTHERS THEN
          RAISE LOG 'rls_auto_enable: failed to enable RLS on %', cmd.object_identity;
      END;
     ELSE
        RAISE LOG 'rls_auto_enable: skip % (either system schema or not in enforced list: %.)', cmd.object_identity, cmd.schema_name;
     END IF;
  END LOOP;
END;
$$;
