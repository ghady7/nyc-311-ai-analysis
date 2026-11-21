-- ==============================================================================
-- Migration: 002_fix_execute_readonly_query_security_invoker.sql
-- Description: Remediates Supabase Security Advisor Linter 0028 & 0029
--              (anon_security_definer_function_executable &
--               authenticated_security_definer_function_executable).
--
-- Security Posture:
-- 1. Drops SECURITY DEFINER in favor of SECURITY INVOKER so the routine
--    executes strictly within the caller's role context (anon, authenticated,
--    service_role, or readonly_app) with zero superuser privilege escalation.
-- 2. Enforces explicit search_path TO 'public' to eliminate search-path injection.
-- 3. Retains multi-statement regex rejection, keyword blacklist, catalog
--    protection, and 30-second statement_timeout ceiling.
-- ==============================================================================

CREATE OR REPLACE FUNCTION public.execute_readonly_query(query_text text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO 'public'
AS $function$
DECLARE
    result JSONB;
BEGIN
    -- 1. Structural multi-statement rejection (semicolons)
    IF query_text ~* ';[[:space:]]*[^[:space:]]' THEN
        RAISE EXCEPTION 'Security violation: Multiple statements detected.';
    END IF;

    -- 2. Prohibited keywords and dangerous routines
    IF query_text ~* '\m(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|GRANT|REVOKE|COPY|CREATE|REPLACE|EXEC|EXECUTE|VACUUM|COMMENT|LOCK|SET|DO|BEGIN|COMMIT|ROLLBACK|MERGE|PG_SLEEP|PG_TERMINATE_BACKEND|PG_CANCEL_BACKEND|PG_READ_FILE|PG_LS_DIR|DBLINK)\M' THEN
        RAISE EXCEPTION 'Security violation: Prohibited SQL keywords or routines detected.';
    END IF;

    -- 3. Prohibit system catalogs and internal schemas (auth, vault, storage, pg_catalog sensitive views)
    IF query_text ~* '\m(pg_shadow|pg_authid|pg_user|pg_roles|pg_database|pg_tablespace|pg_stat_activity|pg_proc|pg_settings)\M'
       OR query_text ~* '\m(auth|vault|storage|realtime|supabase_migrations|extensions)\.' THEN
        RAISE EXCEPTION 'Security violation: Access to sensitive catalogs and internal schemas is prohibited.';
    END IF;

    -- 4. Statement timeout ceiling (30 seconds)
    PERFORM set_config('statement_timeout', '30000', true);

    -- 5. Safe execution restricted to public schema
    EXECUTE 'SELECT COALESCE(jsonb_agg(to_jsonb(t)), ''[]''::jsonb) FROM (' || query_text || ') t' INTO result;
    RETURN result;
END;
$function$;
