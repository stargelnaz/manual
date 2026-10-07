"""Stage 2 — punctuation in or out of emphasis, plus the hand decisions.

The "belongs-to" test:
  - A span that LABELS the block owns its terminal punctuation, which stays inside:
    **Business.**   *Response:*
  - A span inside a sentence is a title or term; punctuation after it belongs to the
    sentence and moves outside:  *Manual of the Church of the Nazarene*.

A span is a label when nothing precedes it in the block except whitespace, the
paragraph number, and stray markup debris (one paragraph opens "<532.13.").

Without this the Manual title is stored as six different strings differing only in
what punctuation followed it, which breaks both citation search and the span-level
alignment the translation app depends on.
"""
import json, re, sys, collections, pathlib

from refs import PARA_CITATION, PARA_RANGE

sys.stdout.reconfigure(encoding='utf-8')

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = json.load(open(ROOT / 'build/paras.json', encoding='utf8'))
OV = json.load(open(ROOT / 'overrides.json', encoding='utf8'))

SPAN = re.compile(r'<(em|b)>(.*?)</\1>')
GAP = re.compile(r'</(em|b)>(\s*)<\1>')
LEADIN = re.compile(r'^[\s<>/]*(?:\d+(?:\.\d+)*\.)?[\s<>/]*$')
TRAIL = re.compile(r'([.,;:!?]+)$')

# Dashes in Bible references. Running text keeps the plain hyphen; inside a
# citation a range within one chapter takes an en dash (Romans 1:18–25; 5:12–14)
# and a range across chapters takes an em dash (7:1—8:9, Genesis 1—3).
# Only explicit book names open a citation, so "In 1894-1895" is left alone.
BOOKS = '|'.join(sorted('''Genesis Exodus Leviticus Numbers Deuteronomy Joshua Judges
    Ruth Samuel Kings Chronicles Ezra Nehemiah Esther Job Psalms? Proverbs
    Ecclesiastes Isaiah Jeremiah Lamentations Ezekiel Daniel Hosea Joel Amos
    Obadiah Jonah Micah Nahum Habakkuk Zephaniah Haggai Zechariah Malachi Matthew
    Mark Luke John Acts Romans Corinthians Galatians Ephesians Philippians
    Colossians Thessalonians Timothy Titus Philemon Hebrews James Peter Jude
    Revelation'''.split(), key=len, reverse=True))
BOOK = r'(?:[1-3] )?(?:Song of (?:Solomon|Songs)|%s)\b' % BOOKS
ONE_CHAPTER = re.compile(r'(?:Obadiah|Philemon|Jude|[23] John)$')
VERSE = r'\d+(?::\d+)?(?:[ab](?![a-z]))?'    # "20a", "3:6b": part of a verse
REF = r'%s(?:\s*[-–—]\s*%s)?' % (VERSE, VERSE)
CITATION = re.compile(r'%s\s+%s(?:\s*[,;]\s*(?:%s\s+)?%s)*' % (BOOK, REF, BOOK, REF))
CITE_TOKEN = re.compile(r'(?P<book>%s)|(?P<ref>%s)|(?P<semi>;)' % (BOOK, REF))
RANGE = re.compile(r'(%s)\s*[-–—]\s*(%s)' % (VERSE, VERSE))


def citation_dashes(cite):
    """Re-dash one citation. A bare number is a verse once a chapter:verse has been
    seen in the same chapter run (after a comma) or in a one-chapter book, and a
    chapter otherwise (after a semicolon or straight after the book name)."""
    out, pos, verses, one = [], 0, False, False
    for t in CITE_TOKEN.finditer(cite):
        if t.group('book'):
            one = bool(ONE_CHAPTER.match(t.group('book')))
            verses = one
        elif t.group('semi'):
            verses = one
        else:
            ref = t.group('ref')
            r = RANGE.fullmatch(ref)
            if r:
                a, b = r.groups()
                cross = (':' in b) or (':' not in a and not verses)
                ref = '%s%s%s' % (a, '—' if cross else '–', b)
            out.append(cite[pos:t.start()])
            out.append(ref)
            pos = t.end()
            if ':' in t.group('ref'):
                verses = True
    out.append(cite[pos:])
    return ''.join(out)


