import { useEffect, useMemo, useState } from 'react';
import lexiconRaw from '../data/lexicon-base.md?raw';

const STORAGE_KEY = 'lexicon-review-v2';

function parseLexicon(raw) {
  const lines = raw.split('\n').filter((l) => l.trim() !== '');
  // skip header (line 0) and separator (line 1)
  const dataLines = lines.slice(2);

  return dataLines.map((line, index) => {
    const cells = line
      .split('|')
      .map((c) => c.trim())
      .filter((_, i, arr) => !(i === 0 && arr[i] === '') && !(i === arr.length - 1 && arr[i] === ''));

    const [phrase = '', pos = '', refs = '', headword = '', inflections = ''] = cells;

    return {
      id: index,
      phrase,
      pos,
      refs,
      headword,
      inflections,
    };
  });
}

// headword is the unique identifier: group every row by it so the review
// unit becomes "this headword and every phrase tied to it".
function groupByHeadword(entries) {
  const order = [];
  const byHeadword = new Map();

  for (const entry of entries) {
    const key = entry.headword;
    if (!byHeadword.has(key)) {
      byHeadword.set(key, []);
      order.push(key);
    }
    byHeadword.get(key).push(entry);
  }

  return order.map((headword) => ({ headword, rows: byHeadword.get(headword) }));
}

// Phrases tied to a headword are listed by name; when the same phrase text
// appears more than once in the group (e.g. "associate" as noun and verb),
// disambiguate each occurrence with its pos in parentheses.
function phraseLabels(rows) {
  const counts = {};
  for (const r of rows) counts[r.phrase] = (counts[r.phrase] || 0) + 1;

  return rows.map((r) => ({
    id: r.id,
    label: counts[r.phrase] > 1 ? `${r.phrase} (${r.pos})` : r.phrase,
  }));
}

function loadReviewState() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return {};
    return JSON.parse(stored);
  } catch {
    return {};
  }
}

function saveReviewState(state) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

const emptyStatus = { status: 'unreviewed', note: '', edits: null };

// Builds the editable draft for a headword group: the headword itself, plus
// each tied row's editable fields, seeded from any previously saved edits.
function buildDraft(group, savedEdits) {
  const rows = {};
  for (const r of group.rows) {
    const saved = savedEdits?.rows?.[r.id];
    rows[r.id] = saved || { phrase: r.phrase, pos: r.pos, refs: r.refs, inflections: r.inflections };
  }
  return { headword: savedEdits?.headword ?? group.headword, rows };
}

