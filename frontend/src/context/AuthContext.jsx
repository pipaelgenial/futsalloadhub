import { createContext, useContext, useEffect, useState } from "react";
import { http } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = anon, object = user
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const { data } = await http.get("/auth/me");
        if (active) setUser(data);
      } catch {
        if (active) setUser(false);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, []);

  async function login(email, password) {
    const { data } = await http.post("/auth/login", { email, password });
    if (data.token) localStorage.setItem("fld_token", data.token);
    setUser(data);
    return data;
  }

  async function register(email, password, name) {
    const { data } = await http.post("/auth/register", { email, password, name });
    if (data.token) localStorage.setItem("fld_token", data.token);
    setUser(data);
    return data;
  }

  async function logout() {
    try { await http.post("/auth/logout"); } catch {}
    localStorage.removeItem("fld_token");
    setUser(false);
  }

  return (
    <AuthCtx.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
