"""Stage 3 — nodes and blocks, written to build/manual.json.

Historical. The database became the canonical Manual on 2026-10-08; this is how
the 2023 Word document was turned into it, kept so the derivation stays
reproducible. It writes to build/, not manual.json — that file is now the
database's snapshot (tools/export.py) and a rebuild must not overwrite it. And it
no longer mints: the database does, and a key minted here could collide with one
minted there.

Text and emphasis come from build/paras_norm.json (rebuilt from Word character
styles, punctuation normalized, overrides applied). Block semantics — note vs
subheading vs subpoint — come from the hand-typed className, which the character
styles do not encode. Hence the hybrid.

One w:p = one block. Every block belongs to exactly one node, so headings, the
Foreword and standalone notes get a node with a hidden generated key.

Two hierarchies, deliberately separate:
  parent_key   numeric:    10.1 -> 10
  section_key  structural: 10 -> "X. Christian Holiness" -> "ARTICLES OF FAITH"
                              -> "PART II Church Constitution"
Walk section_key transitively to answer "everything under PART III".

Node keys are opaque six-character codes (k7xq2m), not paragraph numbers.
Numbers are display and change between editions; a key is identity and never
does. The build works in *locators* — the 2023 number, or a generated anchor like
10.1~h1 — and node_keys.json maps each locator to its key. That file is frozen:
a locator it does not know is a build error, so a lost or truncated registry
cannot silently re-key the Manual.
"""
import json, re, sys, hashlib, collections, pathlib

from refs import PARA_CITATION, PARA_ITEM, PARA_FIRST

sys.stdout.reconfigure(encoding='utf-8')

ROOT = pathlib.Path(__file__).resolve().parent.parent
TYPED = {p['n']: p['typed'] for p in json.load(open(ROOT / 'build/paras.json', encoding='utf8'))}
NORM = json.load(open(ROOT / 'build/paras_norm.json', encoding='utf8'))
OV = json.load(open(ROOT / 'overrides.json', encoding='utf8'))
LANG = 'en'
REGISTRY = ROOT / 'node_keys.json'
MINT = '--mint' in sys.argv

# No 0/1/i/l/o, so a key can be read aloud or retyped without ambiguity, and a
# leading letter, so a key can never look like a paragraph number.
KEY_LETTERS = 'abcdefghjkmnpqrstuvwxyz'
KEY_CHARS = KEY_LETTERS + '23456789'
KEY_SHAPE = re.compile(r'^[%s][%s]{5}$' % (KEY_LETTERS, KEY_CHARS))

# Symbol-font private-use codepoints: "<p>" typed with Symbol active, plus the
# ballot box used on the printed forms.
PUA = {'': '<', '': 'p', '': '>', '': '☐'}
# Case-insensitive: one block is typed <DIV CLASSNAME='PART-NUMBER'> (PART III),
# and a case-sensitive match silently demoted it to body text.
CLASS = re.compile(r'class\s*name\s*=\s*[\'"‘’“”]\s*([a-zA-Z0-9-]+)', re.I)
LEADNUM = re.compile(r'^\s*(\d+(?:\.\d+)*)\.\s+')
SUBPOINT = re.compile(r'^\s*(\((?:\d+|[a-z]|[ivx]+)\))\s+')
LISTMARK = re.compile(r'^\s*(\d+\.|[ivx]+\.|[a-z]\.|\([a-z0-9]+\))\s+')
TAGNUM = re.compile(r'<(?:Para|Paa)Num>\s*(\d[\d.]*?)\.?\s*</ParaNum>')
VERSE = re.compile(r'\b(?:[123]\s)?[A-Z][a-z]+\s+\d+:\d+')
INLINE = ('em', 'b', 'sc')

# "PART II" and its title are one heading; the chapter list is that part's contents.
PART_OPEN = 'part-number'
PART_BODY = {'part-title', 'part-chapter-list'}
LEVEL = {'part-number': 1, 'heading-1': 2, 'subheading': 3}
HEADINGS = set(LEVEL) | PART_BODY
PROSE = {'lead', 'continuation', 'subpoint', 'list-item', 'note', 'bible-reference',
         'table-row', 'table-note'}

# Tables, by the paragraph they sit in. Word sets each row as one w:p with its
# cells separated by tabs; a table-row block keeps them, one "\t" between cells.
# Listed rather than detected, because tabs also follow list markers and fill the
# blanks on the forms. 601.2 is a table too, but its second column was wrapped by
# hand with more tabs, so it stays prose until it is cleaned up.
TABLES = {'201.1', '201.2', '205.15', '301.1'}
NUMRANGE = re.compile(r'^(\d[\d,]*)-(\d[\d,]*)$')         # 0-6,000 -> 0–6,000


