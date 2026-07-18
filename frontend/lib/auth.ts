export type ApiFieldErrors = Record<string, string[]>;
export type UploadProgressHandler = (progress: number) => void;

export type AuthUser = {
  id?: number;
  email?: string;
  username?: string;
  first_name?: string;
  last_name?: string;
  role?: string;
  organization_name?: string;
  region?: string;
  reports_to?: number | null;
  tenant?: number | null;
  tenant_name?: string;
  tenant_slug?: string;
  tenant_type?: string;
  is_active?: boolean;
  is_platform_admin?: boolean;
  is_company_admin?: boolean;
  is_staff?: boolean;
  is_superuser?: boolean;
};

export type AuthSessionPayload = {
  access: string;
  refresh?: string;
  user?: AuthUser;
  expires_in?: number;
  session_expires_at?: string;
};

const API_ROOT = process.env.NEXT_PUBLIC_API_ROOT ?? "http://127.0.0.1:8000/api/v1";
const RAW_USER_API_ROOT = process.env.NEXT_PUBLIC_USERS_API_ROOT ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? API_ROOT;
const LOGIN_PATH = process.env.NEXT_PUBLIC_AUTH_LOGIN_PATH ?? "/auth/login/";

const ACCESS_TOKEN_KEY = "omms_access_token";
const REFRESH_TOKEN_KEY = "omms_refresh_token";
const USER_KEY = "omms_user";
const SESSION_MESSAGE_KEY = "omms_session_message";
const SKIP_RESTORE_KEY = "omms_skip_session_restore";
const LOGOUT_MARKER_KEY = "omms_logout_marker";
const AUTH_EVENT_KEY = "omms_auth_event";
const REFRESH_PATH = "users/auth/token/refresh/";
const LOGOUT_PATH = "users/auth/logout/";
const SESSION_EXPIRED_MESSAGE = "Your session expired after 72 hours of inactivity. Please sign in again.";

let memoryAccessToken: string | null = null;
let refreshPromise: Promise<AuthSessionPayload> | null = null;
let authGeneration = 0;

function isBrowser() {
  return typeof window !== "undefined";
}

export class ApiError extends Error {
  status: number;
  fieldErrors: ApiFieldErrors;
  code: string;

  constructor(message: string, status = 0, fieldErrors: ApiFieldErrors = {}, code = "request_failed") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
    this.code = code;
  }
}