export default function LexiconReview() {
  const entries = useMemo(() => parseLexicon(lexiconRaw), []);
  const groups = useMemo(() => groupByHeadword(entries), [entries]);
  const [reviewState, setReviewState] = useState(() => loadReviewState());
  const [mode, setMode] = useState('review'); // 'review' | 'flagged'
  const [noteDraft, setNoteDraft] = useState('');
  const [editDraft, setEditDraft] = useState(null);
  const [flaggedFocusKey, setFlaggedFocusKey] = useState(null);

  useEffect(() => {
    saveReviewState(reviewState);
  }, [reviewState]);

  const getStatus = (headword) => reviewState[headword] || emptyStatus;

  const unreviewed = groups.filter((g) => getStatus(g.headword).status === 'unreviewed');
  const flagged = groups.filter((g) => getStatus(g.headword).status === 'review');
  const okCount = groups.filter((g) => getStatus(g.headword).status === 'ok').length;

  const current = mode === 'review' ? unreviewed[0] : null;

  useEffect(() => {
    setNoteDraft(current ? getStatus(current.headword).note || '' : '');
    setEditDraft(current ? buildDraft(current, getStatus(current.headword).edits) : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.headword]);

  // Autosave the in-progress edit/note a moment after typing stops, so nothing
  // is lost if the user switches tabs or reloads before clicking OK/Review.
  useEffect(() => {
    if (!current || !editDraft) return;
    const timer = setTimeout(() => saveEdits(current.headword, editDraft), 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editDraft, current?.headword]);

  useEffect(() => {
    if (!current) return;
    const timer = setTimeout(() => saveNote(current.headword, noteDraft), 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [noteDraft, current?.headword]);

  const markOk = (headword) => {
    setReviewState((prev) => ({
      ...prev,
      [headword]: { status: 'ok', note: '', edits: prev[headword]?.edits || null },
    }));
  };

  const markReview = (headword, note) => {
    setReviewState((prev) => ({
      ...prev,
      [headword]: { status: 'review', note, edits: prev[headword]?.edits || null },
    }));
  };

  const saveEdits = (headword, edits) => {
    setReviewState((prev) => ({
      ...prev,
      [headword]: { ...(prev[headword] || emptyStatus), edits },
    }));
  };

  const saveNote = (headword, note) => {
    setReviewState((prev) => ({
      ...prev,
      [headword]: { ...(prev[headword] || emptyStatus), note },
    }));
  };

  const resolveFlagged = (headword, edits) => {
    setReviewState((prev) => ({
      ...prev,
      [headword]: { status: 'ok', note: '', edits },
    }));
    setFlaggedFocusKey(null);
  };

  const reopenFlagged = (headword) => {
    setReviewState((prev) => ({
      ...prev,
      [headword]: { ...(prev[headword] || emptyStatus), status: 'unreviewed' },
    }));
    setMode('review');
  };

  const [confirmingReset, setConfirmingReset] = useState(false);

  const resetAll = () => {
    setReviewState({});
    localStorage.removeItem(STORAGE_KEY);
    setConfirmingReset(false);
  };

  const exportMarkdown = () => {
    const header = '| phrase | pos | refs | headword | inflections |\n' + '| --- | --- | --- | --- | --- |\n';

    const body = groups
      .flatMap((g) => {
        const edits = getStatus(g.headword).edits;
        return g.rows.map((r) => {
          const rowEdit = edits?.rows?.[r.id];
          const headword = edits?.headword ?? g.headword;
          const row = rowEdit ? { ...r, ...rowEdit, headword } : { ...r, headword };
          return `| ${row.phrase} | ${row.pos} | ${row.refs} | ${row.headword} | ${row.inflections} |`;
        });
      })
      .join('\n');

    const blob = new Blob([header + body + '\n'], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'lexicon-base.md';
    a.click();
    URL.revokeObjectURL(url);
  };

  const progressTotal = groups.length;
  const progressDone = progressTotal - unreviewed.length;

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <h1 style={styles.h1}>Lexicon Review</h1>
        <div style={styles.tabs}>
          <button
            style={mode === 'review' ? styles.tabActive : styles.tab}
            onClick={() => setMode('review')}
          >
            Review ({unreviewed.length} left)
          </button>
          <button
            style={mode === 'flagged' ? styles.tabActive : styles.tab}
            onClick={() => setMode('flagged')}
          >
            Flagged ({flagged.length})
          </button>
        </div>
      </header>

      <div style={styles.progressBarOuter}>
        <div
          style={{
            ...styles.progressBarInner,
            width: `${progressTotal ? (progressDone / progressTotal) * 100 : 0}%`,
          }}
        />
      </div>
      <div style={styles.progressLabel}>
        {progressDone} / {progressTotal} headwords reviewed &middot; {okCount} OK &middot; {flagged.length}{' '}
        flagged
      </div>

      {mode === 'review' && (
        <div style={styles.mainArea}>
          {current ? (
            <HeadwordCard
              group={current}
              draft={editDraft}
              onChange={setEditDraft}
              noteDraft={noteDraft}
              onNoteChange={setNoteDraft}
              onOk={() => {
                saveEdits(current.headword, editDraft);
                markOk(current.headword);
              }}
              onFlag={() => {
                saveEdits(current.headword, editDraft);
                markReview(current.headword, noteDraft);
              }}
            />
          ) : (
            <div style={styles.doneBox}>
              <h2>All headwords reviewed 🎉</h2>
              <p>
                {flagged.length > 0
                  ? `${flagged.length} headwords were flagged for changes. Switch to the "Flagged" tab to work through them.`
                  : 'Nothing was flagged. Everything is marked OK.'}
              </p>
              {flagged.length > 0 && (
                <button style={styles.primaryButton} onClick={() => setMode('flagged')}>
                  Go to Flagged List
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {mode === 'flagged' && (
        <div style={styles.mainArea}>
          {flagged.length === 0 ? (
            <div style={styles.doneBox}>
              <h2>No flagged headwords</h2>
              <p>Nothing needs changing right now.</p>
            </div>
          ) : (
            <div style={styles.flaggedList}>
              {flagged.map((g) => (
                <FlaggedGroupRow
                  key={g.headword}
                  group={g}
                  status={getStatus(g.headword)}
                  isOpen={flaggedFocusKey === g.headword}
                  onOpen={() => setFlaggedFocusKey(flaggedFocusKey === g.headword ? null : g.headword)}
                  onResolve={(edits) => resolveFlagged(g.headword, edits)}
                  onReopen={() => reopenFlagged(g.headword)}
                  onAutosave={(edits) => saveEdits(g.headword, edits)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      <footer style={styles.footer}>
        <button style={styles.secondaryButton} onClick={exportMarkdown}>
          Export edited lexicon-base.md
        </button>
        {confirmingReset ? (
          <>
            <span style={styles.confirmText}>Reset all progress?</span>
            <button style={styles.dangerButton} onClick={resetAll}>
              Yes, reset
            </button>
            <button style={styles.secondaryButton} onClick={() => setConfirmingReset(false)}>
              Cancel
            </button>
          </>
        ) : (
          <button style={styles.dangerButton} onClick={() => setConfirmingReset(true)}>
            Reset all progress
          </button>
        )}
      </footer>
    </div>
  );
}

// Editable fields for one phrase tied to the headword (phrase/pos/refs/inflections).
function PhraseFields({ label, value, onChange }) {
  const field = (key, fieldLabel) => (
    <label style={styles.fieldLabel}>
      <span style={styles.fieldLabelText}>{fieldLabel}</span>
      <input
        style={styles.fieldInput}
        value={value[key]}
        onChange={(ev) => onChange({ ...value, [key]: ev.target.value })}
      />
    </label>
  );

  return (
    <div style={styles.phraseBlock}>
      <div style={styles.phraseBlockLabel}>{label}</div>
      {field('phrase', 'phrase')}
      {field('pos', 'pos')}
      {field('refs', 'refs')}
      <label style={styles.fieldLabel}>
        <span style={styles.fieldLabelText}>inflections</span>
        <textarea
          style={styles.fieldTextarea}
          rows={2}
          value={value.inflections}
          onChange={(ev) => onChange({ ...value, inflections: ev.target.value })}
        />
      </label>
    </div>
  );
}

function HeadwordCard({ group, draft, onChange, noteDraft, onNoteChange, onOk, onFlag }) {
  // draft can briefly lag one render behind `group` (its effect fires after
  // the group list changes), so guard against a mismatched draft rather than
  // reading rows that don't exist for this group yet.
  if (!draft || !group.rows.every((r) => draft.rows[r.id])) return null;

  const labels = phraseLabels(group.rows);

  return (
    <div style={styles.card}>
      <label style={styles.titleLabel}>
        <span style={styles.fieldLabelText}>headword</span>
        <input
          style={styles.titleInput}
          value={draft.headword}
          onChange={(ev) => onChange({ ...draft, headword: ev.target.value })}
        />
      </label>

      <div style={styles.phraseList}>
        {labels.map(({ id, label }) => (
          <PhraseFields
            key={id}
            label={label}
            value={draft.rows[id]}
            onChange={(rowValue) =>
              onChange({ ...draft, rows: { ...draft.rows, [id]: rowValue } })
            }
          />
        ))}
      </div>

      <label style={styles.fieldLabel}>
        <span style={styles.fieldLabelText}>note (optional, for flagged items)</span>
        <input
          style={styles.fieldInput}
          placeholder="What needs to change?"
          value={noteDraft}
          onChange={(ev) => onNoteChange(ev.target.value)}
        />
      </label>

      <div style={styles.cardActions}>
        <button style={styles.okButton} onClick={onOk}>
          OK
        </button>
        <button style={styles.flagButton} onClick={onFlag}>
          Review
        </button>
      </div>
    </div>
  );
}

function FlaggedGroupRow({ group, status, isOpen, onOpen, onResolve, onReopen, onAutosave }) {
  const [draft, setDraft] = useState(() => buildDraft(group, status.edits));
  const labels = phraseLabels(group.rows);

  useEffect(() => {
    setDraft(buildDraft(group, status.edits));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  // Autosave a moment after typing stops, so an edit isn't lost if the row
  // is collapsed or another headword is opened before "Save & Resolve".
  useEffect(() => {
    if (!isOpen) return;
    const timer = setTimeout(() => onAutosave(draft), 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, isOpen]);

  return (
    <div style={styles.flaggedRow}>
      <div style={styles.flaggedSummary} onClick={onOpen}>
        <div style={styles.flaggedHeadword}>{group.headword}</div>
        <div style={styles.flaggedMeta}>{labels.map((l) => l.label).join(', ')}</div>
        {status.note && <div style={styles.flaggedNote}>note: {status.note}</div>}
      </div>

      {isOpen && (
        <div style={styles.flaggedEditArea}>
          <label style={styles.fieldLabel}>
            <span style={styles.fieldLabelText}>headword</span>
            <input
              style={styles.fieldInput}
              value={draft.headword}
              onChange={(ev) => setDraft({ ...draft, headword: ev.target.value })}
            />
          </label>

          <div style={styles.phraseList}>
            {labels.map(({ id, label }) => (
              <PhraseFields
                key={id}
                label={label}
                value={draft.rows[id]}
                onChange={(rowValue) => setDraft({ ...draft, rows: { ...draft.rows, [id]: rowValue } })}
              />
            ))}
          </div>

          <div style={styles.cardActions}>
            <button style={styles.okButton} onClick={() => onResolve(draft)}>
              Save &amp; Resolve
            </button>
            <button style={styles.secondaryButton} onClick={onReopen}>
              Send back to Review queue
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  page: {
    maxWidth: 720,
    margin: '0 auto',
    padding: '24px 16px 80px',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    color: '#1a1a1a',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  h1: { fontSize: 22, margin: 0 },
  tabs: { display: 'flex', gap: 8 },
  tab: {
    padding: '6px 12px',
    borderRadius: 6,
    border: '1px solid #ccc',
    background: '#fff',
    cursor: 'pointer',
    fontSize: 13,
  },
  tabActive: {
    padding: '6px 12px',
    borderRadius: 6,
    border: '1px solid #333',
    background: '#333',
    color: '#fff',
    cursor: 'pointer',
    fontSize: 13,
  },
  progressBarOuter: {
    height: 8,
    background: '#eee',
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 4,
  },
  progressBarInner: {
    height: '100%',
    background: '#2e7d32',
    transition: 'width 0.2s ease',
  },
  progressLabel: { fontSize: 12, color: '#666', marginBottom: 20 },
  mainArea: { minHeight: 300 },
  card: {
    border: '1px solid #ddd',
    borderRadius: 10,
    padding: 20,
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    background: '#fafafa',
  },
  titleLabel: { display: 'flex', flexDirection: 'column', gap: 4 },
  titleInput: {
    padding: '10px 12px',
    borderRadius: 8,
    border: '1px solid #bbb',
    fontSize: 24,
    fontWeight: 700,
    background: '#fff',
  },
  phraseList: { display: 'flex', flexDirection: 'column', gap: 12 },
  phraseBlock: {
    border: '1px solid #e2e2e2',
    borderRadius: 8,
    padding: 12,
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    background: '#fff',
  },
  phraseBlockLabel: { fontSize: 13, fontWeight: 600, color: '#444' },
  fieldLabel: { display: 'flex', flexDirection: 'column', gap: 4 },
  fieldLabelText: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5, color: '#888' },
  fieldInput: {
    padding: '8px 10px',
    borderRadius: 6,
    border: '1px solid #ccc',
    fontSize: 14,
  },
  fieldTextarea: {
    padding: '8px 10px',
    borderRadius: 6,
    border: '1px solid #ccc',
    fontSize: 14,
    fontFamily: 'inherit',
    resize: 'vertical',
  },
  cardActions: { display: 'flex', gap: 10, marginTop: 8 },
  okButton: {
    flex: 1,
    padding: '10px 16px',
    borderRadius: 6,
    border: 'none',
    background: '#2e7d32',
    color: '#fff',
    fontSize: 14,
    cursor: 'pointer',
  },
  flagButton: {
    flex: 1,
    padding: '10px 16px',
    borderRadius: 6,
    border: 'none',
    background: '#c62828',
    color: '#fff',
    fontSize: 14,
    cursor: 'pointer',
  },
  doneBox: {
    textAlign: 'center',
    padding: '60px 20px',
    border: '1px dashed #ccc',
    borderRadius: 10,
  },
  primaryButton: {
    padding: '10px 20px',
    borderRadius: 6,
    border: 'none',
    background: '#333',
    color: '#fff',
    fontSize: 14,
    cursor: 'pointer',
    marginTop: 12,
  },
  secondaryButton: {
    padding: '8px 14px',
    borderRadius: 6,
    border: '1px solid #ccc',
    background: '#fff',
    fontSize: 13,
    cursor: 'pointer',
  },
  confirmText: { fontSize: 13, color: '#c62828', alignSelf: 'center' },
  dangerButton: {
    padding: '8px 14px',
    borderRadius: 6,
    border: '1px solid #c62828',
    background: '#fff',
    color: '#c62828',
    fontSize: 13,
    cursor: 'pointer',
  },
  flaggedList: { display: 'flex', flexDirection: 'column', gap: 10 },
  flaggedRow: {
    border: '1px solid #ddd',
    borderRadius: 8,
    overflow: 'hidden',
  },
  flaggedSummary: { padding: '12px 16px', cursor: 'pointer', background: '#fff8f8' },
  flaggedHeadword: { fontWeight: 700, fontSize: 17 },
  flaggedMeta: { fontSize: 12, color: '#888', marginTop: 2 },
  flaggedNote: { fontSize: 12, color: '#c62828', marginTop: 4, fontStyle: 'italic' },
  flaggedEditArea: {
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    borderTop: '1px solid #eee',
  },
  footer: {
    marginTop: 40,
    display: 'flex',
    gap: 10,
    justifyContent: 'center',
  },
};
