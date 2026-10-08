-- record_revision() is a trigger function; nobody needs to call it, and triggers
-- don't check EXECUTE when they fire. Keep it off the RPC surface.
revoke execute on function public.record_revision() from public, anon, authenticated;
