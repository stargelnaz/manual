import { useEffect, useState } from 'react';
import LexiconReview from './pages/LexiconReview';
import ManualReader from './pages/ManualReader';
import Login from './pages/Login';

const USER_KEY = 'manual.testUser';

// Placeholder session: the chosen test user, remembered across reloads.
function useTestUser() {
  const [user, setUser] = useState(() => {
    try {
      return localStorage.getItem(USER_KEY);
    } catch {
      return null;
    }
  });
  const update = (name) => {
    try {
      if (name) localStorage.setItem(USER_KEY, name);
      else localStorage.removeItem(USER_KEY);
    } catch {
      // Storage unavailable; the session just won't survive a reload.
    }
    setUser(name);
  };
  return [user, update];
}

// Hash routing: #/lexicon for the review tool, anything else is the reader.
// Deliberately no router dependency for a two-page app.
function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return hash;
}

function App() {
  const hash = useHashRoute();
  const [user, setUser] = useTestUser();
  if (!user) return <Login onLogin={setUser} />;

  const page = hash === '#/lexicon' ? <LexiconReview /> : <ManualReader />;

  return (
    <>
      <nav style={navStyles.bar}>
        <a href="#/" style={navStyles.link}>
          Manual
        </a>
        <a href="#/lexicon" style={navStyles.link}>
          Lexicon Review
        </a>
        <span style={navStyles.user}>
          {user}
          <button style={navStyles.signOut} onClick={() => setUser(null)}>
            Sign out
          </button>
        </span>
      </nav>
      {page}
    </>
  );
}

const navStyles = {
  bar: {
    display: 'flex',
    gap: 16,
    padding: '10px 24px',
    alignItems: 'center',
    borderBottom: '1px solid var(--border)',
    background: 'rgba(0, 0, 0, 0.25)',
    fontFamily: 'var(--font-ui)',
    fontSize: 14,
  },
  link: {
    color: 'var(--text)',
    textDecoration: 'none',
  },
  user: {
    marginLeft: 'auto',
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    color: 'var(--text-muted)',
  },
  signOut: {
    padding: '4px 10px',
    borderRadius: 6,
    border: '1px solid var(--border-strong)',
    background: 'transparent',
    fontSize: 13,
    cursor: 'pointer',
  },
};

export default App;
