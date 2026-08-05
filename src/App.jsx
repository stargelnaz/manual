import { supabase } from './lib/supabase';

function App() {
  console.log('Supabase URL:', import.meta.env.VITE_SUPABASE_URL);
  console.log('Supabase Key exists:', !!import.meta.env.VITE_SUPABASE_ANON_KEY);

  // Test connection (optional)
  const testConnection = async () => {
    const { data, error } = await supabase.from('your_table_name').select('*').limit(1);
    console.log('Test result:', data, error);
  };

  return (
    <div>
      <h1>Hello World</h1>
      <button onClick={testConnection}>Test Supabase</button>
    </div>
  );
}

export default App;
