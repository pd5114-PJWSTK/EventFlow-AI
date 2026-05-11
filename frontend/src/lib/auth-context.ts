import { createContext } from "react";

import type { ApiClient } from "./api";
import type { AuthTokens, UserMe } from "../types/api";

export interface AuthContextValue {
  api: ApiClient;
  tokens: AuthTokens | null;
  me: UserMe | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  loadMe: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);
