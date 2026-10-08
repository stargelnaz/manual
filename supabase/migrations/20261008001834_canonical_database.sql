-- The database becomes the canonical Manual.
--
-- Until now the Word document was the source and these tables were a copy of
-- manual.json, rebuilt and re-checked by tools/build.py on every run. From here on
-- text is edited in the database, where build.py never sees it, so:
--
--   1. every change to nodes and blocks is recorded in `revisions`;
--   2. the build gates that matter for editing become constraints and triggers;
--   3. the database mints node keys and block ids — node_keys.json is frozen.
--
-- Every constraint below was checked against the loaded data before it was written.

-- ---------------------------------------------------------------- revisions
-- Old and new row for every insert, update and delete. An upsert that changes
-- nothing records nothing. The 2023 load itself predates this table; its baseline is
-- manual.json at the commit that added this migration.
create table if not exists public.revisions (
  id          bigint generated always as identity primary key,
  table_name  text not null check (table_name in ('nodes','blocks')),
  row_key     text not null,
  op          text not null check (op in ('insert','update','delete')),
  old_row     jsonb,
  new_row     jsonb,
  changed_at  timestamptz not null default now(),
  -- The signed-in user when the change came through the API; null for the loader
  -- and the SQL editor, which is what db_role is for.
  changed_by  uuid,
  db_role     text not null
);

create index if not exists revisions_row_idx on public.revisions (table_name, row_key, changed_at);
create index if not exists revisions_at_idx  on public.revisions (changed_at);

comment on table public.revisions is
  'Every change to nodes and blocks since the database became canonical. Append-only.';

-- Security definer so that whoever may write a block may record its revision,
-- without being able to write to revisions directly.
create or replace function public.record_revision()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  pk text := case tg_table_name when 'nodes' then 'key' else 'id' end;
  o  jsonb := case when tg_op <> 'INSERT' then to_jsonb(old) end;
  n  jsonb := case when tg_op <> 'DELETE' then to_jsonb(new) end;
begin
  insert into public.revisions (table_name, row_key, op, old_row, new_row, changed_by, db_role)
  values (tg_table_name, coalesce(n, o) ->> pk, lower(tg_op), o, n,
          auth.uid(),
          coalesce(nullif(current_setting('role', true), 'none'), session_user));
  return null;
end $$;

drop trigger if exists nodes_revision_write  on public.nodes;
drop trigger if exists nodes_revision_update on public.nodes;
drop trigger if exists blocks_revision_write  on public.blocks;
drop trigger if exists blocks_revision_update on public.blocks;
create trigger nodes_revision_write after insert or delete on public.nodes
  for each row execute function public.record_revision();
create trigger nodes_revision_update after update on public.nodes
  for each row when (old is distinct from new) execute function public.record_revision();
create trigger blocks_revision_write after insert or delete on public.blocks
  for each row execute function public.record_revision();
create trigger blocks_revision_update after update on public.blocks
  for each row when (old is distinct from new) execute function public.record_revision();

-- No policies: readable only with the service role. Grants are explicit because
-- migrations here run under a role that misses Supabase's default grants (see
-- grant_table_privileges). Rows are written by record_revision() alone.
alter table public.revisions enable row level security;
revoke all on public.revisions from anon, authenticated;
grant select on public.revisions to service_role;

-- ---------------------------------------------------------------- keys
-- Same alphabet as tools/build.py: no 0/1/i/l/o, and a leading letter so a key can
-- never look like a paragraph number.
alter table public.nodes drop constraint if exists nodes_key_shape;
alter table public.nodes add constraint nodes_key_shape
  check (key ~ '^[a-hjkmnp-z][a-hjkmnp-z2-9]{5}$');

-- A key is never reused, even after its node is deleted: links and translations made
-- against the old node must not silently land on a new one. Deleted keys live on in
-- revisions, so that is checked too.
create or replace function public.mint_node_key()
returns text
language plpgsql
volatile
-- Definer, so the check sees deleted keys in revisions whatever the caller's RLS.
security definer
set search_path = ''
as $$
declare
  letters constant text := 'abcdefghjkmnpqrstuvwxyz';
  chars   constant text := letters || '23456789';
  k text;
begin
  loop
    k := substr(letters, 1 + floor(random() * length(letters))::int, 1);
    for i in 1..5 loop
      k := k || substr(chars, 1 + floor(random() * length(chars))::int, 1);
    end loop;
    exit when not exists (select 1 from public.nodes where key = k)
          and not exists (select 1 from public.revisions
                           where table_name = 'nodes' and row_key = k);
  end loop;
  return k;
end $$;

alter table public.nodes alter column key set default public.mint_node_key();
-- Not an anonymous RPC endpoint; only roles that can insert nodes need it.
revoke execute on function public.mint_node_key() from public, anon;
grant execute on function public.mint_node_key() to authenticated, service_role;

