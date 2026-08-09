"""Do rStyle=italic/bold spans in the docx actually mean 'emphasis'?

624 italic refs vs 175 typed <em> opens could mean the style covers more than
emphasis. Merge adjacent same-style runs into logical spans, strip the typed tag
literals the transcriber left inside them, and see what the count resolves to.
"""
import re, sys, html, collections
sys.stdout.reconfigure(encoding='utf-8')

s = open('dx2/word/document.xml', encoding='utf8').read()
T = re.compile(r'<w:t(?: [^>]*)?>(.*?)</w:t>', re.S)
R = re.compile(r'<w:r[ >](?:(?!</w:r>).)*?</w:r>', re.S)
paras = re.findall(r'<w:p[ >].*?</w:p>', s, re.S)

# Typed tag literals the transcriber left sitting inside the formatted runs.
TAGLIT = re.compile(r'</?(?:em|b|p|div|li|ol|ParaNum|PaaNum|SubPoint|DIV)\b[^>]*>|'
                    r'className=.[^\']*.', re.I)

spans = {'italic': [], 'bold': []}
for pi, p in enumerate(paras):
    cur, curstyle = [], None
    for r in R.findall(p):
        t = html.unescape(''.join(T.findall(r)))
        m = re.search(r'<w:rStyle w:val="(italic|bold)"', r)
        st = m.group(1) if m else None
        if st == curstyle:
            cur.append(t)
        else:
            if curstyle and cur:
                spans[curstyle].append((pi + 1, ''.join(cur)))
            cur, curstyle = [t], st
    if curstyle and cur:
        spans[curstyle].append((pi + 1, ''.join(cur)))

for st in ('italic', 'bold'):
    raw = spans[st]
    clean = []
    for pi, txt in raw:
        t = TAGLIT.sub('', txt).strip()
        if t:
            clean.append((pi, t))
    typed = {'italic': 175, 'bold': 303}[st]
    print('=== %s' % st)
    print('  run refs in file      :', s.count('<w:rStyle w:val="%s"' % st))
    print('  merged logical spans  :', len(raw))
    print('  non-empty after strip :', len(clean), '   (typed <%s> opens: %d)'
          % ('em' if st == 'italic' else 'b', typed))
    bare_num = [t for _, t in clean if re.fullmatch(r'\d+(\.\d+)*\.?', t)]
    print('  spans that are only a paragraph number :', len(bare_num))
    print('  sample:')
    for pi, t in clean[:14]:
        print('     p%-5d %s' % (pi, repr(t[:64])))
    freq = collections.Counter(t for _, t in clean)
    print('  most repeated:', freq.most_common(6))
    print()
