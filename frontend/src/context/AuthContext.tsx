import { createContext, useContext, useState, type ReactNode } from 'react';
import { api } from '../api/client';

interface User {
  user_id: string;
  name: string;
  global_role: string;
  project_roles: Record<string, string> | null;
}

interface AuthCtx {
  user: User | null;
  login: (userId: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthCtx>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  const login = async (userId: string) => {
    const u = await api.login(userId);
    setUser(u);
  };

  const logout = () => setUser(null);

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
