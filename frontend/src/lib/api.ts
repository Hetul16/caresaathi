// API client. Access token lives in memory only (never localStorage); the refresh token is an HttpOnly cookie.
// Errors arrive as RFC 9457 problem details (docs/15-api-spec.md section 3.4).

export interface FieldError { field: string; message: string }

export class ApiError extends Error {
  constructor(public status: number, public type: string, public title: string, public detail: string, public errors: FieldError[] = []) {
    super(title);
  }
  fieldMessage(name: string): string | undefined {
    return this.errors.find((e) => e.field === name)?.message;
  }
}

let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;
let onSessionLost: (() => void) | null = null;

export const setAccessToken = (t: string | null) => { accessToken = t; };
export const getAccessToken = () => accessToken;
export const setSessionLostHandler = (fn: (() => void) | null) => { onSessionLost = fn; };

async function toError(res: Response): Promise<ApiError> {
  let body: { type?: string; title?: string; detail?: string; errors?: FieldError[] } = {};
  try { body = await res.json(); } catch { /* not JSON */ }
  const type = (body.type ?? "error").split("/").pop() ?? "error";
  return new ApiError(res.status, type, body.title ?? "Something went wrong", body.detail ?? "", body.errors ?? []);
}

export async function refreshSession(): Promise<boolean> {
  // One refresh at a time: the refresh token rotates, so two parallel calls would invalidate each other.
  refreshing ??= (async () => {
    try {
      const res = await fetch("/api/v1/auth/refresh", { method: "POST", credentials: "include" });
      if (!res.ok) { accessToken = null; return false; }
      const j = await res.json();
      accessToken = j.access_token;
      return true;
    } catch {
      return false;
    } finally {
      setTimeout(() => { refreshing = null; }, 0);
    }
  })();
  return refreshing;
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown; retry?: boolean } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  let body = init.body;
  if (init.json !== undefined) { headers.set("Content-Type", "application/json"); body = JSON.stringify(init.json); }

  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { ...init, headers, body, credentials: "include" });
  } catch {
    throw new ApiError(0, "network", "Cannot reach CareSaathi", "Check your connection and try again.");
  }
  if (res.status === 401 && init.retry !== false && !path.startsWith("/auth/")) {
    if (await refreshSession()) return api<T>(path, { ...init, retry: false });
    onSessionLost?.();
  }
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
