"""Stage 1 — read the docx, emit each w:p twice.

`typed`     the hand-typed pseudo-HTML, which carries the block semantics (className)
`formatted` the same paragraph rebuilt from Word's character styles, which carry the
            real emphasis

The typed <em>/<b> tags are a lossy hand transcription of formatting already present
in the same file as rStyle="italic" / rStyle="bold". 13 <em> and 24 <b> blocks fail to
close in the typed version; 0 do in the rebuilt one. See tools/styles_probe.py for the
check that the styles mean emphasis and nothing else.

Line numbering is the 1-based w:p index. Splitting on </w:p> instead leaves the
<w:body> preamble on line 1 and shifts every number by one.
"""
import json, re, html, zipfile, pathlib, sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCX = ROOT / 'languages/english/data-app-Foreword-through-900s-no-auxilliaries.docx'
OUT = ROOT / 'build'
OUT.mkdir(exist_ok=True)

with zipfile.ZipFile(DOCX) as z:
    xml = z.read('word/document.xml').decode('utf8')

T = re.compile(r'<w:t(?: [^>]*)?>(.*?)</w:t>', re.S)      # not <w:tabs>
R = re.compile(r'<w:r[ >](?:(?!</w:r>).)*?</w:r>', re.S)   # not <w:rPr>
PARA = re.compile(r'<w:p[ >].*?</w:p>', re.S)
STYLE = re.compile(r'<w:rStyle w:val="(italic|bold)"')
# Typed markup literals the transcriber left sitting inside the formatted runs.
TAGLIT = re.compile(r'</?(?:em|b|p|div|li|ol|ParaNum|PaaNum|SubPoint|DIV)\b[^>]*>', re.I)

paras = PARA.findall(xml)
out = []
for pi, p in enumerate(paras, 1):
    runs = []
    for r in R.findall(p):
        t = html.unescape(''.join(T.findall(r)))
        if t:
            m = STYLE.search(r)
            runs.append((m.group(1) if m else None, t))

    # Merge adjacent runs sharing a style — InDesign kerning splits "Holy Bible"
    # into 'Ho' 'l' 'y' 'Bibl' 'e', which is why the raw rStyle count is 3x the
    # number of logical spans.
    merged, cur, curstyle = [], [], '\x00'
    for st, t in runs:
        if st == curstyle:
            cur.append(t)
        else:
            if cur:
                merged.append((curstyle, ''.join(cur)))
            cur, curstyle = [t], st
    if cur:
        merged.append((curstyle, ''.join(cur)))

    body = []
    for st, t in merged:
        t = TAGLIT.sub('', t)
        if not t:
            continue
        if st and t.strip():
            tag = 'em' if st == 'italic' else 'b'
            lead = t[:len(t) - len(t.lstrip())]
            trail = t[len(t.rstrip()):]
            body.append('%s<%s>%s</%s>%s' % (lead, tag, t.strip(), tag, trail))
        else:
            body.append(t)

    out.append({'n': pi, 'typed': ''.join(t for _, t in runs), 'formatted': ''.join(body)})

assert len(out) == len(paras), 'block/w:p misalignment'
json.dump(out, open(OUT / 'paras.json', 'w', encoding='utf8'), ensure_ascii=False)


def bal(t, x):
    return len(re.findall(r'<' + x + r'[ >]', t)) - len(re.findall(r'</' + x + r'>', t))


print('w:p paragraphs :', len(out))
for x in ('em', 'b'):
    print('  <%s> unbalanced blocks — typed: %d   rebuilt from styles: %d'
          % (x, sum(1 for o in out if bal(o['typed'], x)),
             sum(1 for o in out if bal(o['formatted'], x))))
