import { createContext, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { ApiClient } from "./api";
import { clearTokens, getStoredTokens, storeTokens } from "./session";
import type { AuthTokens, UserMe } from "../types/api";

interface AuthContextValue {
  api: ApiClient;
  tokens: AuthTokens | null;
  me: UserMe | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  loadMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const tokensRef = useRef<AuthTokens | null>(getStoredTokens());
  const [tokens, setTokens] = useState<AuthTokens | null>(() => tokensRef.current);
  const [me, setMe] = useState<UserMe | null>(null);

  const api = useMemo(
    () =>
      new ApiClient(
        () => tokensRef.current,
        (nextTokens) => {
          tokensRef.current = nextTokens;
          if (nextTokens) {
            storeTokens(nextTokens);
            setTokens(nextTokens);
          } else {
            clearTokens();
            setTokens(null);
            setMe(null);
          }
        },
      ),
    [],
  );

  const login = async (username: string, password: string): Promise<void> => {
    await api.login(username, password);
    const meData = await api.request<UserMe>("GET", "/auth/me");
    setMe(meData);
  };

  const logout = async (): Promise<void> => {
    await api.logout();
    setMe(null);
  };

  const loadMe = async (): Promise<void> => {
    if (!tokensRef.current) {
      setMe(null);
      return;
    }
    const meData = await api.request<UserMe>("GET", "/auth/me");
    setMe(meData);
  };

  const value: AuthContextValue = {
    api,
    tokens,
    me,
    isAuthenticated: Boolean(tokens?.accessToken),
    login,
    logout,
    loadMe,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
