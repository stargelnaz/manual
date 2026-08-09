import { useEffect, useState } from 'react';
import LexiconReview from './pages/LexiconReview';
import ManualReader from './pages/ManualReader';

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
    borderBottom: '1px solid #e2e2e2',
    background: '#fafafa',
    fontFamily: 'system-ui, sans-serif',
    fontSize: 14,
  },
  link: {
    color: '#333',
    textDecoration: 'none',
  },
};

export default App;
