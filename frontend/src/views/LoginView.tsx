import { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function LoginView() {
  const { login } = useAuth();
  const [userId, setUserId] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setError('');
      await login(userId);
      const hash = window.location.hash;
      window.location.hash = (hash && hash !== '#') ? hash : '#/projects';
    } catch {
      setError('Unknown user ID');
    }
  };

  return (
    <div style={{ padding: 40, maxWidth: 400, margin: '0 auto' }}>
      <h1>Labeling Tool</h1>
      <form onSubmit={handleSubmit}>
        <input
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="Enter your user ID"
          style={{ display: 'block', width: '100%', padding: 8, marginBottom: 8 }}
        />
        <button type="submit" style={{ padding: '8px 16px' }}>Login</button>
        {error && <p style={{ color: 'red' }}>{error}</p>}
      </form>
    </div>
  );
}
