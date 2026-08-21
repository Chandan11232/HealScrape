/** Backend base URL — set VITE_API_BASE on Vercel (no trailing slash). */
export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

/** fetch() with ngrok browser-warning bypass when needed. */
export function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (API_BASE.includes("ngrok")) {
    headers["ngrok-skip-browser-warning"] = "true";
  }
  return fetch(`${API_BASE}${path}`, { ...options, headers });
}