# Dashes in paragraph cross-references, by the same rule: a range inside one
# paragraph takes an en dash (300.2–300.3, 113–113.1) and a range across paragraphs
# takes an em dash (100—109, 103—104.3, 139.19—140). What counts as a reference is
# in refs.py, shared with the build, which links them.


def para_dash(r):
    a, b = r.groups()
    within = '.' in b and a.split('.')[0] == b.split('.')[0]
    return '%s%s%s' % (a, '–' if within else '—', b)

DROP = {(o['source_line'], o['tag'], o['span_text'])
        for o in OV['emphasis'] if o['action'] == 'drop-emphasis'}
DROP_ALL = {(o['source_line'], o['tag'])
            for o in OV['emphasis'] if o['action'] == 'drop-all-emphasis'}

report, out, dropped = [], [], []
for p in P:
    body = p['formatted']

    # Spans separated only by whitespace are one run the source split. Merge first,
    # or both the label test and the title consolidation misfire.
    merged = 0
    while GAP.search(body):
        body = GAP.sub(lambda m: m.group(2), body, count=1)
        merged += 1
    if merged:
        report.append({'n': p['n'], 'role': 'merge', 'count': merged})

    res, pos = [], 0
    for m in SPAN.finditer(body):
        res.append(body[pos:m.start()])
        pos = m.end()
        tag, txt = m.group(1), m.group(2)

        if (p['n'], tag, txt) in DROP or (p['n'], tag) in DROP_ALL:
            res.append(txt)
            dropped.append({'n': p['n'], 'tag': tag, 'was': txt})
            continue

        is_label = bool(LEADIN.match(SPAN.sub('', body[:m.start()])))
        t = TRAIL.search(txt)
        if t and not is_label and txt[:t.start()].strip():
            kept, moved = txt[:t.start()], t.group(1)
            res.append('<%s>%s</%s>%s' % (tag, kept, tag, moved))
            report.append({'n': p['n'], 'role': 'moved-out', 'tag': tag,
                           'was': txt, 'now': kept, 'moved': moved})
        else:
            res.append(m.group(0))
            if t:
                report.append({'n': p['n'], 'role': 'kept-inside', 'tag': tag,
                               'was': txt, 'now': txt, 'moved': ''})
    res.append(body[pos:])
    body = ''.join(res)

    redashed = CITATION.sub(lambda m: citation_dashes(m.group(0)), body)
    redashed = PARA_CITATION.sub(lambda m: PARA_RANGE.sub(para_dash, m.group(0)), redashed)
    if redashed != body:
        report.append({'n': p['n'], 'role': 'dashes',
                       'count': sum(a != b for a, b in zip(body, redashed))})
    out.append({'n': p['n'], 'typed': p['typed'], 'formatted': redashed})

json.dump(out, open(ROOT / 'build/paras_norm.json', 'w', encoding='utf8'), ensure_ascii=False)
json.dump(report, open(ROOT / 'build/normreport.json', 'w', encoding='utf8'),
          ensure_ascii=False, indent=1)

moved = [r for r in report if r['role'] == 'moved-out']
kept = [r for r in report if r['role'] == 'kept-inside']
assert not [r for r in moved if TRAIL.search(r['now'])], 'inline span still has punctuation'

print('split spans merged      :', sum(r['count'] for r in report if r['role'] == 'merge'))
print('emphasis dropped        :', len(dropped), 'per overrides.json')
print('punctuation moved out   :', len(moved))
print('punctuation kept inside :', len(kept))
print('reference dashes set    :', sum(r['count'] for r in report if r['role'] == 'dashes'))
c = collections.Counter(m.group(2) for q in out for m in SPAN.finditer(q['formatted'])
                        if m.group(2).startswith('Manual'))
print('Manual title forms      :', dict(c))
