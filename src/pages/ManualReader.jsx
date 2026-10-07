import { useEffect, useMemo, useRef, useState } from 'react';
import { supabase } from '../lib/supabase';

const PAGE = 1000; // PostgREST caps a single request at 1000 rows
const LANG = 'en';

async function fetchAllBlocks() {
  const rows = [];
  for (let from = 0; ; from += PAGE) {
    const { data, error } = await supabase
      .from('manual_reading_order')
      .select('*')
      .eq('lang', LANG)
      .order('doc_order')
      .order('ordinal')
      .range(from, from + PAGE - 1);
    if (error) throw error;
    rows.push(...data);
    if (data.length < PAGE) return rows;
  }
}

// Bodies contain only <em>, <b>, <sc> and <ref to="key"> — enforced by the build
// gates — and every tag balances within its block, so a single stack is enough to
// parse them. A ref is a paragraph cross-reference; its target is a node key.
const TAG_RE = /<(\/?)(em|b|sc|ref)(?: to="([^"]*)")?>/g;

function renderInline(body, keyPrefix) {
  const root = { tag: null, children: [] };
  const stack = [root];
  let last = 0;
  let n = 0;

  for (const m of body.matchAll(TAG_RE)) {
    const text = body.slice(last, m.index);
    if (text) stack[stack.length - 1].children.push(text);
    last = m.index + m[0].length;
    if (m[1] === '') {
      const node = { tag: m[2], to: m[3], children: [] };
      stack[stack.length - 1].children.push(node);
      stack.push(node);
    } else if (stack.length > 1) {
      stack.pop();
    }
  }
  const tail = body.slice(last);
  if (tail) root.children.push(tail);

  const toReact = (node) =>
    node.children.map((c) => {
      if (typeof c === 'string') return c;
      const key = `${keyPrefix}-${n++}`;
      if (c.tag === 'em') return <em key={key}>{toReact(c)}</em>;
      if (c.tag === 'b') return <b key={key}>{toReact(c)}</b>;
      // A real hash link, so the browser's Back returns to where the reader was.
      if (c.tag === 'ref')
        return (
          <a key={key} className="ref" href={`#${anchorId(c.to)}`}>
            {toReact(c)}
          </a>
        );
      return (
        <span key={key} style={{ fontVariant: 'small-caps' }}>
          {toReact(c)}
        </span>
      );
    });

  return toReact(root);
}

// Anchors are node keys, never paragraph numbers: keys are identity, numbers
// are display and may change between editions.
const anchorId = (nodeKey) => `n-${nodeKey}`;

// Blocks that appear in the contents. A part is two blocks (number, title) on
// one node; the anchor goes on the first.
const TOC_LEVEL = { 'part-number': 1, 'part-title': 1, 'heading-1': 2, subheading: 3 };

// Parts listed flat in the contents: no expandable chapters, but some chapters
// are promoted to their own top-level line under the part's number. Display
// only; the data keeps them as chapters. Keyed by node key.
const TOC_FLAT_PARTS = new Set(['m94m2y']); // Part X
const TOC_PROMOTE = {
  qg4bre: 'Administrative Policies',
  d38re5: 'Current Moral and Social Issues',
};

function Block({ block }) {
  const body = renderInline(block.body, block.id);
  // Contents entries and numbered paragraphs (what a cross-reference points to)
  // carry their node's anchor.
  const anchored = (TOC_LEVEL[block.kind] && block.kind !== 'part-title') || block.kind === 'lead';
  const id = anchored ? anchorId(block.node_key) : undefined;

  switch (block.kind) {
    case 'part-number':
      return (
        <div id={id} style={styles.partNumber}>
          {body}
        </div>
      );
    case 'part-title':
      return <div style={styles.partTitle}>{body}</div>;
    case 'part-chapter-list':
      return <div style={styles.partChapterList}>{body}</div>;
    case 'heading-1':
      return (
        <h2 id={id} style={styles.heading1}>
          {body}
        </h2>
      );
    case 'subheading':
      return (
        <h3 id={id} style={styles.subheading}>
          {block.number_visible && `${block.number}. `}
          {body}
        </h3>
      );
    case 'table-note':
      return <p className="table-note">{body}</p>;
    case 'note':
    case 'bible-reference':
      return <p style={styles.note}>{body}</p>;
    case 'lead':
      return (
        <p id={id} style={styles.paragraph}>
          {block.number_visible && (
            <span style={styles.paraNum}>{block.number}. </span>
          )}
          {body}
        </p>
      );
    default: // continuation
      return <p style={styles.paragraph}>{body}</p>;
  }
}

