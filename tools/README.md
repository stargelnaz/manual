# Tools

The database is the canonical Manual. Two tools work against it day to day:

```sh
python tools/export.py          # database -> manual.json, then the gates
python tools/export.py --check  # the gates against the database, writes nothing
```

`export.py` reads through the public read policy, so the anon key in `.env` is
enough. It writes `manual.json` in the shape the build always wrote, and runs the
whole-document gates in `gates.py` — the ones a row-level constraint can't express
(parts count, section cycles, numbering order across the document, ragged tables).
Commit the snapshot after editing: git is the readable history, and the free plan
keeps no backups you can download.

The database guards each row itself (migration `20261008001834`):

- every insert, update and delete on `nodes` and `blocks` lands in `revisions`, old
  and new row, with the role and the signed-in user; no-op writes record nothing
- block bodies allow only `<em> <b> <sc> <ref to="key">`, properly nested
- a `<ref>` must name an existing node, and a node that is linked to can't be deleted
- paragraph numbers strictly increase in document order; `sort_key` matches `number`
- node keys are permanent: they can't be changed, and `mint_node_key()` — the
  column default — never reissues one, even after its node is deleted
- new blocks get a random 8-character id by default

## The 2023 import

How the English Word document became the database. Kept so the derivation stays
reproducible; nothing here writes to the canonical text.

```sh
python tools/extract.py     # docx  -> build/paras.json
python tools/normalize.py   #       -> build/paras_norm.json  (+ build/normreport.json)
python tools/build.py       #       -> build/manual.json
```

Everything lands in `build/` and is disposable. `overrides.json` holds the
hand-made decisions the import applied.

Node keys came from `node_keys.json`, which maps each 2023 locator (paragraph
number, or a generated anchor such as `10.1~h1`) to a permanent opaque key like
`k7xq2m`. It is frozen: the build stops on a locator it doesn't know, and `--mint`
is retired, because a key minted here could collide with one the database minted.

`python tools/styles_probe.py` is a check, not a stage — it verifies that the Word
character styles mean "emphasis" and nothing else. Run it if the source document is
ever re-exported.

## Why three stages

**extract** emits every `w:p` twice. `typed` is the hand-typed pseudo-HTML, which is
the only place block semantics live (`className`). `formatted` is the same paragraph
rebuilt from Word's own character styles, which is the only place *reliable* emphasis
lives — the typed `<em>`/`<b>` tags leave 13 and 24 blocks unclosed respectively,
while the character styles leave none. Everything downstream takes structure from one
and inline formatting from the other.

**normalize** applies the punctuation rule (see `plan.md`) and the hand decisions in
`overrides.json`.

**build** assigns nodes and blocks, then runs the gates.

## Gates

`build.py` asserts, every run:

- every node has a registry key; keys unique and well-formed; block ids unique; every block has a node
- every `parent_key` and `section_key` resolves; no cycles in the section chain
- paragraph numbers strictly increasing
- `nodes.order` + `blocks.ordinal` reproduces document order — the query the app runs
- the numbered paragraphs equal the tagged set plus exactly `{346.3}`; the only
  numbered headings are the rituals, 700–709
- every number taken off the front of a block lands on a node
- no block body contains markup outside `<em> <b> <sc> <ref to="key">`; all inline tags balance
- every `<ref>` points to an existing node; every cross-reference item that names no
  node is listed in `overrides.json` under `references`, and every listed item still
  is one (the patterns are in `refs.py`, shared with normalize)
- exactly 9 parts — I-VIII and X

PART IX (the auxiliary constitutions) was not in the 2023 import. It is being added
to the database directly, one organization at a time: NYI (¶810) went in on
2026-10-08 from `languages/english/NYI.docx`; NMI (¶811) and NDI (¶812) follow.
`PARTS` in `gates.py` is now 10. PART XI (the 900s appendix) still sits under
PART X, because the 2023 export had no heading for it.

Block ids are `sha1(lang|node_key|ordinal)[:8]`, so two consecutive builds produce a
byte-identical file. That makes the idempotency requirement testable with `diff`.

## Source defects handled here

Documented in case a re-export reintroduces them:

- a leading `"1. "` is not always a paragraph number — numbered list items in the
  forms and rituals otherwise mint duplicate nodes for ¶1-¶8
- 22 paragraphs carry a stray `<` before the number (`<530.10.`); ¶220.3 has no
  period after its number
- `PART III` is typed `<DIV CLASSNAME='PART-NUMBER'>` in uppercase — a
  case-sensitive match silently demotes it to body text
- a `part-chapter-list` can reappear far from its part (w:p 209, 1741), so it is only
  folded into the part node when contiguous
- `` is a ballot box on the printed forms, not a `<p>` fragment
- five small-caps runs are typed as `<span>`; they become `<sc>`

## Restoring from a snapshot

`load.py` loaded the 2023 import. Now it only restores the database from
`manual.json`, and every write replaces whatever the database holds, so writes
need `--overwrite`:

```sh
python tools/load.py --check                # compare file and database, row by row
python tools/load.py --overwrite            # upsert nodes then blocks from the file
python tools/load.py --overwrite --prune    # also delete rows not in the file
python tools/load.py --overwrite --sql      # emit build/seed.sql for the SQL editor instead
```

Export first, so what you're replacing is in git. Needs `SUPABASE_SERVICE_ROLE_KEY`
in the environment or `.env` (gitignored); the anon key can't write past RLS.

## Schema changes

Migrations in `supabase/migrations/` are named by the version the database
recorded, so local and remote history match. Link once with an access token from
the work account (`SUPABASE_ACCESS_TOKEN` in `.env`), then push:

```sh
supabase link --project-ref fpnphylpwzdnzjmfkgfo
supabase migration list    # local and remote should agree
supabase db push
```

The schema was validated against a live Postgres 17 in a throwaway schema: deferred
self-FKs accept a child inserted before its parent, all eight check/unique/FK
constraints reject bad rows, upsert is a no-op on re-run, the reading-order view
reproduces document order, and a recursive walk of `section_key` answers containment.
