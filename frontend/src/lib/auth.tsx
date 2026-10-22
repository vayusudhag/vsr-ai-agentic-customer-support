import { createContext, useContext, useState, type ReactNode } from "react";
import { api, session, type User } from "./api";

type AuthCtx = { user: User | null; login: (email: string, password: string) => Promise<User>; logout: () => void };
const Ctx = createContext<AuthCtx>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(session.user);
  const login = async (email: string, password: string) => {
    const r = await api<{ access_token: string; user: User }>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
    session.save(r.access_token, r.user);
    setUser(r.user);
    return r.user;
  };
  const logout = () => { session.clear(); setUser(null); };
  return <Ctx.Provider value={{ user, login, logout }}>{children}</Ctx.Provider>;
}
export const useAuth = () => useContext(Ctx);
