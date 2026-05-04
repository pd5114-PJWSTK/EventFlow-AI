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
  private readonly requestTimeoutMs = 15000;
  private readonly slowRequestWarnMs = 4000;

  constructor(
    getTokens: () => AuthTokens | null,
    onTokenUpdate: (tokens: AuthTokens | null) => void,
  ) {
    this.getTokens = getTokens;
    this.onTokenUpdate = onTokenUpdate;
  }

  async login(username: string, password: string): Promise<AuthTokens> {
    const response = await this.safeFetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new ApiError(data?.detail ?? "Sign-in error", response.status, data ?? null);
    }
    const tokens = { accessToken: data.access_token as string, refreshToken: data.refresh_token as string };
    this.onTokenUpdate(tokens);
    return tokens;
  }

  async logout(): Promise<void> {
    const tokens = this.getTokens();
    if (tokens) {
      await this.safeFetch("/auth/logout", {
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
      throw new ApiError("No user session", 401, null);
    }

    const response = await this.safeFetch(path, {
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
        payload?.detail ?? payload?.message ?? `API error (${response.status})`,
        response.status,
        payload,
      );
    }
    return data as T;
  }

  private async refresh(refreshToken: string): Promise<boolean> {
    const response = await this.safeFetch("/auth/refresh", {
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

  private async safeFetch(input: string, init?: RequestInit): Promise<Response> {
    const requestId =
      typeof globalThis.crypto?.randomUUID === "function"
        ? globalThis.crypto.randomUUID()
        : `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const startedAt = Date.now();
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.requestTimeoutMs);
    const headers = new Headers(init?.headers);
    headers.set("X-Request-Id", requestId);
    try {
      const response = await fetch(input, { ...init, headers, signal: controller.signal });
      const durationMs = Date.now() - startedAt;
      if (durationMs >= this.slowRequestWarnMs) {
        console.warn(`[api][slow] ${String(input)} (${durationMs}ms, request-id=${requestId})`);
      }
      return response;
    } catch (error) {
      const durationMs = Date.now() - startedAt;
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new ApiError("API response timeout exceeded.", 0, null);
      }
      if (error instanceof TypeError) {
        console.error(`[api][network] ${String(input)} (${durationMs}ms, request-id=${requestId})`);
        throw new ApiError(
          "No API connection. Check that the backend is running and the frontend API address is correct.",
          0,
          null,
        );
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }
}
