// Thin fetch helper shared by lib/api/client.ts. Server Components call
// the FastAPI backend directly (same container, localhost network);
// Client Components go through the same-origin `/api/backend/*` proxy
// (see app/api/backend/[...path]/route.ts) since the browser can only
// reach the Next.js origin inside the Replit preview iframe.
//
// Every call is best-effort: on any network error, non-2xx response,
// or "no analysis has run yet" condition, callers get `null` back so
// they can fall back to mock data without throwing.

const SERVER_BACKEND_ORIGIN = process.env.BACKEND_URL || "http://localhost:8000";

function baseUrl(): string {
  return typeof window === "undefined" ? SERVER_BACKEND_ORIGIN : "/api/backend";
}

export async function backendGet<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${baseUrl()}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function backendPostJson<T>(path: string, body: unknown): Promise<T | null> {
  try {
    const res = await fetch(`${baseUrl()}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function backendUpload<T>(path: string, formData: FormData): Promise<T | { error: string } | null> {
  try {
    const res = await fetch(`${baseUrl()}${path}`, {
      method: "POST",
      body: formData,
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      return { error: (data && data.detail) || `Upload failed (${res.status})` };
    }
    return data as T;
  } catch {
    return { error: "Backend unavailable" };
  }
}
