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
      <p style={styles.subtitle}>2023 Manual</p>
      <div style={styles.boxes}>
        {TEST_USERS.map((name) => (
          <button key={name} className="btn btn-lg" style={styles.box} onClick={() => onLogin(name)}>
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
    gap: 20,
    padding: '48px 16px',
    boxSizing: 'border-box',
    fontFamily: 'var(--font-reading)',
  },
  logo: {
    width: 'min(560px, 90vw)',
    height: 'auto',
  },
  subtitle: {
    margin: '0 0 36px',
    color: 'var(--text-muted)',
    fontSize: 22,
    letterSpacing: '0.12em',
  },
  boxes: {
    display: 'flex',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 20,
  },
  // Large tiles: btn-lg, made taller and fixed-width.
  box: {
    width: 180,
    padding: '28px 16px',
    fontFamily: 'var(--font-reading)',
    fontSize: 17,
  },
};
