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

  let response: Response;
  try {
    response = await fetch(normalizeUrl(API_ROOT, path), {
      ...init,
      headers,
    });
  } catch {
    throw new ApiError("We couldn't reach the server. Check your connection and try again.", 0, {}, "network_error");
  }

  if (!response.ok) {
    if (response.status === 401) {
      clearAuthSession();
      throw new ApiError("Your session has expired. Please sign in again.", response.status, {}, "session_expired");
    }
    throw await parseApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function apiUpload<T>(
  path: string,
  formData: FormData,
  options: {
    method?: string;
    onProgress?: UploadProgressHandler;
  } = {},
): Promise<T> {
  const token = getAccessToken();

  return new Promise<T>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(options.method ?? "POST", normalizeUrl(API_ROOT, path));

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
        clearAuthSession();
        reject(new ApiError("Your session has expired. Please sign in again.", request.status, {}, "session_expired"));
        return;
      }

      reject(createApiError(request.status, payload));
    };

    request.send(formData);
  });
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
