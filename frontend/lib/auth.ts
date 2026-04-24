export type ApiFieldErrors = Record<string, string[]>;

export type AuthUser = {
  id?: number;
  email?: string;
  username?: string;
  first_name?: string;
  last_name?: string;
  role?: string;
  organization_name?: string;
  is_active?: boolean;
};

export type AuthSessionPayload = {
  access: string;
  refresh?: string;
  user?: AuthUser;
};

const API_ROOT = process.env.NEXT_PUBLIC_API_ROOT ?? "http://127.0.0.1:8000/api/v1";
const USER_API_ROOT = process.env.NEXT_PUBLIC_API_BASE_URL ?? `${API_ROOT}/users`;
const LOGIN_PATH = process.env.NEXT_PUBLIC_AUTH_LOGIN_PATH ?? "/auth/login/";

const ACCESS_TOKEN_KEY = "omms_access_token";
const REFRESH_TOKEN_KEY = "omms_refresh_token";
const USER_KEY = "omms_user";

function isBrowser() {
  return typeof window !== "undefined";
}

export class ApiError extends Error {
  status: number;
  fieldErrors: ApiFieldErrors;

  constructor(message: string, status = 0, fieldErrors: ApiFieldErrors = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

function normalizeUrl(root: string, path: string) {
  return `${root.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

function normalizeFieldErrors(payload: unknown): ApiFieldErrors {
  if (!payload || typeof payload !== "object") {
    return {};
  }

  const errors: ApiFieldErrors = {};
  for (const [key, value] of Object.entries(payload)) {
    if (Array.isArray(value)) {
      errors[key] = value.map(String);
    } else if (typeof value === "string") {
      errors[key] = [value];
    }
  }
  return errors;
}

export async function parseApiError(response: Response): Promise<ApiError> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  const fieldErrors = normalizeFieldErrors(payload);
  const detail =
    payload && typeof payload === "object" && "detail" in payload
      ? String((payload as { detail: unknown }).detail)
      : "";
  const message = detail || fieldErrors.non_field_errors?.[0] || "Request failed.";
  return new ApiError(message, response.status, fieldErrors);
}

export function getAccessToken() {
  if (!isBrowser()) {
    return null;
  }
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (!isBrowser()) {
    return null;
  }

  const rawUser = window.localStorage.getItem(USER_KEY);
  if (!rawUser) {
    return null;
  }

  try {
    return JSON.parse(rawUser) as AuthUser;
  } catch {
    return null;
  }
}

export function storeAuthSession(payload: AuthSessionPayload) {
  if (!isBrowser()) {
    return;
  }

  window.localStorage.setItem(ACCESS_TOKEN_KEY, payload.access);
  if (payload.refresh) {
    window.localStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh);
  }
  if (payload.user) {
    window.localStorage.setItem(USER_KEY, JSON.stringify(payload.user));
  }
}

export function clearAuthSession() {
  if (!isBrowser()) {
    return;
  }

  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(init.headers);

  if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(normalizeUrl(API_ROOT, path), {
    ...init,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      clearAuthSession();
      throw new ApiError("Your session has expired. Please sign in again.", response.status);
    }
    throw await parseApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function loginWithEmailPassword(email: string, password: string): Promise<AuthSessionPayload> {
  const response = await fetch(normalizeUrl(USER_API_ROOT, LOGIN_PATH), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw await parseApiError(response);
  }

  return response.json() as Promise<AuthSessionPayload>;
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  return apiFetch<AuthUser>("users/auth/me/");
}
