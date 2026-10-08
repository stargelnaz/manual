-- Manual schema: canonical structure in `nodes`, translatable text in `blocks`.
--
-- The 2023 Manual paragraph numbers are canonical. A translation may not renumber,
-- reorder, insert or drop a numbered paragraph. That is not enforced with a check —
-- it is unrepresentable: `nodes` has no `lang` column, so there is nowhere to put a
-- divergent number. Only `blocks` varies by language.
--
-- Safe to re-run.

create extension if not exists pg_trgm;

-- ---------------------------------------------------------------- nodes
create table if not exists public.nodes (
  key            text primary key,
  role           text not null check (role in ('paragraph','heading','note','part')),
  number         text,
  number_visible boolean not null default false,
  sort_key       int[],
  -- Self-referencing, and deferred: the loader writes in batches, so a child can
  -- land in the same transaction as its parent without ordering games.
  parent_key     text references public.nodes(key) on delete restrict
                   deferrable initially deferred,
  section_key    text references public.nodes(key) on delete restrict
                   deferrable initially deferred,
  level          smallint check (level between 1 and 3),
  doc_order      integer not null,

  -- "order" is reserved in SQL, hence doc_order. Gapped by 1000 so a paragraph can
  -- be inserted without renumbering every row.
  constraint nodes_doc_order_key unique (doc_order),
  -- A visible number must have a number to show, and a number must be sortable.
  constraint nodes_number_visible_has_number
    check (not number_visible or number is not null),
  constraint nodes_number_has_sort_key
    check ((number is null) = (sort_key is null)),
  -- Nothing may be its own parent or its own section.
  constraint nodes_no_self_parent  check (parent_key is distinct from key),
  constraint nodes_no_self_section check (section_key is distinct from key)
);

create index if not exists nodes_doc_order_idx   on public.nodes (doc_order);
create index if not exists nodes_parent_idx      on public.nodes (parent_key);
create index if not exists nodes_section_idx     on public.nodes (section_key);
create index if not exists nodes_sort_key_idx    on public.nodes (sort_key);
create index if not exists nodes_number_idx      on public.nodes (number) where number is not null;

comment on table  public.nodes is
  'Canonical, language-independent structure. One row per addressable node for ALL languages.';
comment on column public.nodes.parent_key is
  'Numeric hierarchy: 10.1 -> 10.';
comment on column public.nodes.section_key is
  'Structural containment: 10 -> "X. Christian Holiness" -> "ARTICLES OF FAITH" -> PART II. Walk transitively for "everything under PART III".';
comment on column public.nodes.number_visible is
  'False for generated keys — headings, the Foreword, standalone notes.';

-- ---------------------------------------------------------------- blocks
create table if not exists public.blocks (
  id          text primary key,
  node_key    text not null references public.nodes(key) on delete cascade,
  lang        text not null,
  ordinal     smallint not null check (ordinal >= 0),
  kind        text not null,
  marker      text,
  body        text not null check (body <> ''),
  source_line integer,
  is_lead     boolean not null default false,

  constraint blocks_node_lang_ordinal_key unique (node_key, lang, ordinal)
);

create index if not exists blocks_node_lang_idx on public.blocks (node_key, lang, ordinal);
create index if not exists blocks_lang_idx      on public.blocks (lang);
create index if not exists blocks_kind_idx      on public.blocks (kind);
create index if not exists blocks_body_trgm_idx on public.blocks using gin (body gin_trgm_ops);

comment on table  public.blocks is
  'Translatable text. One row per w:p per language.';
comment on column public.blocks.ordinal is
  'Position within the node. Alignment across languages is exact at the node level and by ordinal within it — a translation may legitimately split or merge blocks.';
comment on column public.blocks.body is
  'Inline markup limited to <em>, <b>, <sc>. Punctuation belonging to the sentence sits outside the emphasis; punctuation belonging to a label sits inside.';

-- ---------------------------------------------------------------- reading order
-- The document start to finish. This is the query the reader app runs.
create or replace view public.manual_reading_order as
  select b.id, b.lang, b.kind, b.marker, b.body, b.is_lead, b.ordinal,
         n.key as node_key, n.role, n.number, n.number_visible,
         n.section_key, n.doc_order
    from public.blocks b
    join public.nodes  n on n.key = b.node_key
   order by n.doc_order, b.ordinal;

comment on view public.manual_reading_order is
  'Blocks in document order. nodes.doc_order then blocks.ordinal reproduces the source exactly.';

-- ---------------------------------------------------------------- security
alter table public.nodes  enable row level security;
alter table public.blocks enable row level security;

-- The Manual is public text: anyone may read it. Writes go through the loader with
-- the service role key, which bypasses RLS; no policy grants write to anon.
drop policy if exists nodes_read_all  on public.nodes;
drop policy if exists blocks_read_all on public.blocks;
create policy nodes_read_all  on public.nodes  for select to anon, authenticated using (true);
create policy blocks_read_all on public.blocks for select to anon, authenticated using (true);