def is_scripture(body):
    hits = VERSE.findall(body)
    return len(hits) >= 2 or (len(hits) == 1 and len(body) < 120)


def classify(typed):
    m = CLASS.search(typed[:140])
    if m:
        return m.group(1).lower()
    if re.match(r'^\s*<(?:li|ol)\b', typed, re.I):
        return 'list-item'
    return 'paragraph'


def clean(body):
    for k, v in PUA.items():
        body = body.replace(k, v)
    body = re.sub(r'<span[^>]*small-caps[^>]*>(.*?)</span>', r'<sc>\1</sc>',
                  body, flags=re.I | re.S)
    body = re.sub(r'</?(?:p|div|li|ol|span)\b[^>]*>', '', body, flags=re.I)
    # Remaining angle brackets are debris — a stray "<" before a paragraph number,
    # or the tail of a broken <p>. Protect the real tags, drop the rest.
    for i, t in enumerate(INLINE):
        body = body.replace('<%s>' % t, '\x00%d' % i).replace('</%s>' % t, '\x01%d' % i)
    body = body.replace('<', '').replace('>', '')
    for i, t in enumerate(INLINE):
        body = body.replace('\x00%d' % i, '<%s>' % t).replace('\x01%d' % i, '</%s>' % t)
    return re.sub(r'[ \t]+', ' ', body).strip()


nodes, blocks = [], []
order = 0
open_key = last_number = prev_kind = None
stack = {}                      # level -> node key of the innermost open heading
autoseq = collections.Counter()
per_node = collections.Counter()


def section_of(level=4):
    """Innermost open heading shallower than `level`."""
    for lv in sorted(stack, reverse=True):
        if lv < level:
            return stack[lv]
    return None


def add_node(key, role, number, visible, parent, section, level=None):
    global order, open_key
    order += 1000
    nodes.append({'key': key, 'role': role, 'number': number,
                  'number_visible': visible,
                  'sort_key': [int(x) for x in number.split('.')] if number else None,
                  'parent_key': parent, 'section_key': section, 'level': level,
                  'order': order})
    open_key = key
    return key


def genkey(role):
    anchor = last_number or 'front'
    autoseq[(anchor, role)] += 1
    return '%s~%s%d' % (anchor, role[0], autoseq[(anchor, role)])


for p in NORM:
    n = p['n']
    typed, kind = TYPED[n], classify(TYPED[n])
    body = clean(p['formatted'])
    if not body:
        # An empty heading still separates what follows from what came before, so a
        # note after it must stand alone rather than attaching to the last paragraph.
        if kind in HEADINGS:
            prev_kind = None
        continue

    marker, is_lead = None, False

    # Prefer the number the typed markup declares. 22 paragraphs carry a stray "<"
    # before the number (<530.10.) and 220.3 has no period after it, so re-parsing
    # the body text misses them. Fall back to a bare leading number only when it
    # continues the sequence — otherwise every numbered list item in the forms and
    # rituals mints a duplicate node for 1-8.
    number = None
    tag_num = TAGNUM.search(typed)
    if tag_num:
        number = tag_num.group(1)
        body = re.sub(r'^\s*<?\s*' + re.escape(number) + r'\.?\s*', '', body, count=1)
    else:
        m = LEADNUM.match(body)
        if m:
            nxt = [int(x) for x in m.group(1).split('.')]
            cur = [int(x) for x in last_number.split('.')] if last_number else []
            if nxt > cur:
                number, body = m.group(1), body[m.end():]

    if kind not in HEADINGS and kind != 'note' and number:
        parent = number.rsplit('.', 1)[0] if '.' in number else None
        add_node(number, 'paragraph', number, True, parent, section_of())
        last_number = number
        kind, is_lead = 'lead', True
        number = None

    elif kind == PART_OPEN:
        stack.clear()
        stack[1] = add_node(genkey('part'), 'part', None, False, None, None, 1)

    elif kind in PART_BODY:
        # The title and chapter list belong to the part only when they directly
        # follow it. They do not always: a chapter list reappears mid-document
        # (w:p 209, 1741), and folding those into a part node created hundreds of
        # paragraphs earlier breaks document order.
        if 1 in stack and open_key == stack[1]:
            pass                                    # contiguous — keep collecting
        else:
            add_node(genkey('heading'), 'heading', None, False,
                     None, stack.get(1), 2)

    elif kind in LEVEL:
        # The rituals (700-709) are numbered subheadings: the number is the heading's,
        # shown on it and citable. last_number stays put, so the generated locators
        # after it, and with them the registry keys, do not move.
        lv = LEVEL[kind]
        for deeper in [k for k in stack if k >= lv]:
            del stack[deeper]
        stack[lv] = add_node(genkey('heading'), 'heading', number, bool(number),
                             None, section_of(lv), lv)
        number = None

    elif kind == 'note':
        # A note after prose or another note cites it. A note after a heading, or
        # with nothing open, stands on its own in the flow.
        if not (prev_kind in PROSE and open_key):
            add_node(genkey('note'), 'note', None, False, None, section_of())
        kind = 'bible-reference' if is_scripture(body) else 'note'

    else:
        sp = SUBPOINT.match(body)
        if sp:
            marker, body, kind = sp.group(1), body[sp.end():], 'subpoint'
        elif kind == 'list-item':
            lm = LISTMARK.match(body)
            if lm:
                marker, body = lm.group(1), body[lm.end():]
        elif last_number in TABLES and '\t' in p['formatted']:
            # A leading tab only moves the first cell to its tab stop; it is not a cell.
            cells = [clean(c) for c in p['formatted'].split('\t')]
            if not cells[0]:
                cells = cells[1:]
            body, kind = '\t'.join(NUMRANGE.sub('\\1–\\2', c) for c in cells), 'table-row'
        elif prev_kind == 'table-row':
            kind = 'table-note'
        else:
            kind = 'continuation'

    # A number taken off the body must have landed on a node. Before this check
    # the 700-709 subheadings lost theirs without a trace.
    assert number is None, 'number %s stripped from w:p %d (%s) but not stored' % (number, n, kind)

    if open_key is None:
        add_node(genkey('heading'), 'heading', None, False, None, None, 2)

    ordinal = per_node[open_key]
    per_node[open_key] += 1
    blocks.append({
        'node_key': open_key, 'lang': LANG, 'ordinal': ordinal, 'kind': kind,
        'marker': marker, 'body': body, 'source_line': n, 'is_lead': is_lead,
    })
    prev_kind = kind

