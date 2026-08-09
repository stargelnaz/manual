import { useEffect, useMemo, useState } from 'react';
import { supabase } from '../lib/supabase';

const PAGE = 1000; // PostgREST caps a single request at 1000 rows

async function fetchAllBlocks() {
  const rows = [];
  for (let from = 0; ; from += PAGE) {
    const { data, error } = await supabase
      .from('manual_reading_order')
      .select('*')
      .order('doc_order')
      .order('ordinal')
      .range(from, from + PAGE - 1);
    if (error) throw error;
    rows.push(...data);
    if (data.length < PAGE) return rows;
  }
}

// Bodies contain only <em>, <b>, <sc> — enforced by the build gates — and every
// tag balances within its block, so a single stack is enough to parse them.
const TAG_RE = /<(\/?)(em|b|sc)>/g;

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
      const node = { tag: m[2], children: [] };
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
      return (
        <span key={key} style={{ fontVariant: 'small-caps' }}>
          {toReact(c)}
        </span>
      );
    });

  return toReact(root);
}

function Block({ block }) {
  const body = renderInline(block.body, block.id);

  switch (block.kind) {
    case 'part-number':
      return <div style={styles.partNumber}>{body}</div>;
    case 'part-title':
      return <div style={styles.partTitle}>{body}</div>;
    case 'part-chapter-list':
      return <div style={styles.partChapterList}>{body}</div>;
    case 'heading-1':
      return <h2 style={styles.heading1}>{body}</h2>;
    case 'subheading':
      return <h3 style={styles.subheading}>{body}</h3>;
    case 'note':
    case 'bible-reference':
      return <p style={styles.note}>{body}</p>;
    case 'lead':
      return (
        <p style={styles.paragraph}>
          {block.number_visible && (
            <span style={styles.paraNum}>{block.number} </span>
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

function groupBlocks(blocks) {
  const groups = [];
  for (const b of blocks) {
    const isListKind = b.kind === 'subpoint' || b.kind === 'list-item';
    const last = groups[groups.length - 1];
    if (isListKind && last?.list) {
      last.blocks.push(b);
    } else if (isListKind) {
      groups.push({ list: true, blocks: [b] });
    } else {
      groups.push({ list: false, blocks: [b] });
    }
  }
  return groups;
}

export default function ManualReader() {
  const [blocks, setBlocks] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAllBlocks().then(setBlocks, setError);
  }, []);

  const groups = useMemo(() => (blocks ? groupBlocks(blocks) : []), [blocks]);

  if (error) {
    return <div style={styles.status}>Failed to load: {error.message}</div>;
  }
  if (!blocks) {
    return <div style={styles.status}>Loading the Manual…</div>;
  }

  return (
    <div style={styles.page}>
      <main style={styles.main}>
        {groups.map((g) =>
          g.list ? (
            <ListRun key={g.blocks[0].id} blocks={g.blocks} />
          ) : (
            <Block key={g.blocks[0].id} block={g.blocks[0]} />
          )
        )}
      </main>
    </div>
  );
}

const styles = {
  page: {
    fontFamily: 'Georgia, "Times New Roman", serif',
    lineHeight: 1.6,
    color: '#1a1a1a',
    background: '#fff',
    minHeight: '100vh',
  },
  main: {
    maxWidth: 680,
    margin: '0 auto',
    padding: '48px 24px 96px',
  },
  status: {
    padding: 48,
    textAlign: 'center',
    fontFamily: 'Georgia, serif',
    color: '#555',
  },
  partNumber: {
    marginTop: 72,
    textAlign: 'center',
    fontSize: 15,
    letterSpacing: '0.25em',
    textTransform: 'uppercase',
    color: '#666',
  },
  partTitle: {
    textAlign: 'center',
    fontSize: 28,
    fontWeight: 700,
    margin: '8px 0 16px',
  },
  partChapterList: {
    textAlign: 'center',
    fontSize: 14,
    color: '#666',
    margin: '2px 0',
  },
  heading1: {
    marginTop: 56,
    fontSize: 21,
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
  },
  subheading: {
    marginTop: 36,
    fontSize: 17,
    fontStyle: 'italic',
    fontWeight: 600,
  },
  paragraph: {
    margin: '12px 0',
    textAlign: 'justify',
  },
  paraNum: {
    fontWeight: 700,
  },
  note: {
    margin: '10px 0',
    fontSize: 14.5,
    color: '#444',
  },
  list: {
    listStyle: 'none',
    margin: '8px 0',
    paddingLeft: 36,
  },
  listItem: {
    margin: '6px 0',
  },
  marker: {
    fontWeight: 600,
  },
};
