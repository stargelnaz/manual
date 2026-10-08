-- The schema migration ran under a role whose objects miss the standard Supabase
-- default grants; restore them. RLS still gates anon/authenticated to read-only.
grant usage on schema public to anon, authenticated, service_role;
grant all on public.nodes, public.blocks to service_role;
grant select on public.nodes, public.blocks to anon, authenticated;
grant select on public.manual_reading_order to anon, authenticated, service_role;
