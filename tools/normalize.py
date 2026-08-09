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

sys.stdout.reconfigure(encoding='utf-8')

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = json.load(open(ROOT / 'build/paras.json', encoding='utf8'))
OV = json.load(open(ROOT / 'overrides.json', encoding='utf8'))

SPAN = re.compile(r'<(em|b)>(.*?)</\1>')
GAP = re.compile(r'</(em|b)>(\s*)<\1>')
LEADIN = re.compile(r'^[\s<>/]*(?:\d+(?:\.\d+)*\.)?[\s<>/]*$')
TRAIL = re.compile(r'([.,;:!?]+)$')

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
    out.append({'n': p['n'], 'typed': p['typed'], 'formatted': ''.join(res)})

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
c = collections.Counter(m.group(2) for q in out for m in SPAN.finditer(q['formatted'])
                        if m.group(2).startswith('Manual'))
print('Manual title forms      :', dict(c))
