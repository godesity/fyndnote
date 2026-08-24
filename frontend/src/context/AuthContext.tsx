import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, type User as ApiUser } from '../api/client';

export interface User extends ApiUser {}

interface AuthCtx {
  user: User | null;
  token: string | null;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  handleCallback: () => Promise<void>;
}

const AuthContext = createContext<AuthCtx>(null!);

// Session state lives in localStorage so a refresh keeps the JWT.
const TOKEN_KEY = 'fyndnot_sso_token';
const USER_KEY = 'fyndnot_sso_user';

function readSession(): { token: string | null; user: User | null } {
  const token = localStorage.getItem(TOKEN_KEY);
  const raw = localStorage.getItem(USER_KEY);
  let user: User | null = null;
  if (raw) {
    try {
      user = JSON.parse(raw) as User;
    } catch {
      user = null;
    }
  }
  return { token, user };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const session = readSession();
  const [user, setUser] = useState<User | null>(session.user);
  const [token, setToken] = useState<string | null>(session.token);

  // On mount, if we have a token but no cached user, resolve it via /sso/me.
  useEffect(() => {
    if (token && !user) {
      api.me(token).then((res) => {
        setUser(res.user);
        localStorage.setItem(USER_KEY, JSON.stringify(res.user));
      }).catch(() => {
        clearSession();
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function clearSession() {
    setUser(null);
    setToken(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  const login = async () => {
    // Full browser navigation to the backend /sso/login. The backend sets a
    // signed session cookie (CSRF state), then redirects to Keycloak, which
    // redirects back to /callback?code=...&state=... in this same tab.
    window.location.href = `${api.base}/sso/login`;
  };

  // Called from the /callback route after Keycloak returns ?code=...&state=...
const handleCallback = async () => {
    // The backend redirects here (top-level nav) with the tokens in the query
    // string after completing the OAuth exchange with Keycloak.
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    const user_id = params.get('user_id');
    const name = params.get('name');
    const global_role = params.get('global_role');
    if (!token || !user_id) {
      clearSession();
      return;
    }
    const user: User = { user_id, name: name || '', global_role: global_role || 'annotator', project_roles: null };
    setUser(user);
    setToken(token);
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  };

  const logout = async () => {
    clearSession();
    try {
      // Backend clears the session cookie and redirects to Keycloak logout.
      const res = await fetch(`${api.base}/sso/logout`, { credentials: 'include' });
      if (res.ok && res.redirected) {
        window.location.href = res.url;
        return;
      }
    } catch {
      // ignore
    }
    window.location.href = '/';
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, handleCallback }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