// Consecutive subpoint / list-item blocks render as one list. Markers are
// stored text ("(1)", "1."), not CSS counters — the source numbering is
// canonical and sometimes restarts, so it is reproduced verbatim.
function ListRun({ blocks }) {
  return (
    <ol style={styles.list}>
      {blocks.map((b) => (
        <li key={b.id} style={styles.listItem}>
          {b.marker && <span style={styles.marker}>{b.marker} </span>}
          {renderInline(b.body, b.id)}
        </li>
      ))}
    </ol>
  );
}

// Consecutive table-row blocks render as one table, so the columns line up. Each
// row's cells are separated by "\t"; the first row is the column heads.
function TableRun({ blocks }) {
  const [head, ...rows] = blocks.map((b) => b.body.split('\t'));
  const cells = (row, Cell, id) =>
    row.map((c, i) => <Cell key={i}>{renderInline(c, `${id}-${i}`)}</Cell>);
  return (
    <table className="table">
      <thead>
        <tr>{cells(head, 'th', blocks[0].id)}</tr>
      </thead>
      <tbody>
        {rows.map((row, r) => (
          <tr key={blocks[r + 1].id}>{cells(row, 'td', blocks[r + 1].id)}</tr>
        ))}
      </tbody>
    </table>
  );
}

const RUN_KIND = { subpoint: 'list', 'list-item': 'list', 'table-row': 'table' };

function groupBlocks(blocks) {
  const groups = [];
  for (const b of blocks) {
    const run = RUN_KIND[b.kind] ?? null;
    const last = groups[groups.length - 1];
    if (run && last?.run === run) {
      last.blocks.push(b);
    } else {
      groups.push({ run, blocks: [b] });
    }
  }
  return groups;
}

// Each Part opens a new sheet, like a section of the printed book.
function groupSheets(groups) {
  const sheets = [];
  for (const g of groups) {
    if (!sheets.length || (!g.run && g.blocks[0].kind === 'part-number')) sheets.push([]);
    sheets[sheets.length - 1].push(g);
  }
  return sheets;
}

const plainText = (body) => body.replace(/<[^>]+>/g, '');

// Contents tree from the heading blocks; containment comes from section_key.
// Parents precede children in document order, so one pass suffices. Inside a
// flat part (until the next part starts) headings are skipped, except promoted
// ones, which become roots numbered like their part.
function buildToc(blocks) {
  const byKey = new Map();
  const roots = [];
  let flatPart = null;
  for (const b of blocks) {
    if (!TOC_LEVEL[b.kind]) continue;
    if (b.kind === 'part-number') {
      flatPart = TOC_FLAT_PARTS.has(b.node_key) ? b.node_key : null;
    } else if (flatPart && b.node_key !== flatPart) {
      const title = TOC_PROMOTE[b.node_key];
      if (title && !byKey.has(b.node_key)) {
        const entry = {
          key: b.node_key,
          number: byKey.get(flatPart).number,
          title,
          parent: null,
          children: [],
        };
        byKey.set(b.node_key, entry);
        roots.push(entry);
      }
      continue;
    }
    let entry = byKey.get(b.node_key);
    if (!entry) {
      const parent = byKey.get(b.section_key) ?? null;
      entry = { key: b.node_key, number: '', title: '', parent, children: [] };
      byKey.set(b.node_key, entry);
      (parent ? parent.children : roots).push(entry);
    }
    if (b.kind === 'part-number') entry.number = plainText(b.body);
    else entry.title = plainText(b.body);
    if (b.kind === 'subheading' && b.number_visible) entry.number = b.number;
  }
  return { roots, byKey, keys: [...byKey.keys()] };
}

