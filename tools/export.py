"""Snapshot the canonical Manual out of Supabase into manual.json, and check it.

    python tools/export.py            write manual.json from the database
    python tools/export.py --check    run the gates against the database, write nothing

The database is the Manual now; manual.json is its snapshot. Commit the file after
editing so git keeps a readable, diffable history alongside the revisions table,
and so there is a copy to restore from (tools/load.py --overwrite) — the free plan
keeps no backups you can download.

Reads only, through the public read policy, so the anon key in .env is enough.
The file is written in exactly the shape build.py wrote, so the first export after
the switch differs from the last build by its "source" line alone.
"""
import json, sys, argparse
import gates, load

SOURCE = 'supabase'


def fetch(api, lang):
    rows = api.rows('nodes', ','.join(load.NODE_COLS))
    nodes = [{'key': r['key'], 'role': r['role'], 'number': r['number'],
              'number_visible': r['number_visible'], 'sort_key': r['sort_key'],
              'parent_key': r['parent_key'], 'section_key': r['section_key'],
              'level': r['level'], 'order': r['doc_order']}
             for r in sorted(rows, key=lambda r: r['doc_order'])]
    order = {d['key']: d['order'] for d in nodes}
    rows = [r for r in api.rows('blocks', ','.join(load.BLOCK_COLS)) if r['lang'] == lang]
    blocks = [{c: r[c] for c in load.BLOCK_COLS}
              for r in sorted(rows, key=lambda r: (order.get(r['node_key'], -1), r['ordinal']))]
    return nodes, blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='run the gates, write nothing')
    ap.add_argument('--lang', default='en')
    a = ap.parse_args()

    url = load.env('SUPABASE_URL') or load.env('VITE_SUPABASE_URL')
    key = load.env('SUPABASE_SERVICE_ROLE_KEY') or load.env('VITE_SUPABASE_ANON_KEY')
    if not url or not key:
        sys.exit('Need VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in .env.')
    nodes, blocks = fetch(load.Api(url, key), a.lang)
    print('database: %d nodes, %d %s blocks' % (len(nodes), len(blocks), a.lang))

    failures = gates.check(nodes, blocks)
    for f in failures[:40]:
        print('  FAIL', f)
    if len(failures) > 40:
        print('  ... and %d more' % (len(failures) - 40))

    if not a.check:
        # A snapshot of what is there is worth having even when a gate fails —
        # write it, but exit non-zero so the failure is not missed.
        path = load.ROOT / ('manual.json' if a.lang == 'en' else 'manual.%s.json' % a.lang)
        with open(path, 'w', encoding='utf8') as f:
            json.dump({'lang': a.lang, 'source': SOURCE, 'nodes': nodes, 'blocks': blocks},
                      f, ensure_ascii=False, indent=1)
        print('wrote', path.name)

    if failures:
        sys.exit('%d gate failure(s)' % len(failures))
    print('all gates passed')


if __name__ == '__main__':
    main()
