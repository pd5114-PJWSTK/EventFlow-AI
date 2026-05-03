import type { ApiErrorPayload, AuthTokens } from "../types/api";

type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE";

export class ApiError extends Error {
  status: number;
  payload: ApiErrorPayload | null;

  constructor(message: string, status: number, payload: ApiErrorPayload | null) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

export class ApiClient {
  private getTokens: () => AuthTokens | null;
  private onTokenUpdate: (tokens: AuthTokens | null) => void;

  constructor(
    getTokens: () => AuthTokens | null,
    onTokenUpdate: (tokens: AuthTokens | null) => void,
  ) {
    this.getTokens = getTokens;
    this.onTokenUpdate = onTokenUpdate;
  }

  async login(username: string, password: string): Promise<AuthTokens> {
    const response = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new ApiError(data?.detail ?? "B³¹d logowania", response.status, data ?? null);
    }
    const tokens = { accessToken: data.access_token as string, refreshToken: data.refresh_token as string };
    this.onTokenUpdate(tokens);
    return tokens;
  }

  async logout(): Promise<void> {
    const tokens = this.getTokens();
    if (tokens) {
      await fetch("/auth/logout", {
        method: "POST",
        headers: { Authorization: `Bearer ${tokens.refreshToken}` },
      });
    }
    this.onTokenUpdate(null);
  }

  async logoutAll(): Promise<void> {
    await this.request("POST", "/auth/logout-all", undefined, true);
    this.onTokenUpdate(null);
  }

  async request<T>(
    method: HttpMethod,
    path: string,
    body?: unknown,
    allowUnauthenticated = false,
    retryOnUnauthorized = true,
  ): Promise<T> {
    const tokens = this.getTokens();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (tokens?.accessToken) {
      headers.Authorization = `Bearer ${tokens.accessToken}`;
    } else if (!allowUnauthenticated) {
      throw new ApiError("Brak sesji u¿ytkownika", 401, null);
    }

    const response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });

    if (response.status === 401 && retryOnUnauthorized && !allowUnauthenticated && tokens?.refreshToken) {
      const refreshed = await this.refresh(tokens.refreshToken);
      if (refreshed) {
        return this.request<T>(method, path, body, allowUnauthenticated, false);
      }
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const data = (await response.json().catch(() => null)) as T | ApiErrorPayload | null;
    if (!response.ok) {
      const payload = (data as ApiErrorPayload | null) ?? null;
      throw new ApiError(
        payload?.detail ?? payload?.message ?? `B³¹d API (${response.status})`,
        response.status,
        payload,
      );
    }
    return data as T;
  }

  private async refresh(refreshToken: string): Promise<boolean> {
    const response = await fetch("/auth/refresh", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${refreshToken}`,
      },
    });
    if (!response.ok) {
      this.onTokenUpdate(null);
      return false;
    }
    const data = await response.json();
    this.onTokenUpdate({ accessToken: data.access_token as string, refreshToken: data.refresh_token as string });
    return true;
  }
}