# ---------------------------------------------------------------- keys
# Everything above speaks locators. Swap them for registry keys here, then
# derive block ids from the keys so ids follow identity, not numbering.
registry = (json.load(open(REGISTRY, encoding='utf8'))['keys']
            if REGISTRY.exists() else {})
missing = [d['key'] for d in nodes if d['key'] not in registry]
if MINT:
    sys.exit('--mint is retired: the database mints node keys now (mint_node_key()).')
if missing:
    sys.exit('%d node(s) have no key in node_keys.json, e.g. %s. The registry is frozen;\n'
             'new content is added in the database, not through this build.'
             % (len(missing), missing[:5]))

assert len(set(registry.values())) == len(registry), 'duplicate key in registry'
assert all(KEY_SHAPE.match(k) for k in registry.values()), 'malformed key in registry'

for d in nodes:
    d['key'] = registry[d['key']]
    d['parent_key'] = registry[d['parent_key']] if d['parent_key'] else None
    d['section_key'] = registry[d['section_key']] if d['section_key'] else None
for i, b in enumerate(blocks):
    key = registry[b['node_key']]
    bid = hashlib.sha1(('%s|%s|%d' % (LANG, key, b['ordinal'])).encode()).hexdigest()[:8]
    blocks[i] = {'id': bid, **b, 'node_key': key}

# ---------------------------------------------------------------- references
# Each item of a cross-reference links to the node its first number names:
# "(300.1–300.3, 301)" -> <ref to="key of 300.1">300.1–300.3</ref>, <ref to="key of 301">301</ref>.
# The tag carries the key, not the number, so a link survives renumbering. An item
# that names no node in this export must be listed in overrides.json "references"
# (years, the 800s and 900s), and every listed item must still be one.
bynum = {d['number']: d['key'] for d in nodes if d['number']}
UNLINKED = {(r['source_line'], r['text']) for o in OV['references'] for r in o['items']}
unlinked = set()


def link(cite, line):
    def item(m):
        key = bynum.get(PARA_FIRST.match(m.group(0)).group(0))
        if key:
            return '<ref to="%s">%s</ref>' % (key, m.group(0))
        unlinked.add((line, m.group(0)))
        return m.group(0)
    return PARA_ITEM.sub(item, cite)


for b in blocks:
    b['body'] = PARA_CITATION.sub(lambda m: link(m.group(0), b['source_line']), b['body'])

# ---------------------------------------------------------------- gates
bykey = {d['key']: d for d in nodes}
numbered = [d for d in nodes if d['number']]

