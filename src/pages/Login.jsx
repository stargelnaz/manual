// Placeholder sign-in: pick a test user. Replace with real auth later.
const TEST_USERS = ['Scott', 'Jeff', 'Gary'];

export default function Login({ onLogin }) {
  return (
    <div style={styles.page}>
      <img
        src="/images/nazarene_logo_wide-white.png"
        alt="Church of the Nazarene"
        style={styles.logo}
      />
      <div style={styles.boxes}>
        {TEST_USERS.map((name) => (
          <button key={name} style={styles.box} onClick={() => onLogin(name)}>
            Test as {name}
          </button>
        ))}
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 56,
    padding: '48px 16px',
    boxSizing: 'border-box',
    fontFamily: 'var(--font-reading)',
  },
  logo: {
    width: 'min(560px, 90vw)',
    height: 'auto',
  },
  boxes: {
    display: 'flex',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 20,
  },
  box: {
    width: 180,
    padding: '28px 16px',
    border: '1px solid var(--border-strong)',
    borderRadius: 10,
    background: 'var(--panel-raised)',
    color: 'var(--text)',
    fontSize: 17,
    letterSpacing: '0.03em',
    cursor: 'pointer',
  },
};
