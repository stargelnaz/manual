# Extraction pipeline

Turns the English Word document into `manual.json`. Run from the repo root:

```sh
python tools/extract.py     # docx  -> build/paras.json
python tools/normalize.py   #       -> build/paras_norm.json  (+ build/normreport.json)
python tools/build.py       #       -> manual.json
```

Intermediates land in `build/` and are disposable. `manual.json` and
`overrides.json` are the products; `overrides.json` is hand-maintained and must not
be regenerated.

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

- node keys unique, block ids unique, every block has a node
- every `parent_key` and `section_key` resolves; no cycles in the section chain
- paragraph numbers strictly increasing
- `nodes.order` + `blocks.ordinal` reproduces document order — the query the app runs
- the numbered set equals the tagged set plus exactly `{346.3}`
- no block body contains markup outside `<em> <b> <sc>`; all inline tags balance
- exactly 9 parts — I-VIII and X

PART IX exists in the Manual (the auxiliary constitutions, 800 series) but is not in
this export and has not been added yet. The parts gate will fail the moment it lands,
which is intended: bump it to 10 deliberately rather than letting the count drift.

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

## Stage 4 — loading

```sh
python tools/load.py --check    # what would change; writes nothing
python tools/load.py            # upsert nodes then blocks
python tools/load.py --prune    # also delete rows no longer in manual.json
python tools/load.py --sql      # emit build/seed.sql for the SQL editor instead
```

Needs a service role key — the anon key cannot write past RLS. Put
`SUPABASE_SERVICE_ROLE_KEY` in the environment or in `.env` (gitignored).

Apply the schema first:

```sh
supabase link --project-ref <ref>
supabase db push
```

The schema was validated against a live Postgres 17 in a throwaway schema: deferred
self-FKs accept a child inserted before its parent, all eight check/unique/FK
constraints reject bad rows, upsert is a no-op on re-run, the reading-order view
reproduces document order, and a recursive walk of `section_key` answers containment.
