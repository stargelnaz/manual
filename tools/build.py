"""Stage 3 — nodes and blocks, written to manual.json.

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
"""
import json, re, sys, hashlib, collections, pathlib

sys.stdout.reconfigure(encoding='utf-8')

ROOT = pathlib.Path(__file__).resolve().parent.parent
TYPED = {p['n']: p['typed'] for p in json.load(open(ROOT / 'build/paras.json', encoding='utf8'))}
NORM = json.load(open(ROOT / 'build/paras_norm.json', encoding='utf8'))
LANG = 'en'

# Symbol-font private-use codepoints: "<p>" typed with Symbol active, plus the
# ballot box used on the printed forms.
PUA = {'': '<', '': 'p', '': '>', '': '☐'}
# Case-insensitive: one block is typed <DIV CLASSNAME='PART-NUMBER'> (PART III),
# and a case-sensitive match silently demoted it to body text.
CLASS = re.compile(r'class\s*name\s*=\s*[\'"‘’“”]\s*([a-zA-Z0-9-]+)', re.I)
LEADNUM = re.compile(r'^\s*(\d+(?:\.\d+)*)\.\s+')
SUBPOINT = re.compile(r'^\s*(\((?:\d+|[a-z]|[ivx]+)\))\s+')
LISTMARK = re.compile(r'^\s*(\d+\.|[a-z]\.|\([a-z0-9]+\))\s+')
TAGNUM = re.compile(r'<(?:Para|Paa)Num>\s*(\d[\d.]*?)\.?\s*</ParaNum>')
VERSE = re.compile(r'\b(?:[123]\s)?[A-Z][a-z]+\s+\d+:\d+')
INLINE = ('em', 'b', 'sc')

# "PART II" and its title are one heading; the chapter list is that part's contents.
PART_OPEN = 'part-number'
PART_BODY = {'part-title', 'part-chapter-list'}
LEVEL = {'part-number': 1, 'heading-1': 2, 'subheading': 3}
HEADINGS = set(LEVEL) | PART_BODY
PROSE = {'lead', 'continuation', 'subpoint', 'list-item', 'note', 'bible-reference'}


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
        lv = LEVEL[kind]
        for deeper in [k for k in stack if k >= lv]:
            del stack[deeper]
        stack[lv] = add_node(genkey('heading'), 'heading', None, False,
                             None, section_of(lv), lv)

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
        else:
            kind = 'continuation'

    if open_key is None:
        add_node(genkey('heading'), 'heading', None, False, None, None, 2)

    ordinal = per_node[open_key]
    per_node[open_key] += 1
    blocks.append({
        'id': hashlib.sha1(('%s|%s|%d' % (LANG, open_key, ordinal)).encode()).hexdigest()[:8],
        'node_key': open_key, 'lang': LANG, 'ordinal': ordinal, 'kind': kind,
        'marker': marker, 'body': body, 'source_line': n, 'is_lead': is_lead,
    })
    prev_kind = kind

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

# The numbered set is the tagged set plus 346.3, which carries no <ParaNum> wrapper.
_tagged = {m.group(1) for t in TYPED.values() for m in TAGNUM.finditer(t)}
assert {d['number'] for d in numbered} - _tagged == {'346.3'}, 'unexpected numbered node'
assert not _tagged - {d['number'] for d in numbered}, 'tagged paragraph number missing'

for b in blocks:
    assert not re.search(r'<(?!/?(?:em|b|sc)>)', b['body']), \
        'stray markup in %s: %r' % (b['id'], b['body'][:80])
    for t in INLINE:
        assert len(re.findall(r'<' + t + r'[ >]', b['body'])) == \
               len(re.findall(r'</' + t + r'>', b['body'])), 'unbalanced %s in %s' % (t, b['id'])

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
          open(ROOT / 'manual.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)

print('nodes  :', len(nodes), '  numbered:', len(numbered),
      '  generated:', len(nodes) - len(numbered))
print('roles  :', collections.Counter(d['role'] for d in nodes).most_common())
print('kinds  :', collections.Counter(b['kind'] for b in blocks).most_common())
print('blocks :', len(blocks), 'of', len(NORM), 'w:p')
print('numbers:', numbered[0]['number'], '->', numbered[-1]['number'])
print('nodes with a section:', sum(1 for d in nodes if d['section_key']),
      ' roots:', sum(1 for d in nodes if not d['section_key']))
print('all gates passed')
