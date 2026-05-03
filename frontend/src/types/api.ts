export type JsonObject = Record<string, unknown>;

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

export interface UserMe {
  user_id: string;
  username: string;
  roles: string[];
  is_superadmin: boolean;
}

export interface ApiErrorPayload {
  detail?: string;
  error_code?: string;
  message?: string;
}