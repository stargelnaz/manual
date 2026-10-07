# Manual

The 2023 *Manual of the Church of the Nazarene* as structured data, built to support
translation. Every paragraph, heading and note is an addressable node with a stable key,
so any translation can be aligned against the English original.

The 2023 paragraph numbers are canonical: a translation cannot renumber, reorder, insert
or drop a numbered paragraph. The schema makes that unrepresentable rather than
validating it — see `plan.md` for the full design.

## Layout

| Path | What |
|---|---|
| `tools/` | Python pipeline: Word document → `manual.json` → Supabase. See `tools/README.md` |
| `manual.json` | Built English Manual — nodes and blocks. Generated; do not hand-edit |
| `overrides.json` | Hand-maintained editorial decisions applied by the pipeline |
| `supabase/migrations/` | Database schema (`nodes`, `blocks`, `manual_reading_order` view) |
| `src/` | React app (plain JavaScript, Vite): the Manual reader and the lexicon review tool |
| `languages/` | Source documents and lexicons per language |
| `plan.md` | Design notes, source defects found, and the reasoning behind the data shape |

## Running the app

```sh
npm install
npm run dev
```

Needs `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in `.env` (gitignored).

## Rebuilding the data

```sh
python tools/extract.py
python tools/normalize.py
python tools/build.py      # -> manual.json, runs all gates
python tools/load.py       # -> Supabase (needs SUPABASE_SERVICE_ROLE_KEY)
```
