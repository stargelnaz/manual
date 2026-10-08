"""The gates any copy of the Manual must pass, wherever it came from.

build.py ran these on every build of the Word document. Now that text is edited in
the database, export.py runs them against the live tables. The database enforces
the ones that matter row by row (see the 20261008 migration); these are the
whole-document ones it can't, plus the row checks again as a second line.

check(nodes, blocks) takes rows in manual.json shape (node 'order', not 'doc_order')
and returns a list of failures — empty when everything passes.
"""
import collections, re

KEY_SHAPE = re.compile(r'^[a-hjkmnp-z][a-hjkmnp-z2-9]{5}$')
TAG = re.compile(r'<(/?)(em|b|sc|ref)(?: to="([^"]*)")?>')
STRAY = re.compile(r'<(?!/?(?:em|b|sc)>|ref to="[^"]*">|/ref>)')
LEVELS = {'part': {1}, 'heading': {2, 3, 4, 5}, 'paragraph': {None}, 'note': {None}}
# I-X; PART XI (the appendix) is not yet split out of Part X. Bump deliberately.
PARTS = 10


def nesting(body):
    """None if the inline tags nest properly, else what went wrong."""
    stack = []
    for m in TAG.finditer(body):
        if not m[1]:
            if m[2] == 'ref' and 'ref' in stack:
                return 'ref inside ref'
            stack.append(m[2])
        elif not stack or stack.pop() != m[2]:
            return 'misnested </%s>' % m[2]
    return 'unclosed <%s>' % stack[-1] if stack else None


def check(nodes, blocks):
    fail = []
    bykey = {d['key']: d for d in nodes}

    if len(bykey) != len(nodes):
        fail.append('duplicate node key')
    fail += ['malformed key %r' % d['key'] for d in nodes if not KEY_SHAPE.match(d['key'])]
    if len({d['order'] for d in nodes}) != len(nodes):
        fail.append('duplicate node order')
    for d in nodes:
        for col in ('parent_key', 'section_key'):
            if d[col] and d[col] not in bykey:
                fail.append('%s %s: %s %s does not exist' % (d['role'], d['key'], col, d[col]))
        if d['level'] not in LEVELS.get(d['role'], ()):
            fail.append('%s %s has level %s' % (d['role'], d['key'], d['level']))
        if d['number'] and d['sort_key'] != [int(x) for x in d['number'].split('.')]:
            fail.append('%s: sort_key %s does not match' % (d['number'], d['sort_key']))
        seen, cur = set(), d['section_key']
        while cur in bykey:
            if cur in seen:
                fail.append('section cycle at %s' % d['key'])
                break
            seen.add(cur)
            cur = bykey[cur]['section_key']

    numbered = sorted((d for d in nodes if d['number']), key=lambda d: d['order'])
    for a, b in zip(numbered, numbered[1:]):
        if not a['sort_key'] < b['sort_key']:
            fail.append('paragraph %s comes before %s' % (a['number'], b['number']))

    parts = sum(1 for d in nodes if d['role'] == 'part')
    if parts != PARTS:
        fail.append('expected %d parts, got %d' % (PARTS, parts))

    if len({b['id'] for b in blocks}) != len(blocks):
        fail.append('duplicate block id')
    slots = collections.Counter((b['node_key'], b['lang'], b['ordinal']) for b in blocks)
    fail += ['two blocks at %s/%s/%d' % s for s, n in slots.items() if n > 1]
    tables = collections.defaultdict(set)
    for b in blocks:
        where = 'block %s' % b['id']
        if b['node_key'] not in bykey:
            fail.append('%s: node %s does not exist' % (where, b['node_key']))
        if not b['body']:
            fail.append('%s: empty body' % where)
        if STRAY.search(b['body']):
            at = STRAY.search(b['body']).start()
            fail.append('%s: stray markup %r' % (where, b['body'][at:at + 12]))
        bad = nesting(b['body'])
        if bad:
            fail.append('%s: %s' % (where, bad))
        fail += ['%s: <ref> to missing node %s' % (where, m[3])
                 for m in TAG.finditer(b['body'])
                 if m[2] == 'ref' and not m[1] and m[3] not in bykey]
        if b['kind'] == 'table-row':
            tables[(b['node_key'], b['lang'])].add(b['body'].count('\t') + 1)
        if b['kind'] == 'table-note' and not b['body'].startswith(('(', '*')):
            fail.append('%s: table note does not open with "(" or "*"' % where)
    fail += ['ragged table in node %s (%s): widths %s' % (k, lang, sorted(w))
             for (k, lang), w in tables.items() if len(w) > 1]
    return fail
