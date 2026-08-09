# Manual data-shape plan

Source of truth: `languages/english/data-app-Foreword-through-900s-no-auxilliaries.docx`.
Auxiliaries get fitted to this shape later, once English is proven out.

## What the source actually looks like

Word paragraphs whose _text_ contains hand-typed pseudo-HTML:

```
<div className=‘subheading’>X. Christian Holiness and Entire Sanctification</div>
<p><ParaNum>10.</ParaNum> We believe that sanctification is the work of God…</p>
<p>We believe that entire sanctification is that act of God…</p>
<p><ParaNum>10.1.</ParaNum> We believe that there is a marked distinction…</p>
<div className=‘note’>(Jeremiah 31:31-34; …)</div>
```

Measured:

| thing                       | count                                                                                                   |
| --------------------------- | ------------------------------------------------------------------------------------------------------- |
| `w:p` (Word paragraphs)     | 2151                                                                                                    |
| nonblank typed lines        | 2151                                                                                                    |
| `<ParaNum>`                 | 994 (993 unique)                                                                                        |
| `<SubPoint>`                | 18                                                                                                      |
| `<p>` opens / `</p>` closes | 1988 / 1291                                                                                             |
| `<div>` / `<li>` / `<ol>`   | 292 / 209 / 4                                                                                           |
| `className` values          | subheading 130, note 116, part-chapter-list 45, heading-1 35, part-title 9, part-number 8, small-caps 5 |

### Known dirt

- **Unbalanced tags.** 1988 `<p>` vs 1291 `</p>`. 336 `w:p` contain two typed block tags, 3 contain none.
- **Typos.** `PaaNum` ×22, one uppercase `<DIV>`.
- **Curly quotes**, inconsistent: `className=‘note’` / `’note’` / `'note'`.
- **Symbol-font PUA chars.** ``is`<p>` typed with Symbol font active. ~12 lines.
- **`<li>` without `<ol>`**: 209 vs 4. And markers typed into the text: `<ol><li>1. recommendation from…`
- **Bare numbers, no wrapper**: `346.3. <b>Regional Advisory Council (RAC).</b> …`
- **`<ParaNum>The</ParaNum>`** — one non-numeric.
- Word's `w:pStyle` is useless for `kind` — 1959 of 2151 paragraphs carry no style. Typed `className` is the real signal.

### Consequence

Do **not** balance the typed tags — they don't balance, and no tolerant parser recovers boundaries from them.

**One `w:p` = one block.** That boundary is exact (2151 = 2151). Typed markup is only ever _read_ for its leading tag, `className`, `<ParaNum>` / `<SubPoint>` value, and inline `<b>`/`<em>` — never parsed as a tree.

## The data shape

Two tables. The driving constraint is the translation app: **every piece of text must be an addressable, alignable node** — including headings and standalone notes — so a translator can sit any node beside its English original. That means no orphan blocks; `blocks.unit_id` is NOT NULL, and non-paragraph content gets a unit with a hidden auto-generated number.

**The 2023 Manual paragraph numbers are canonical.** A translation may not renumber, reorder, insert, or drop a numbered paragraph. Rather than enforce that with validation, the schema is split so it _cannot be expressed_: structure lives in one language-independent table, translatable text in another.

Verified this holds in the source: 1013 numeric ParaNums, strictly increasing, zero ordering violations, 1 → 934. Document order and numeric order agree everywhere. (3 mis-tagged — `Our`, `The`, `The` — go in overrides.)

### `nodes` — canonical structure, no language

| column           | type            | notes                                                                           |
| ---------------- | --------------- | ------------------------------------------------------------------------------- |
| `key`            | text PK         | `10.1` for numbered; `fwd`, `art-10-note` for unnumbered. Language-invariant    |
| `role`           | text            | `paragraph` \| `heading` \| `note` \| `part`                                    |
| `number`         | text            | display form `"10.1"`; null for unnumbered                                      |
| `number_visible` | bool            | false for auto-generated keys                                                   |
| `sort_key`       | int[]           | `[10,1]` — `"10."` sorts before `"2."` as a string, so display form can't order |
| `parent_key`     | text FK → nodes | 10.1 → 10; nullable                                                             |
| `order`          | int             | gapped by 1000                                                                  |

There is exactly one row per node for all languages. Numbering, ordering, and hierarchy are therefore _unable_ to differ per language — the canonical guarantee is enforced by there being nowhere to put a divergent value.

### `blocks` — translatable text

