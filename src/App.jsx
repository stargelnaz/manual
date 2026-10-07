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
  const [tocOpen, setTocOpen] = useState(false);
  if (!user) return <Login onLogin={setUser} />;

  const isReader = hash !== '#/lexicon';
  const page = isReader ? (
    <ManualReader tocOpen={tocOpen} onTocClose={() => setTocOpen(false)} />
  ) : (
    <LexiconReview />
  );

  return (
    <>
      <nav className="navbar">
        {isReader && (
          <button
            className="btn btn-sm btn-ghost navbar-toc"
            aria-expanded={tocOpen}
            onClick={() => setTocOpen(!tocOpen)}
          >
            Contents
          </button>
        )}
        <a href="#/" onClick={() => setTocOpen(false)}>
          Manual
        </a>
        <a href="#/lexicon" onClick={() => setTocOpen(false)}>
          Lexicon Review
        </a>
        <span className="navbar-user">
          {user}
          <button className="btn btn-sm" onClick={() => setUser(null)}>
            Sign out
          </button>
        </span>
      </nav>
      {page}
    </>
  );
}

export default App;
