# Manual text styles

A working spec for the Manual's text styles, to edit before any reader CSS is written.
It replaces the 50+ InDesign paragraph styles with a short, logical set. When a style
here is settled, it becomes a class in `src/manual.css` (not yet created) under the
same name.

## Conventions

- **Names** are lowercase kebab-case, `family-variant`: `para`, `para-flush`,
  `list-bullet`. The family says what the text is; the variant says how it differs. No
  spaces, no "Manual" prefix. The classes are scoped under the reader's `.manual`
  container, which keeps them clear of `ui.css`.
- **Sizes** are in print points and picas (`0p9` = 9pt, `1p6` = 18pt), the units of the
  InDesign file. The reader already scales print points to the screen (`pt()` in
  `ManualReader.jsx`), so `0p9` is written as `pt(9)` and keeps its proportion to the
  body text at any width.
- **Leading** is one unitless value, `--leading-body` (1.5), for all running text. The
  print leading (10.5 on 9.25, 8.5 on 7) is listed for reference only. Headings set
  their own leading.
- **Paragraphs are separated by indents, not space.** Running text has no space
  before or after. Only divisions (headings and part openers) add vertical space.
- **Ragged right** for all running text. Nothing is justified.
- **No tracking or character-spacing adjustments.** `letter-spacing` is never set. The
  print file adjusted character spacing to fit lines; the web version doesn't.
- **Data → style.** Each block `kind` in the data maps to exactly one style, shown under
  each entry. Several kinds may share a style.
- Any value marked **TBD** is still to be decided.

## Body

### `para`
The default running paragraph. *InDesign: Manual Paragraph Text.*

| | |
|---|---|
| Size / leading | 9.25pt / 1.5 (print 9.25/10.5) |
| First-line indent | 0p9 |
| Space before / after | 0 |
| Alignment | ragged right |
| Data kinds | `lead`, `continuation` |

A numbered paragraph (a `lead` block with a visible number) is always `para`, never
`para-flush`, even directly after a heading. It keeps its indent.

### `para-flush`
`para` with no first-line indent. Used for an unnumbered paragraph that follows a
heading, where the heading already marks the start, as in conventional typesetting.
*InDesign: TBD (is there one?).*

| | |
|---|---|
| Based on | `para` |
| First-line indent | 0 |
| Applies to | the first block after a heading, unless it is a numbered paragraph |
| Data kinds | none: applied by position, not stored |

### `note`
Smaller, block-indented text set off from the body. *InDesign: Manual Note.*

| | |
|---|---|
| Size / leading | 8pt / 1.5 (print 7/8.5) |
| Left indent | 0p9 (whole block) |
| First-line indent | 0 |
| Space before / after | TBD (see question 1) |
| Alignment | ragged right |
| Color | `--text-muted` |
| Data kinds | `note`, `bible-reference` |

## Lists

### `list-bullet`
Generic bulleted list, with a hanging indent: the bullet sits at 0p9 and the text at
1p6, so turnover lines align with the first word, not the bullet. *InDesign: TBD.*

| | |
|---|---|
| Size / leading | as `para` |
| Marker | `•` at 0p9 |
| Text indent | 1p6 (hanging) |
| Space between items | 0 |
| Data kinds | `list-item` with no stored marker |

### `list-number`
Numbered list, set like a paragraph rather than with a hanging indent (see 100.2):
the number starts at the 0p9 first-line indent, the text follows it on the same line,
and turnover lines return to the left margin. The numbers are stored text, never CSS
counters, because the source numbering is canonical and sometimes restarts.
*InDesign: TBD.*

| | |
|---|---|
| Based on | `para` |
| First-line indent | 0p9 |
| Marker | stored text (`1.`, `(1)`), then a space; weight TBD |
| Turnover lines | flush to the left margin |
| Space between items | 0 |
| Data kinds | `list-item` with a marker, `subpoint` |

## Headings and part openers

Carried over from the current reader so the whole set lives in one place. Their
names are still open. These are the only styles with space before and after.

| Style | Spec (as currently built) | Data kind |
|---|---|---|
| `part-number` | 8.5pt caps, centered, accent color (current 0.25em tracking to be removed) | `part-number` |
| `part-title` | bold 15/18, centered | `part-title` |
| `part-contents` | 8pt centered, muted | `part-chapter-list` |
| `heading-1` | bold serif 12/14, centered, 0p6 before / 0p3 after | `heading-1` |
| `heading-2` | sans 11/13 at weight 500, centered, 0p6 before / 0p3 after | `subheading` |

## Inline (character) styles

| Style | Markup in data | Rendering |
|---|---|---|
| emphasis | `<em>` | italic |
| strong | `<b>` | bold |
| small caps | `<sc>` | `font-variant: small-caps` |
| `para-number` | paragraph number before a `lead` block | bold, always followed by a full stop, then a space: `32.`, `102.2.` |

The full stop is added when the number is displayed. The stored number stays `32` or
`102.2`, because it's also the paragraph's key for sorting and cross-references.

## InDesign styles not yet mapped

List the remaining InDesign style names here with a decision for each: map to a
style above, add a new one, or drop it.

| InDesign style | Decision |
|---|---|
| | |

## Open questions

1. **Space around notes.** With no space between paragraphs, a note relies on its
   smaller size and 0p9 indent to stand apart from the body. Is that enough, or
   does a note (or a run of notes) get space before and after? The same question
   applies to two notes in a row: they have no first-line indent to separate them.
2. **Number weight in lists.** Bold like `para-number`, or the same weight as the text?
3. **Nesting:** do notes ever contain lists, or lists contain notes or sub-lists? If
   they do, the indents need to add up (for example, a list in a note starts at
   0p9 + 0p9).