| column        | type            | notes                                                                             |
| ------------- | --------------- | --------------------------------------------------------------------------------- |
| `id`          | text PK         | 8-char nanoid, stable                                                             |
| `node_key`    | text FK → nodes | NOT NULL                                                                          |
| `lang`        | text            | `'en'`, `'es'`, …                                                                 |
| `ordinal`     | int             | position within the node, 0-based                                                 |
| `kind`        | text            | see below                                                                         |
| `marker`      | text            | `(1)` for subpoints, `1.` for list items; null otherwise. Extracted out of `body` |
| `body`        | text            | inline `<b>`/`<em>` preserved; `<ParaNum>`/`<SubPoint>` spans stripped            |
| `source_line` | int             | 1-based `w:p` index in that language's source, for diffing                        |

`source_line` really is the `w:p` index. An early pass split the XML on `</w:p>`, which left the `<w:body>` preamble on line 1 and shifted every number by one — so the extractor asserts `len(blocks) == len(w:p)` with index alignment. Cheap tripwire for a defect that is otherwise invisible.

Unique on `(node_key, lang, ordinal)`.

**Alignment is guaranteed at the node level, best-effort within it.** A translation may legitimately split one English paragraph into two sentences-worth of blocks or merge two — so block counts per node can differ by language. The side-by-side view pairs nodes (always exact) and pairs blocks by ordinal (usually right, and visibly ragged when it isn't, which is the correct failure mode).

`blocks.kind`: `lead` · `continuation` · `subpoint` · `list-item` · `note` · `bible-reference` · `heading-1` · `subheading` · `part-title` · `part-number` · `part-chapter-list` · `small-caps`

## Inline `<em>` / `<b>` do NOT export cleanly — 37 blocks affected

Globally `<b>` looks balanced (303/303) and `<em>` nearly so (175/172), but that hides the problem: emphasis routinely crosses a paragraph mark. Per block, 24 `b` and 13 `em` blocks are unbalanced. Four distinct classes:

**1. Leaked close tag — 15 cases, mechanical fix.** The paragraph mark got swallowed inside the emphasis run, so `</b>` lands at position 0 of the _next_ block:

```
<p><ParaNum>813.</ParaNum> <b>Local Minister’s License</p>
</b><p>THIS IS TO CERTIFY that ______ is licensed as a Local Minister…
```

`b`: 195/196, 467/468, 998/999, 1965/66, 1973/74, 2011/12, 2017/18, 2023/24, 2032/33, 2056/57, 2059/60 (11 — all the run-in bold heading pattern).
`em`: 1893/94, 1895/96, 1897/98 (rubric labels "For a Believer:"), 1975/76 (4).
Fix: move the close to the end of the previous block, drop the orphan. Safe to automate.

**2. Genuine multi-block span — 1 case, must be preserved.** Lines 1818–1825, the Agreed Statement of Belief: eight consecutive paragraphs all italic, `<em>` opening at 1818 and closing at 1825. The intent is real and can't be discarded.

**3. Never closed — 3 cases, need judgment.**

- 653, 1025: `the <em>Manual of the Church of the Nazarene.</p>` — italic book title, close belongs after `Manual`, not at block end.
- 201: `reflect<em>s </em>the global nature` plus a second unclosed open — a tracked-changes artifact; the italic on a single letter is meaningless.

**4. Ambiguous — 1 case.** 1978 opens `<b>`, 1980 closes it, with 1979 in between. Review by hand.

### RESOLVED — the real emphasis is already in the file as character styles

The typed tags are not the only record of emphasis. Every run also carries a Word **character style**: `rStyle="italic"` (624 refs) and `rStyle="bold"` (931 refs). The `italic` style contains a genuine `<w:i/>`. The transcriber typed the tags *while the formatting was switched on*, so the styles bracket the tag literals too:

```
w:p 1976 runs:   italic:'<em>'   italic:'Manual '   italic:'</em>'   plain:'225.13) '
```

Merging adjacent same-style runs and stripping the typed tag literals gives **176 italic and 297 bold logical spans**, against 175 and 303 typed tags. The raw 624/931 was pure run fragmentation — InDesign kerning splits "Holy Bible" into `'Ho' 'l' 'y' 'Bibl' 'e'`. Zero italic spans and one bold span are bare paragraph numbers, so the styles mean emphasis and nothing else.

**Rebuilding every paragraph from its character styles yields 0 unbalanced blocks**, against 13 `<em>` and 24 `<b>` in the typed version. All 37 breakages resolve with no heuristic.

So: **emphasis comes from `rStyle`; the typed `<em>`/`<b>` are authoritative for nothing and are discarded.** Block `kind` still comes from the typed `className`, which the styles do not encode — hence the hybrid: structure from the typed markup, inline emphasis from the character styles.

Cases the styles settled that the heuristics could not:
- 652 / 1024 — the italic covers the **full title**, `Manual of the Church of the Nazarene.`, not just `Manual`.
- 1977–1979 — three **independent** bold run-in headings. My nearest-preceding matcher invented a multi-block span that was never there; the 12-block `MAXSPAN` cap produced a false positive. Exactly the failure mode the style data removes.
- Trailing spaces fall outside the emphasis automatically: `<em>Manual</em> 505-520`.

Remaining judgment calls: **5 spans across the whole document** put emphasis on punctuation with no word attached (an italic full stop at w:p 200 and 1327, a bold colon at 537, `;` at 167, `:` at 1854). Almost certainly authoring slips. Review page: <https://claude.ai/code/artifact/ef7fd9dd-49dd-430b-83ec-71007d2962c7>

### Punctuation normalization — the "belongs-to" rule

Print convention puts punctuation inside the emphasis; digital practice keeps the markup semantic. For a store-once/render-many system the semantic form must win in storage — the printed look is restored with CSS at render time, whereas punctuation baked into the data cannot be cleanly removed later.

The cost of not doing this, measured in this file: the *Manual* title appeared **79 times in 6 distinct stored strings** (`Manual`, `Manual,`, `Manual.`, `Manual of the Church of the Nazarene.`, …) differing only by the punctuation that followed. `Regional Sourcebook for Ministerial Development` was fragmented three ways. For the translator app this is decisive — Spanish and French punctuate differently, so a span carrying its punctuation won't align with its counterpart.

**The test is not the mark or the tag — it is what the punctuation belongs to.**

| example | punctuation belongs to | goes |
|---|---|---|
| **Business.** | the run-in heading | inside |
| *Response:* | the rubric label | inside |
| …and the IBOE**.** | the sentence | outside |
| *Whither Holiness?* | the title itself | inside |

Implemented as: a span is a **label** when nothing precedes it in the block but whitespace, the paragraph number, and stray markup debris. Labels keep their terminal punctuation; inline spans give it up.

Applied to the source: **31 marks moved out, 231 kept inside** (190 bold run-in headings ending in a period, 25 italic rubric labels ending in a colon). Result: *Manual* collapses from 6 stored forms to 2, `Regional Sourcebook…` to 1.

Two bugs the pass exposed, both fixed:
- **Split spans.** 6 spans across 4 paragraphs were one emphasis run broken by an intervening space — `<b>duties…President</b> <b>are:</b>`, `<em>Regional</em> <em>Sourcebook for</em> <em>Ministerial Development</em>`. Merge before testing anything, or the label test and the title consolidation both misfire.
- **Stray markup defeating the label test.** w:p 1634 opens `<532.13.` — a bare `<` before the number — so the lead-in test must tolerate markup debris.

### Blackline residue — italics that are not emphasis

¶15 and ¶27 carried italics left over from the legal-blackline markup originally used to show revisions: `We believe that <em>at the end of the age</em> the Lord Jesus Christ will <em>be revealed as Lord of all. He will</em> come again…`, and `reflect<em>s</em>` where a tracked insertion kept its formatting. These are not emphasis and are dropped wholesale.

A sweep of every italic span that occurs once and runs three or more words found no others — the remaining ones are all publication titles (`Global Missions Operations Handbook`, `General Board Policy Manual`, `Guide to Christian Perfection`). 45 distinct italic spans in total, all accounted for.

All decisions live in `overrides.json`, keyed by `source_line` + span text, with the reason recorded.

### Design consequence

Because class 2 is real, a raw-HTML `body` string means some blocks cannot be rendered independently — which breaks the side-by-side node view, where a block is displayed on its own. So the normalizer must make **every block self-contained**: a span crossing block boundaries is re-opened in each block it covers. After normalization, per-block open/close counts must match for every block — that's a hard gate, not a warning.

Also cosmetic: `<em>Manual </em>` puts the trailing space _inside_ the tag throughout, italicizing whitespace. Normalize by pulling trailing spaces out of emphasis runs.

## Assignment rules

1. Walk `w:p` in order; each becomes one block.
2. **Normalize first**: Symbol-PUA → ASCII, straighten curly quotes in `className`, `PaaNum`→`ParaNum`, `DIV`→`div`.
3. `<ParaNum>N.</ParaNum>` **or** `^\d+(\.\d+)*\.\s` at block start → open a new `role=paragraph` unit, block `kind=lead`.
4. Plain `<p>` while a paragraph unit is open → `kind=continuation` of that unit.
5. `<SubPoint>(n)</SubPoint>` and `<li>` → `kind=subpoint` / `list-item` **of the currently open unit**, marker extracted. They are _not_ their own units — "201.1 subpoint (2)" resolves to unit 201.1 rendered whole, with subpoints as an OL. This matches how citations are actually written.
6. **Notes** — the split your data already shows (85 follow a paragraph, 19 follow another note, 10 follow a heading):
   - Following a paragraph or another note → block of the open unit, `kind = note` or `bible-reference`.
   - Following a heading, or with no open unit → **its own** `role=note` unit with a hidden auto-number. Independent, inserted in the flow.
7. `heading-1` / `subheading` / `part-*` → close the open paragraph unit, become their own `role=heading` / `role=part` unit with a hidden auto-number and a single block. **That heading unit stays open as fallback parent** — see below.

### Orphan blocks — measured, not hypothetical

201 blocks (198 `<p>`, 3 `<li>`) occur with no numbered paragraph open: the whole Foreword, plus stray list runs. With `unit_id NOT NULL`, rule 7 closing the unit outright would fail the load. So a heading's unit remains the parent for any following unnumbered prose until the next lead or heading. The Foreword becomes one `role=heading` unit ("FOREWORD") carrying ~9 continuation blocks — which is also the right translation granularity.

### `note` vs `bible-reference`

A run like ¶10's is 6 consecutive note divs; the first starts `(Jeremiah 31:31-34; …)` but later ones start `“Heart purity”: Matthew 5:8; …`. So "starts with `(`" is insufficient (only 51 of 116 match). Classify by scripture-citation density — `Book Ch:Vv` pattern coverage over the block — then **hand-review all 116**. It's a small enough set to be worth eyeballing once.

Verified: all 9 notes following a heading are genuinely independent — editorial notes (`NOTE: Scripture references are supportive of the Articles of Faith…`) and ritual rubrics (`When the sponsors shall have presented themselves with the child…`). The rule holds against the class, not just one line. Note also that `note` appears as both `<div className='note'>` and `<p className='note'>`, and one is mangled: `<b><p className='note'>NOTE:</b>`.

## Import: English is the skeleton (decided)

Sequential auto-keys (`u:auto:0042`) would be a **position, not a key** — a Spanish import with one extra heading shifts every subsequent key by one and skews the alignment silently. So:

**Only the English import writes `nodes`.** Translation imports never mint, renumber, or reorder anything; they attach blocks to node keys that already exist.

- Numbered paragraphs auto-match on their canonical number. A translation carrying `10.1` lands on node `10.1`, full stop.
- Unnumbered nodes (headings, Foreword, standalone notes) can't auto-match reliably, so they're **queued for human confirmation** in the translator app — anchored between their two neighbouring numbered paragraphs, which narrows the candidates to a handful.
- A translation containing a paragraph number not in `nodes`, or missing one that is, is an **import error**, not a new node. That's the canonical guarantee showing up as a loud failure instead of a silent skew.

Unnumbered keys are generated once during the English import and stored. They are derived from their anchoring paragraph (`art-10-note`, not `auto-0042`) so they stay legible and don't renumber when something is inserted elsewhere.

## Stability / idempotency

Many translations are coming, in mixed formats (PDF, Word, INDD), prepped separately. The translator app shows each node beside its English original, so alignment is the whole product.

- Node keys minted once during the English import, persisted, never regenerated.
- Importer is idempotent: match on `key` for nodes and `(node_key, lang, ordinal)` for blocks; mint only for genuinely new content.
- Re-running the English import must produce zero ID churn and zero `nodes` diff. **Test this explicitly** — import twice, diff.

### Validation gates on every import

- ParaNums strictly increasing (holds today: 1013 numbers, 0 violations).
- **Every block's inline tags balance within that block** (fails today for 37 blocks; must pass post-normalization).
- Document order == `sort_key` order for all numbered nodes.
- No translation import creates or removes a `nodes` row.

### Normalizer tripwire

994 `<ParaNum>` + 22 `<PaaNum>` = 1016 = the `</ParaNum>` count, exactly. So all 22 typos are open-tag-only. Assert post-normalization that ParaNum opens == closes == 1016; if that ever drifts, the normalizer broke something.

## Rendering

`SELECT * FROM blocks ORDER BY "order"` reproduces the document start to finish. Join `units` to render the number in front of `kind=lead` where `number_visible`. Group consecutive `subpoint` / `list-item` blocks into an `<ol>` at render time.

## Built — `manual.json`

Generated by `tools/build.py`. 1.2 MB, `{lang, source, nodes[], blocks[]}`. See `tools/README.md` to run it.

| | |
|---|---|
| nodes | 1202 — 1014 numbered, 188 generated |
| roles | paragraph 1014, heading 171, part 9, note 8 |
| blocks | 2132 of 2151 `w:p` |
| kinds | lead 1014, continuation 549, list-item 211, subheading 128, note 59, bible-reference 55, part-chapter-list 45, heading-1 35, subpoint 18, part-number 9, part-title 9 |
| numbers | 1 → 934 |

### Two hierarchies, deliberately separate
- **`parent_key`** — numeric: `10.1` → `10`.
- **`section_key`** — structural: `10` → *X. Christian Holiness and Entire Sanctification* → *ARTICLES OF FAITH* → *PART II*.

Levels are `part-number` 1, `heading-1` 2, `subheading` 3. Walk `section_key` transitively for containment: PART III resolves to 44 nodes, 96 blocks, ¶28–¶35. Ten roots — the Foreword plus 9 parts (I-VIII and X). PART IX, the auxiliary constitutions, exists in the Manual but is not in this export and has not been added yet; the parts gate is set to 9 and will fail deliberately when it lands.

1014 numbered nodes against 1013 tagged `<ParaNum>` — the extra is `346.3`, which has no wrapper and is caught by the bare-number fallback.

The 19 `w:p` with no block are empty structural markup only: `<ol>` ×2, `</ol>`, two empty `<div className='subheading'></div>`, and 14 bare `<p><p>`. No text is lost.

### Pipeline
1. `tools/extract.py` — each `w:p` twice: as typed, and rebuilt from character styles.
2. `tools/normalize.py` — punctuation rule, span merging, `overrides.json` applied.
3. `tools/build.py` — nodes and blocks, with the gates below.
4. `tools/styles_probe.py` — the check that the character styles mean emphasis.

### Source defects the build exposed
- **A leading `"1. "` is not always a paragraph number.** Numbered list items inside the forms and rituals minted duplicate nodes for ¶1–¶8 — forty collisions. The bare-number fallback now only fires when the number *exceeds* the previous one, which is safe because the sequence is strictly increasing.
- **22 paragraphs carry a stray `<` before the number** — `<530.10.`, `<531.11.`, `<606.12.` and so on, all in the 530/531/532/606 ranges. Re-parsing the body text missed every one. The build now takes the number from the `<ParaNum>` tag and only falls back to the body.
- **¶220.3 has no period after its number** — `220.3 To forward…`. Same fix covers it.
- **`PART III` is typed in uppercase markup** — `<DIV CLASSNAME='PART-NUMBER'>`, the only such block in the file. A case-sensitive `className` match silently demoted it to body text, so PART III had no node and everything in it was orphaned from the hierarchy.
- **A `part-chapter-list` can reappear far from its part** (w:p 209, 1741). Folding those into a part node created hundreds of paragraphs earlier breaks document order, so the title and chapter list are only merged into the part when contiguous.
- **Five small-caps runs** are typed as `<span className='small-caps'>`; they become a real `<sc>` inline tag.
- `` is a ballot box on the printed forms, not a `<p>` fragment — 20 blocks carry it as `☐`.

### Gates (all passing)
- node keys unique; block ids unique; every block has a node; every parent key exists
- blocks in document order; paragraph numbers strictly increasing
- no body contains markup outside `<em> <b> <sc>`; all inline tags balance within their block
- **re-running produces a byte-identical file** — ids are `sha1(lang|node_key|ordinal)[:8]`, so the build is reproducible and the double-import test is trivial

## Steps

1. Normalizer + extractor → `manual.json` (units + blocks). No DB yet.
2. Review pass: the ~116 notes, and any block the rules can't classify. Corrections go in a **versioned `overrides.json`** next to the importer, keyed by `source_line` + body-hash — _not_ into the docx. Edits that live only in a binary Word file are lost the moment someone re-exports, and the pipeline has to stay re-runnable.
3. Supabase migration for the two tables.
4. Loader with the idempotency matching above; double-import test.
5. React renderer over the ordered blocks.
