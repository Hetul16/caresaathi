// An invitation code waits in this browser tab between opening the link and signing in. It is never stored anywhere else.
const KEY = "cs-join";
export function pendingJoin(): string | null { try { return sessionStorage.getItem(KEY); } catch { return null; } }
export function rememberJoin(code: string) { try { sessionStorage.setItem(KEY, code); } catch { /* ignore */ } }
export function clearPendingJoin() { try { sessionStorage.removeItem(KEY); } catch { /* ignore */ } }
