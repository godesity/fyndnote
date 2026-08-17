import { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function LoginView() {
  const { login } = useAuth();
  const [userId, setUserId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setError('');
      setLoading(true);
      await login(userId);
      const hash = window.location.hash;
      window.location.hash = (hash && hash !== '#') ? hash : '#/projects';
    } catch {
      setError('Unknown user ID');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-sunset-50 via-white to-coral-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm animate-fade-in">
        <div className="p-[2px] rounded-2xl bg-gradient-to-r from-sunset-500 via-coral-500 to-violet-500 shadow-lg shadow-sunset-200/50">
          <div className="bg-white rounded-[calc(1rem-2px)] p-8">
            <div className="flex flex-col items-center mb-6">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-sunset-500 to-coral-500 flex items-center justify-center text-white text-lg font-bold mb-3 shadow-sm">
                L
              </div>
              <h1 className="text-xl font-bold text-[var(--color-text-heading)]">
                Label Tool
              </h1>
              <p className="text-sm text-[var(--color-text-muted)] mt-1">
                Sign in to start labeling
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <input
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="Enter your user ID"
                autoFocus
                className="w-full px-3 py-2.5 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400 focus:ring-3 focus:ring-sunset-100 transition-all"
              />
              <button
                type="submit"
                disabled={loading || !userId.trim()}
                className="w-full py-2.5 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white font-medium text-sm hover:from-sunset-600 hover:to-coral-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm"
              >
                {loading ? 'Signing in...' : 'Sign In'}
              </button>
              {error && (
                <p className="text-red-500 text-sm text-center">{error}</p>
              )}
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