assert len(bykey) == len(nodes), 'duplicate node key'
assert len({b['id'] for b in blocks}) == len(blocks), 'duplicate block id'
assert all(b['node_key'] in bykey for b in blocks), 'block with no node'
assert all(d['parent_key'] in bykey for d in nodes if d['parent_key']), 'missing parent'
assert all(d['section_key'] in bykey for d in nodes if d['section_key']), 'missing section'
sk = [d['sort_key'] for d in numbered]
assert sk == sorted(sk), 'paragraph numbers not strictly increasing'

# Stored keys must reconstruct document order — that is the query the app runs.
_rec = sorted(blocks, key=lambda b: (bykey[b['node_key']]['order'], b['ordinal']))
assert [b['source_line'] for b in _rec] == sorted(b['source_line'] for b in _rec), \
    'nodes.order + blocks.ordinal does not reproduce document order'

# The numbered paragraphs are the tagged set plus 346.3, which carries no <ParaNum>
# wrapper. The only numbered headings are the ten rituals.
_tagged = {m.group(1) for t in TYPED.values() for m in TAGNUM.finditer(t)}
assert {d['number'] for d in numbered if d['role'] == 'paragraph'} - _tagged == {'346.3'}, \
    'unexpected numbered paragraph'
assert {d['number'] for d in numbered if d['role'] != 'paragraph'} == \
       {str(n) for n in range(700, 710)}, 'unexpected numbered heading'
assert not _tagged - {d['number'] for d in numbered}, 'tagged paragraph number missing'

REF_OPEN = re.compile(r'<ref to="([^"]*)">')
for b in blocks:
    assert not re.search(r'<(?!/?(?:em|b|sc)>|ref to="[^"]*">|/ref>)', b['body']), \
        'stray markup in %s: %r' % (b['id'], b['body'][:80])
    for t in INLINE + ('ref',):
        assert len(re.findall(r'<' + t + r'[ >]', b['body'])) == \
               len(re.findall(r'</' + t + r'>', b['body'])), 'unbalanced %s in %s' % (t, b['id'])
    assert all(k in bykey for k in REF_OPEN.findall(b['body'])), 'dangling ref in %s' % b['id']

assert not unlinked - UNLINKED, 'unresolved references, list them in overrides.json:\n%s' % \
    '\n'.join('  w:p %d  %s' % u for u in sorted(unlinked - UNLINKED))
assert not UNLINKED - unlinked, 'stale reference overrides (now linked, or text changed):\n%s' % \
    '\n'.join('  w:p %d  %s' % u for u in sorted(UNLINKED - unlinked))

# Every listed table is found, every row has as many cells as its header row, and
# the line after a table is its "(For every ...)" note.
_tables = collections.defaultdict(list)
for b in blocks:
    if b['kind'] == 'table-row':
        _tables[bykey[b['node_key']]['number']].append(b['body'].count('\t') + 1)
    if b['kind'] == 'table-note':
        assert b['body'].startswith('('), 'table note in %s: %r' % (b['id'], b['body'][:60])
assert set(_tables) == TABLES, 'tables found: %s' % sorted(_tables)
for num, widths in _tables.items():
    assert len(widths) > 1 and len(set(widths)) == 1, 'ragged table in %s: %s' % (num, widths)

# No section cycles, and every chain terminates at a part or the document root.
# PART IX (auxiliary constitutions) exists in the Manual but is not in this
# export and has not been added yet. Bump to 10 deliberately when it lands.
_parts = [d for d in nodes if d['role'] == 'part']
assert len(_parts) == 9, 'expected 9 parts, got %d' % len(_parts)

for d in nodes:
    seen, cur = set(), d['section_key']
    while cur:
        assert cur not in seen, 'section cycle at %s' % d['key']
        seen.add(cur)
        cur = bykey[cur]['section_key']

json.dump({'lang': LANG,
           'source': 'languages/english/data-app-Foreword-through-900s-no-auxilliaries.docx',
           'nodes': nodes, 'blocks': blocks},
          open(ROOT / 'build/manual.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)

print('nodes  :', len(nodes), '  numbered:', len(numbered),
      '  generated:', len(nodes) - len(numbered))
print('roles  :', collections.Counter(d['role'] for d in nodes).most_common())
print('kinds  :', collections.Counter(b['kind'] for b in blocks).most_common())
print('blocks :', len(blocks), 'of', len(NORM), 'w:p')
print('numbers:', numbered[0]['number'], '->', numbered[-1]['number'])
print('nodes with a section:', sum(1 for d in nodes if d['section_key']),
      ' roots:', sum(1 for d in nodes if not d['section_key']))
print('refs   :', sum(len(REF_OPEN.findall(b['body'])) for b in blocks), 'linked  ',
      len(unlinked), 'unlinked by override')
print('keys   :', len(nodes), 'from', REGISTRY.name,
      '  unused registry entries:', len(registry) - len(nodes))
print('all gates passed')
