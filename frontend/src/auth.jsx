import { createContext, useContext, useEffect, useState } from "react";
import { api, clearSession, readStoredUser, saveSession } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readStoredUser);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("askdb_access");
    if (!token) {
      setReady(true);
      return;
    }
    api("/api/auth/me")
      .then((me) => {
        setUser(me);
        localStorage.setItem("askdb_user", JSON.stringify(me));
      })
      .catch(() => {
        clearSession();
        setUser(null);
      })
      .finally(() => setReady(true));
  }, []);

  async function login(email, password) {
    const data = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    saveSession(data);
    setUser(data.user);
  }

  async function register(name, email, password) {
    const data = await api("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    });
    saveSession(data);
    setUser(data.user);
  }

  async function logout() {
    const refresh = localStorage.getItem("askdb_refresh");
    try {
      if (refresh) {
        await api("/api/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: refresh }),
        });
      }
    } catch {
      // Local sign-out still happens when the network call fails.
    }
    clearSession();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, ready, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