// The heading the reader is in: the last one above a line just below the
// navbar. Headings are in document order, so a binary search over their
// positions is enough on each scroll frame.
function useCurrentHeading(keys) {
  const [current, setCurrent] = useState(null);
  useEffect(() => {
    const els = keys.map((k) => document.getElementById(anchorId(k)));
    if (!els.length || els.some((el) => !el)) return;
    const line = (document.querySelector('.navbar')?.offsetHeight ?? 0) + 96;
    let frame = 0;
    const update = () => {
      frame = 0;
      let lo = 0;
      let hi = els.length - 1;
      let found = 0;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (els[mid].getBoundingClientRect().top <= line) {
          found = mid;
          lo = mid + 1;
        } else {
          hi = mid - 1;
        }
      }
      setCurrent(keys[found]);
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
    };
  }, [keys]);
  return current;
}

function TocList({ entries, ...props }) {
  return (
    <ul>
      {entries.map((e) => (
        <TocItem key={e.key} entry={e} {...props} />
      ))}
    </ul>
  );
}

// A branch follows the reading position (open while the reader is inside it)
// until the reader toggles it; after that their choice sticks.
function TocItem({ entry, current, trail, toggled, onToggle, onGo }) {
  const hasChildren = entry.children.length > 0;
  const open = hasChildren && (toggled.get(entry.key) ?? trail.has(entry.key));
  return (
    <li>
      <div className="toc-row">
        <button
          className="toc-link"
          aria-current={current === entry.key ? 'true' : undefined}
          onClick={() => onGo(entry.key)}
        >
          {entry.number && <span className="toc-number">{entry.number}</span>}
          {entry.title}
        </button>
        {hasChildren && (
          <button
            className="btn btn-sm btn-ghost toc-toggle"
            aria-expanded={open}
            aria-label={`${open ? 'Collapse' : 'Expand'} ${entry.title}`}
            onClick={() => onToggle(entry.key, !open)}
          >
            ▸
          </button>
        )}
      </div>
      {open && (
        <TocList
          entries={entry.children}
          current={current}
          trail={trail}
          toggled={toggled}
          onToggle={onToggle}
          onGo={onGo}
        />
      )}
    </li>
  );
}

function Toc({ toc, current, onGo }) {
  const [toggled, setToggled] = useState(() => new Map());
  const navRef = useRef(null);

  const trail = useMemo(() => {
    const keys = new Set();
    for (let e = toc.byKey.get(current); e; e = e.parent) keys.add(e.key);
    return keys;
  }, [toc, current]);

  // Keep the current entry visible in the sidebar. Scrolls only the sidebar;
  // scrollIntoView would also move the window while the banner is on screen.
  useEffect(() => {
    const box = navRef.current?.parentElement; // the sidebar
    const el = navRef.current?.querySelector('[aria-current="true"]');
    if (!box || !el) return;
    const r = el.getBoundingClientRect();
    const b = box.getBoundingClientRect();
    const bottom = Math.min(b.bottom, window.innerHeight);
    if (r.top < b.top) box.scrollTop -= b.top - r.top + 16;
    else if (r.bottom > bottom) box.scrollTop += r.bottom - bottom + 16;
  }, [current]);

  const onToggle = (key, open) => setToggled((m) => new Map(m).set(key, open));

  return (
    <nav ref={navRef} className="toc" aria-label="Contents">
      <TocList
        entries={toc.roots}
        current={current}
        trail={trail}
        toggled={toggled}
        onToggle={onToggle}
        onGo={onGo}
      />
    </nav>
  );
}

export default function ManualReader({ tocOpen, onTocClose }) {
  const [blocks, setBlocks] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAllBlocks().then(setBlocks, setError);
  }, []);

  const sheets = useMemo(() => (blocks ? groupSheets(groupBlocks(blocks)) : []), [blocks]);
  const toc = useMemo(() => buildToc(blocks ?? []), [blocks]);
  const current = useCurrentHeading(toc.keys);

  useEffect(() => {
    if (!tocOpen) return;
    const onKey = (e) => e.key === 'Escape' && onTocClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [tocOpen, onTocClose]);

  const goTo = (key) => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document.getElementById(anchorId(key))?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth' });
    onTocClose();
  };

  return (
    <>
      <header className="banner">
        <img src="/images/nazarene_logo_wide-white.png" alt="Church of the Nazarene" />
        <p>2023 Manual</p>
      </header>
      <div className="shell">
        <aside className="shell-sidebar" data-open={tocOpen || undefined}>
          {blocks && <Toc toc={toc} current={current} onGo={goTo} />}
        </aside>
        {tocOpen && <div className="shell-backdrop" onClick={onTocClose} />}
        <main className="shell-content" lang={LANG}>
          {error && <div style={styles.status}>Failed to load: {error.message}</div>}
          {!error && !blocks && <div style={styles.status}>Loading the Manual…</div>}
          {sheets.map((groups) => (
            <section key={groups[0].blocks[0].id} className="page manual" style={styles.sheet}>
              {groups.map((g) =>
                g.run === 'list' ? (
                  <ListRun key={g.blocks[0].id} blocks={g.blocks} />
                ) : g.run === 'table' ? (
                  <TableRun key={g.blocks[0].id} blocks={g.blocks} />
                ) : (
                  <Block key={g.blocks[0].id} block={g.blocks[0]} />
                )
              )}
            </section>
          ))}
        </main>
        {/* Reserved for tips (and, later, the English side-by-side). It always
            holds its column on wide screens, so filling it never moves the page. */}
        <aside className="shell-gutter" aria-label="Tips" />
      </div>
    </>
  );
}

