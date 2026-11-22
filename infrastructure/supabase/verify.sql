-- ROADGUARD AI — post-cutover verification (SQL Editor).
-- Every row should read `true` / the expected non-zero count.
-- Safe: read-only.

-- 1. Schema present and at head
select
    (select count(*) from information_schema.tables
      where table_schema = 'public' and table_type = 'BASE TABLE') as public_tables,
    (select version_num from alembic_version) as alembic_head;

-- 2. RLS enabled and policies present
select
    count(*) filter (where c.relrowsecurity) as rls_tables,
    (select count(*) from pg_policies where schemaname = 'public') as policies,
    count(*) filter (
        where c.relrowsecurity
          and exists (select 1 from pg_policy p where p.polrelid = c.oid)
    ) as tables_with_a_policy
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'r';

-- 3. Policies really key off the tenant setting
select count(*) as policies_using_current_organization_id
from pg_policies
where schemaname = 'public'
  and coalesce(qual, '') like '%current_organization_id%';

-- 4. Runtime role cannot bypass RLS
select rolname, rolsuper, rolbypassrls, rolcanlogin, rolinherit
from pg_roles where rolname = 'roadguard_app';

-- 5. Audit trail is append-only for the runtime role
select
    has_table_privilege('roadguard_app', 'audit_logs', 'SELECT') as can_select,
    has_table_privilege('roadguard_app', 'audit_logs', 'INSERT') as can_insert,
    has_table_privilege('roadguard_app', 'audit_logs', 'UPDATE') as can_update_must_be_false,
    has_table_privilege('roadguard_app', 'audit_logs', 'DELETE') as can_delete_must_be_false;

-- 6. PostGIS geography columns for the map
select f_table_name, f_geography_column, type
from geography_columns
where f_table_schema = 'public'
order by f_table_name;
