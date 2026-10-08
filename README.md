# Manual

The 2023 *Manual of the Church of the Nazarene* as structured data, built to support
translation. Every paragraph, heading and note is an addressable node with a stable key,
so any translation can be aligned against the English original.

The 2023 paragraph numbers are canonical: a translation cannot renumber, reorder, insert
or drop a numbered paragraph. The schema makes that unrepresentable rather than
validating it — see `plan.md` for the full design.

**The Supabase database is the canonical text.** The 2023 English Manual was
imported from Word on 2026-10-08; since then it is edited in the database, which
records every change in `revisions` and enforces the markup, numbering and link
rules itself. `manual.json` is a snapshot exported from it for git.

## Layout

| Path | What |
|---|---|
| `tools/` | Export and check the database; the original Word → database import. See `tools/README.md` |
| `manual.json` | Snapshot of the database — nodes and English blocks. Written by `tools/export.py`; do not hand-edit |
| `overrides.json` | Editorial decisions the 2023 import applied. Historical |
| `node_keys.json` | Node keys (`k7xq2m`) issued by the 2023 import, by locator. Frozen; the database mints new ones |
| `supabase/migrations/` | Database schema (`nodes`, `blocks`, `revisions`, `manual_reading_order` view) |
| `src/` | React app (plain JavaScript, Vite): the Manual reader and the lexicon review tool |
| `languages/` | Source documents and lexicons per language |
| `plan.md` | Design notes, source defects found, and the reasoning behind the data shape |

## Running the app

```sh
npm install
npm run dev
```

Needs `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in `.env` (gitignored).

## Snapshots

After editing, export and commit:

```sh
python tools/export.py          # database -> manual.json, runs all gates
python tools/export.py --check  # gates only, writes nothing
```

`tools/load.py --overwrite` restores the database from `manual.json`, replacing
whatever is there. It is for disaster recovery only.
