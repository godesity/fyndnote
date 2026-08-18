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
              <div className="w-14 h-14 rounded-xl bg-white flex items-center justify-center mb-3 shadow-sm">
                <svg width="40" height="40" viewBox="0 0 140 140" fill="none">
                  <ellipse cx="70" cy="116" rx="44" ry="8" fill="#fbbf24" opacity="0.12"/>
                  <polygon points="80,95 110,85 115,65 95,58 72,68 70,88" fill="#ea580c" stroke="#c2410c" stroke-width="2" opacity="0.25"/>
                  <polygon points="95,58 104,64 92,68" fill="#fdba74" opacity="0.15"/>
                  <polygon points="35,100 25,80 40,65 65,72 60,100" fill="#fed7aa" stroke="#fdba74" stroke-width="2"/>
                  <polygon points="40,65 50,68 42,78" fill="#ffedd5" opacity="0.5"/>
                  <polygon points="75,105 100,100 110,78 95,68 72,78" fill="#fed7aa" stroke="#fdba74" stroke-width="2"/>
                  <polygon points="95,68 102,75 90,77" fill="#ffedd5" opacity="0.5"/>
                  <polygon points="50,82 65,70 85,72 88,90 55,95" fill="#fef3c7" stroke="#fde68a" stroke-width="2"/>
                  <polygon points="65,70 72,72 68,82" fill="#fffbeb" opacity="0.5"/>
                  <polygon points="55,55 62,38 72,42 68,60" fill="#f97316" stroke="#ea580c" stroke-width="1.5"/>
                  <polygon points="55,55 68,60 63,52" fill="#fdba74" opacity="0.5"/>
                  <polygon points="62,38 66,40 64,50" fill="#fdba74" opacity="0.4"/>
                  <polygon points="75,50 82,35 90,45 85,58" fill="#a855f7" stroke="#9333ea" stroke-width="1.5"/>
                  <polygon points="75,50 85,58 80,51" fill="#d8b4fe" opacity="0.5"/>
                  <polygon points="82,35 86,38 83,48" fill="#d8b4fe" opacity="0.4"/>
                  <polygon points="45,62 50,52 55,62 50,68" fill="#fbbf24" stroke="#f59e0b" stroke-width="1.5"/>
                  <polygon points="45,62 50,68 48,63" fill="#fde68a" opacity="0.5"/>
                  <path d="M92 28l1.5 4 4 1.5-4 1.5-1.5 4-1.5-4-4-1.5 4-1.5 1.5-4z" fill="#fbbf24"/>
                </svg>
              </div>
              <h1 className="text-xl font-bold text-[var(--color-text-heading)]">
                fyndnot
              </h1>
              <p className="text-sm text-[var(--color-text-muted)] mt-1">
                Discover. Annotate. Export.
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