// Sizes are written in print points: calc(N * var(--pt)) is "N pt" at the
// current scale. --pt (set on each sheet) is chosen so the print measure, 20p9
// (26p9 page less 3p margins = 249pt), fills the content column between 16px
// gutters, held between a readable minimum and a desktop maximum. Below the
// minimum, lines get shorter than print rather than type tinier.
//
// Where there is room the sheet is the 26p9 print page; its side margins are
// whatever is left around the measure, between 16px and the print 3p.
const MEASURE_PT = 249;
const PAGE_PT = 321;
const pt = (n) => `calc(${n} * var(--pt))`;

const styles = {
  sheet: {
    // 1pt between 1.84px (17px body) and 2.27px (21px body). cqi is the
    // .shell-content width, which, unlike vw, excludes the scrollbar.
    '--pt': `clamp(17px / 9.25, (100cqi - 32px) / ${MEASURE_PT}, 21px / 9.25)`,
    fontFamily: 'var(--font-reading)',
    lineHeight: 'var(--leading-body)',
    color: 'var(--text)',
    fontSize: pt(9.25),
    boxSizing: 'border-box',
    maxWidth: pt(PAGE_PT),
    margin: '0 auto',
    padding: `${pt(30)} clamp(16px, (100cqi - ${pt(MEASURE_PT)}) / 2, ${pt(36)}) ${pt(60)}`,
  },
  status: {
    padding: 48,
    textAlign: 'center',
    fontFamily: 'var(--font-reading)',
    color: 'var(--text-muted)',
  },
  partNumber: {
    marginTop: pt(36),
    textAlign: 'center',
    fontSize: pt(8.5),
    letterSpacing: '0.25em',
    textTransform: 'uppercase',
    color: 'var(--accent)',
  },
  partTitle: {
    textAlign: 'center',
    fontSize: pt(15),
    lineHeight: 18 / 15,
    fontWeight: 700,
    margin: `${pt(4)} 0 ${pt(9)}`,
  },
  partChapterList: {
    textAlign: 'center',
    fontSize: pt(8),
    color: 'var(--text-muted)',
    margin: `${pt(1)} 0`,
  },
  // Major divisions: bold 12/14, centered, 0p6 before / 0p3 after.
  heading1: {
    fontSize: pt(12),
    lineHeight: 14 / 12,
    fontWeight: 700,
    textAlign: 'center',
    margin: `${pt(6)} 0 ${pt(3)}`,
  },
  // Subdivisions: "Bold No. 2" 10/12 at weight 500, centered, 0p6 before / 0p3 after.
  subheading: {
    fontFamily: 'var(--font-division)',
    fontSize: pt(10),
    lineHeight: 12 / 10,
    fontWeight: 500,
    textAlign: 'center',
    margin: `${pt(6)} 0 ${pt(3)}`,
  },
  // Kept below the 0p6 heading space so collapsing margins don't swallow it.
  paragraph: {
    margin: `${pt(3)} 0`,
    textIndent: pt(9),
  },
    paraNum: {
    fontWeight: 600,
  },
  note: {
    margin: `${pt(3)} 0`,
    fontSize: pt(8.25),
    color: 'var(--text-muted)',
  },
  list: {
    listStyle: 'none',
    margin: `${pt(3)} 0`,
    paddingLeft: pt(18),
  },
  listItem: {
    margin: `${pt(2.5)} 0`,
  },
  marker: {
    fontWeight: 600,
  },
};