function normalizeUrl(root: string, path: string) {
  return `${root.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

function normalizeUsersApiRoot(root: string) {
  const normalizedRoot = root.replace(/\/$/, "");
  return normalizedRoot.endsWith("/users") ? normalizedRoot : normalizeUrl(normalizedRoot, "users");
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

function isGenericDetail(detail: string) {
  return ["not found.", "request failed.", "permission denied.", "method not allowed."].includes(
    detail.trim().toLowerCase(),
  );
}

function getDefaultApiErrorMessage(status: number, fieldErrors: ApiFieldErrors) {
  if (status === 400 && Object.keys(fieldErrors).length > 0) {
    return "Please review the highlighted fields and try again.";
  }
  if (status === 400) {
    return "We could not accept that request. Please review the details and try again.";
  }
  if (status === 401) {
    return "Your session has expired. Please sign in again.";
  }
  if (status === 403) {
    return "You do not have permission to perform this action.";
  }
  if (status === 404) {
    return "The requested record could not be found.";
  }
  if (status === 405) {
    return "This action is not available right now.";
  }
  if (status === 409) {
    return "This request conflicts with existing data. Please refresh and try again.";
  }
  if (status >= 500) {
    return "The server ran into a problem. Please try again in a moment.";
  }
  return "We couldn't complete your request. Please try again.";
}

function createApiError(status: number, payload: unknown) {
  const fieldErrors = normalizeFieldErrors(payload);
  const detail =
    payload && typeof payload === "object" && "detail" in payload
      ? String((payload as { detail: unknown }).detail)
      : "";
  const code =
    payload && typeof payload === "object" && "code" in payload ? String((payload as { code: unknown }).code) : "";
  const specificDetail = detail && !isGenericDetail(detail) ? detail : "";
  const message = specificDetail || fieldErrors.non_field_errors?.[0] || getDefaultApiErrorMessage(status, fieldErrors);
  return new ApiError(message, status, fieldErrors, code || "request_failed");
}

export async function parseApiError(response: Response): Promise<ApiError> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  return createApiError(response.status, payload);
}

export function getAccessToken() {
  if (!isBrowser()) {
    return null;
  }
  if (window.localStorage.getItem(LOGOUT_MARKER_KEY)) {
    return null;
  }
  if (memoryAccessToken) {
    return memoryAccessToken;
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

  memoryAccessToken = payload.access;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, payload.access);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  window.localStorage.removeItem(LOGOUT_MARKER_KEY);
  if (payload.user) {
    window.localStorage.setItem(USER_KEY, JSON.stringify(payload.user));
  }
  publishAuthEvent("session_refreshed");
}

function publishAuthEvent(type: "session_cleared" | "session_refreshed") {
  if (!isBrowser()) {
    return;
  }
  const payload = JSON.stringify({ type, at: Date.now() });
  try {
    window.localStorage.setItem(AUTH_EVENT_KEY, payload);
  } catch {
    return;
  }
  if ("BroadcastChannel" in window) {
    try {
      const channel = new BroadcastChannel("omms-auth");
      channel.postMessage({ type });
      channel.close();
    } catch {
      // Storage events still cover browsers without usable BroadcastChannel support.
    }
  }
}

async function revokeServerSession(accessToken: string | null) {
  try {
    const headers = new Headers({ "Content-Type": "application/json" });
    if (accessToken) {
      headers.set("Authorization", `Bearer ${accessToken}`);
    }
    await fetch(normalizeUrl(API_ROOT, LOGOUT_PATH), {
      method: "POST",
      headers,
      credentials: "include",
      keepalive: true,
      body: "{}",
    });
  } catch {
    // Logout must still clear local state if the network is unavailable.
  }
}

export function clearAuthSession(options: { notifyServer?: boolean; reason?: "expired" | "logout" } = {}) {
  if (!isBrowser()) {
    return;
  }

  const accessToken = getAccessToken();
  authGeneration += 1;
  if (options.notifyServer !== false) {
    void revokeServerSession(accessToken);
  }
  memoryAccessToken = null;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
  if (options.reason === "expired") {
    window.sessionStorage.setItem(SESSION_MESSAGE_KEY, SESSION_EXPIRED_MESSAGE);
  } else if (options.notifyServer !== false) {
    window.sessionStorage.setItem(SKIP_RESTORE_KEY, "1");
    window.localStorage.setItem(LOGOUT_MARKER_KEY, String(Date.now()));
  }
  publishAuthEvent("session_cleared");
}

export function consumeSessionMessage() {
  if (!isBrowser()) {
    return "";
  }
  const message = window.sessionStorage.getItem(SESSION_MESSAGE_KEY) || "";
  window.sessionStorage.removeItem(SESSION_MESSAGE_KEY);
  return message;
}

export function consumeSkipSessionRestore() {
  if (!isBrowser()) {
    return false;
  }
  const shouldSkip = Boolean(
    window.sessionStorage.getItem(SKIP_RESTORE_KEY) || window.localStorage.getItem(LOGOUT_MARKER_KEY),
  );
  window.sessionStorage.removeItem(SKIP_RESTORE_KEY);
  return shouldSkip;
}

async function refreshAuthSession(): Promise<AuthSessionPayload> {
  if (refreshPromise) {
    return refreshPromise;
  }

  const refreshGeneration = authGeneration;
  refreshPromise = (async () => {
    const legacyRefresh = isBrowser() ? window.localStorage.getItem(REFRESH_TOKEN_KEY) : null;
    let response: Response;
    try {
      response = await fetch(normalizeUrl(API_ROOT, REFRESH_PATH), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(legacyRefresh ? { refresh: legacyRefresh } : {}),
      });
    } catch {
      throw new ApiError("We couldn't reach the server. Check your connection and try again.", 0, {}, "network_error");
    }

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        const wasExplicitLogout = isBrowser() && Boolean(window.localStorage.getItem(LOGOUT_MARKER_KEY));
        clearAuthSession({ notifyServer: false, reason: wasExplicitLogout ? undefined : "expired" });
        throw new ApiError(SESSION_EXPIRED_MESSAGE, response.status, {}, "session_expired");
      }
      throw await parseApiError(response);
    }

    const payload = (await response.json()) as AuthSessionPayload;
    if (refreshGeneration !== authGeneration || (isBrowser() && window.localStorage.getItem(LOGOUT_MARKER_KEY))) {
      throw new ApiError("Session changed while refresh was in progress.", 0, {}, "session_changed");
    }
    storeAuthSession(payload);
    return payload;
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

export async function restoreAuthSession(): Promise<AuthUser | null> {
  if (consumeSkipSessionRestore()) {
    return null;
  }
  const token = getAccessToken();
  if (token) {
    return getStoredUser();
  }
  try {
    const payload = await refreshAuthSession();
    return payload.user ?? getStoredUser();
  } catch (error) {
    if (error instanceof ApiError && error.code === "network_error") {
      throw error;
    }
    return null;
  }
}

function shouldAttemptRefresh(path: string) {
  return !path.includes(REFRESH_PATH) && !path.includes(LOGOUT_PATH);
}

async function fetchWithAuth(path: string, init: RequestInit, retryOnUnauthorized: boolean): Promise<Response> {
  const token = getAccessToken();
  const headers = new Headers(init.headers);

  if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(normalizeUrl(API_ROOT, path), {
      ...init,
      headers,
      credentials: init.credentials ?? "include",
    });
  } catch {
    throw new ApiError("We couldn't reach the server. Check your connection and try again.", 0, {}, "network_error");
  }

  if (response.status === 401 && retryOnUnauthorized && shouldAttemptRefresh(path)) {
    await refreshAuthSession();
    return fetchWithAuth(path, init, false);
  }
  return response;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetchWithAuth(path, init, true);

  if (!response.ok) {
    if (response.status === 401) {
      clearAuthSession({ notifyServer: false, reason: "expired" });
      throw new ApiError(SESSION_EXPIRED_MESSAGE, response.status, {}, "session_expired");
    }
    throw await parseApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function apiDownload(path: string, init: RequestInit = {}): Promise<Blob> {
  const response = await fetchWithAuth(path, init, true);

  if (!response.ok) {
    if (response.status === 401) {
      clearAuthSession({ notifyServer: false, reason: "expired" });
      throw new ApiError(SESSION_EXPIRED_MESSAGE, response.status, {}, "session_expired");
    }
    throw await parseApiError(response);
  }

  return response.blob();
}

export async function apiUpload<T>(
  path: string,
  formData: FormData,
  options: {
    method?: string;
    onProgress?: UploadProgressHandler;
  } = {},
): Promise<T> {
  const sendUpload = (retryOnUnauthorized: boolean): Promise<T> => new Promise<T>((resolve, reject) => {
    const token = getAccessToken();
    const request = new XMLHttpRequest();
    request.open(options.method ?? "POST", normalizeUrl(API_ROOT, path));
    request.withCredentials = true;

    if (token) {
      request.setRequestHeader("Authorization", `Bearer ${token}`);
    }

    if (options.onProgress) {
      request.upload.onprogress = (event) => {
        if (!event.lengthComputable) {
          options.onProgress?.(0);
          return;
        }

        options.onProgress?.(Math.round((event.loaded / event.total) * 100));
      };
    }

    request.onerror = () => {
      reject(new ApiError("We couldn't reach the server. Check your connection and try again.", 0, {}, "network_error"));
    };

    request.onload = () => {
      let payload: unknown = null;
      if (request.responseText) {
        try {
          payload = JSON.parse(request.responseText);
        } catch {
          payload = null;
        }
      }

      if (request.status >= 200 && request.status < 300) {
        options.onProgress?.(100);
        if (request.status === 204) {
          resolve(undefined as T);
          return;
        }
        resolve(payload as T);
        return;
      }

      if (request.status === 401) {
        if (retryOnUnauthorized) {
          refreshAuthSession()
            .then(() => sendUpload(false).then(resolve).catch(reject))
            .catch(reject);
          return;
        }
        clearAuthSession({ notifyServer: false, reason: "expired" });
        reject(new ApiError(SESSION_EXPIRED_MESSAGE, request.status, {}, "session_expired"));
        return;
      }

      reject(createApiError(request.status, payload));
    };

    request.send(formData);
  });

  return sendUpload(true);
}

export async function loginWithEmailPassword(email: string, password: string): Promise<AuthSessionPayload> {
  const response = await fetch(normalizeUrl(normalizeUsersApiRoot(RAW_USER_API_ROOT), LOGIN_PATH), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify({ email: email.trim(), password }),
  });

  if (!response.ok) {
    throw await parseApiError(response);
  }

  return response.json() as Promise<AuthSessionPayload>;
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  return apiFetch<AuthUser>("users/auth/me/");
}

if (isBrowser()) {
  window.addEventListener("storage", (event) => {
    if (event.key !== AUTH_EVENT_KEY || !event.newValue) {
      return;
    }
    try {
      const payload = JSON.parse(event.newValue) as { type?: string };
      if (payload.type === "session_cleared") {
        memoryAccessToken = null;
      }
    } catch {
      memoryAccessToken = null;
    }
  });
  if ("BroadcastChannel" in window) {
    try {
      const channel = new BroadcastChannel("omms-auth");
      channel.onmessage = (event) => {
        if (event.data?.type === "session_cleared") {
          memoryAccessToken = null;
        }
      };
    } catch {
      // Storage events are enough for unsupported environments.
    }
  }
}