-- Block ids loaded from manual.json are sha1(lang|node_key|ordinal)[:8]. That formula
-- suits a build, not editing — moving a block would change its id — so new blocks
-- get a random id of the same shape.
alter table public.blocks alter column id set default left(md5(gen_random_uuid()::text), 8);

-- A key is identity. Changing one would orphan every link and translation made to it.
create or replace function public.nodes_guard()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' then
    if new.key <> old.key then
      raise exception 'node keys are permanent: % cannot become %', old.key, new.key;
    end if;
    return new;
  end if;
  -- DELETE: refuse while another node's text links here. The node's own blocks are
  -- about to cascade, so they don't count.
  if exists (select 1 from public.blocks
              where node_key <> old.key
                and body like '%<ref to="' || old.key || '">%') then
    raise exception 'node % is the target of a <ref>; remove the links first', old.key;
  end if;
  return old;
end $$;

drop trigger if exists nodes_guard on public.nodes;
create trigger nodes_guard before update of key or delete on public.nodes
  for each row execute function public.nodes_guard();

-- ---------------------------------------------------------------- numbers
-- sort_key is the number, split. build.py derived one from the other; now an edit
-- could change one and forget the other.
alter table public.nodes drop constraint if exists nodes_sort_key_matches_number;
alter table public.nodes add constraint nodes_sort_key_matches_number
  check (number is null or sort_key = string_to_array(number, '.')::int[]);

-- Paragraph numbers strictly increase in document order. Checked against the
-- nearest numbered neighbours at commit, so a renumbering can pass through
-- out-of-order states inside one transaction.
create or replace function public.nodes_number_order()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  cur  public.nodes;
  prev int[];
  nxt  int[];
begin
  select * into cur from public.nodes where key = new.key;
  if not found or cur.number is null then
    return null;
  end if;
  select sort_key into prev from public.nodes
   where number is not null and doc_order < cur.doc_order
   order by doc_order desc limit 1;
  select sort_key into nxt from public.nodes
   where number is not null and doc_order > cur.doc_order
   order by doc_order limit 1;
  if prev >= cur.sort_key or nxt <= cur.sort_key then
    raise exception 'paragraph % is out of order (previous %, next %)',
      cur.number, array_to_string(prev, '.'), array_to_string(nxt, '.');
  end if;
  return null;
end $$;

drop trigger if exists nodes_number_order on public.nodes;
create constraint trigger nodes_number_order
  after insert or update of number, sort_key, doc_order on public.nodes
  deferrable initially deferred
  for each row execute function public.nodes_number_order();

-- ---------------------------------------------------------------- block text
-- Only <em> <b> <sc> and <ref to="key">, properly nested, no ref inside a ref. The
-- reader parses bodies with a single stack and relies on all of this.
create or replace function public.manual_body_ok(body text)
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  m     text[];
  stack text[] := '{}';
begin
  if body ~ '<(?!/?(em|b|sc)>|ref to="[a-hjkmnp-z][a-hjkmnp-z2-9]{5}">|/ref>)' then
    return false;
  end if;
  for m in select regexp_matches(body, '<(/?)(em|b|sc|ref)(?: to="[^"]*")?>', 'g') loop
    if m[1] = '' then
      if m[2] = 'ref' and 'ref' = any (stack) then
        return false;
      end if;
      stack := stack || m[2];
    elsif cardinality(stack) = 0 or stack[cardinality(stack)] <> m[2] then
      return false;
    else
      stack := stack[1:cardinality(stack) - 1];
    end if;
  end loop;
  return cardinality(stack) = 0;
end $$;

alter table public.blocks drop constraint if exists blocks_body_markup;
alter table public.blocks add constraint blocks_body_markup
  check (public.manual_body_ok(body));

-- Every <ref> names a node that exists. Deferred, and re-reads the row, so a node
-- and the links to it can be added in either order within one transaction.
create or replace function public.blocks_refs_exist()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_body  text;
  missing text;
begin
  select b.body into v_body from public.blocks b where b.id = new.id;
  if not found then
    return null;
  end if;
  select r.k into missing
    from (select (regexp_matches(v_body, '<ref to="([^"]*)">', 'g'))[1] as k) r
   where not exists (select 1 from public.nodes n where n.key = r.k)
   limit 1;
  if missing is not null then
    raise exception 'block %: <ref to="%"> names no node', new.id, missing;
  end if;
  return null;
end $$;

drop trigger if exists blocks_refs_exist on public.blocks;
create constraint trigger blocks_refs_exist
  after insert or update of body on public.blocks
  deferrable initially deferred
  for each row execute function public.blocks_refs_exist();

comment on column public.blocks.body is
  'Inline markup limited to <em>, <b>, <sc> and <ref to="node key">, properly nested (enforced by blocks_body_markup). Punctuation belonging to the sentence sits outside the emphasis; punctuation belonging to a label sits inside.';
comment on column public.blocks.source_line is
  'w:p index in the 2023 source document. Null for blocks written in the database.';
comment on column public.nodes.key is
  'Permanent opaque key. Minted by mint_node_key(); never changed, never reused.';
