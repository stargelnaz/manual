# Manual text styles

A working spec for the Manual's text styles, to edit before any reader CSS is written.
It replaces the 50+ InDesign paragraph styles with a short, logical set. When a style
here is settled, it becomes a class in `src/manual.css` under the
same name.

## Conventions

- **Names** are lowercase kebab-case, `family-variant`: `para`, `list-bullet`,
  `heading-1`. The family says what the text is; the variant says how it differs. No
  spaces, no "Manual" prefix. The classes are scoped under the reader's `.manual`
  container, which keeps them clear of `ui.css`.
- **Sizes** are in print points and picas (`0p9` = 9pt, `1p6` = 18pt), the units of the
  InDesign file. `.manual` sets `--pt`, one print point at the current screen scale
  (`src/manual.css`), so `0p9` is written as `calc(9 * var(--pt))` and keeps its
  proportion to the body text at any width.
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

Every paragraph keeps its indent, including the first one after a heading.

### `note`
Smaller, block-indented text set off from the body. *InDesign: Manual Note.*

| | |
|---|---|
| Size / leading | 8pt / 1.5 (print 7/8.5) |
| Left indent | 0p9 (whole block) |
| First-line indent | 0 |
| Space before / after | 0p3 / 0p3; between two notes, one 0p3 |
| Alignment | ragged right |
| Color | `--text-muted` |
| Data kinds | `note`, `bible-reference` |

## Lists

Every list is set with a hanging indent, so a reader can scan the markers: the
marker starts at the 0p9 paragraph indent and the text, turnover lines included,
aligns at 2p3. The three styles differ only in their marker. Markers are stored
text, never CSS counters, because the source numbering is canonical and sometimes
restarts. Markers are bold (700) in `--text-strong`, like `para-number`. A marker
wider than 1p6 pushes its first line along rather than overlapping the text. CSS: `.manual .list`, `.list-item`, `.list-marker` in `src/manual.css`.
*InDesign: TBD.*

| | |
|---|---|
| Based on | `para` |
| Marker | at 0p9, in a 1p6 box; weight 600 |
| Text and turnover lines | 2p3 (hanging) |
| Space around the list | 0p3 |
| Space between items | 2.5pt |

### `list-number`
Numbered list, as in 100.2. Marker: stored text (`1.`, `(1)`).
Data kinds: `list-item` with a marker, `subpoint`.

### `list-hanging`
The numbered lists of 810.4 (Our Values) and 810.5 (Our Guiding Principles). Kept as
its own kind from the source; set exactly as `list-number`.
Data kinds: `list-hanging`.

### `list-bullet`
Unnumbered list items. No marker is drawn yet; the text sits at 2p3 like the other
lists. *Bullet TBD.*
Data kinds: `list-item` with no stored marker.

## Tables

The delegate tables (201.1, 201.2, 205.15, 301.1). Word sets each row as a paragraph
with its cells on tab stops; the data keeps one `\t` between cells and the reader sets
consecutive rows as one table, so the columns line up. The tables are listed by
paragraph in `tools/build.py` (`TABLES`), not detected, since tabs also follow list
markers and fill the blanks on the forms. 601.2 is a table too, but is still prose
until its hand-wrapped second column is cleaned up.

### `table`
*InDesign: TBD.*

| | |
|---|---|
| Size / leading | as `para` |
| First-line indent | 0 |
| Space between rows | 0 |
| Space before | 0p3; none after, so `table-note` sits tight |
| Columns | one per tab-separated cell, sized to the content, 1p6 apart |
| Cell alignment | centered, as on the Word tab stops |
| Column heads | the first row; same weight as the body, as in print |
| Number ranges | en dash (`0–6,000`) |
| Data kinds | `table-row` |

### `table-note`
The parenthetical rule that closes a table: "(For every 5,000 members above
40,000…)". *InDesign: TBD.*

| | |
|---|---|
| Based on | `para` |
| First-line indent | 0 |
| Space before / after | 0 / 0p3 |
| Data kinds | `table-note` (the block straight after a table) |

## Headings and part openers

Carried over from the current reader so the whole set lives in one place. Their
names are still open. These are the only styles with space before and after.

| Style | Spec (as currently built) | Data kind |
|---|---|---|
| `part-number` | 8.5pt caps, centered, accent color | `part-number` |
| `part-title` | bold 15/18, centered | `part-title` |
| `part-contents` | 8pt centered, muted | `part-chapter-list` |
| `heading-1` | bold serif 12/14, centered, 0p6 before / 0p3 after | `heading-1` |
| `heading-2` | sans 10/12 at weight 500, centered, 0p6 before / 0p3 after | `subheading` |

## Inline (character) styles

| Style | Markup in data | Rendering |
|---|---|---|
| emphasis | `<em>` | italic |
| strong | `<b>` | bold (700), in `--text-strong` |
| `small-caps` | `<sc>` | `font-variant: small-caps` |
| `para-number` | paragraph number before a `lead` block | bold (700), in `--text-strong`, always followed by a full stop, then a space: `32.`, `102.2.` |
| `cross-reference` | `<ref to="key">` around one item of a paragraph reference | a link in `--text-muted` (the `note` color), no underline, no visited state |

The full stop is added when the number is displayed. The stored number stays `32` or
`102.2`, because it's also the paragraph's key for sorting and cross-references.

The numbered rituals (700–709) are `heading-2` blocks whose node carries the number.
It is shown before the title in the heading's own style: `700. LORD’S SUPPER`.

Each item of a cross-reference links to the paragraph its first number names, so
`(300.1–300.3, 301)` is two links, to 300.1 and to 301. `tools/build.py` adds the
tags; an item that names no paragraph in this export (a year, the 800s) must be
listed in `overrides.json` under `references`.

## Dashes

| Where | Dash | Example |
|---|---|---|
| running text | hyphen `-` | `2017-2021`, `co-pastors` |
| reference range within one chapter, or within one paragraph (subpoint to subpoint, or the paragraph to one of its subpoints) | en dash `–` | `Romans 1:18–25; 5:12–14`, `(300.2–300.3)`, `(113–113.1)` |
| reference range across chapters, or across paragraphs | em dash `—` | `Romans 7:1—8:9`, `(100—109)`, `(103—104.3)`, `(139.19—140)` |

References are stored with these dashes, set by `tools/normalize.py`. Type a plain
hyphen in the Word source; the build picks the dash.

## InDesign styles not yet mapped

List the remaining InDesign style names here with a decision for each: map to a
style above, add a new one, or drop it.

| InDesign style | Decision |
|---|---|
| | |

## Open questions

1. **Nesting:** do notes ever contain lists, or lists contain notes or sub-lists? If
   they do, the indents need to add up (for example, a list in a note starts at
   0p9 + 0p9).
