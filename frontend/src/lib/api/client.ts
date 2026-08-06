export type ApiErrorKind =
  | "validation"
  | "network"
  | "execution"
  | "backend_unavailable"
  | "configuration"
  | "unknown";

export class ApiError extends Error {
  kind: ApiErrorKind;
  status?: number;
  detail?: unknown;

  constructor(message: string, kind: ApiErrorKind = "unknown", status?: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.detail = detail;
  }
}

function baseUrl() {
  const url = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  if (!url) return "/api/backend";

  const isLocalApi = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(url);
  const isLocalBrowser =
    typeof window !== "undefined" &&
    ["localhost", "127.0.0.1"].includes(window.location.hostname);

  if (isLocalApi && !isLocalBrowser) return "/api/backend";
  return url;
}

function classify(status: number): ApiErrorKind {
  if (status === 400 || status === 422) return "validation";
  if (status === 503) return "backend_unavailable";
  if (status >= 500) return "execution";
  return "unknown";
}

async function parseBody(res: Response) {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${baseUrl()}${path}`, {
      ...init,
      signal,
      cache: "no-store",
      headers: {
        ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...init.headers,
      },
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError("API unavailable. Check that the FastAPI contract service is running.", "backend_unavailable");
  }

  const body = await parseBody(res);
  if (!res.ok) {
    const message =
      typeof body === "object" && body && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : `Request failed with status ${res.status}`;
    throw new ApiError(message, classify(res.status), res.status, body);
  }
  return body as T;
}

export function uploadWithProgress<T>(
  path: string,
  formData: FormData,
  onProgress?: (progress: number) => void,
  signal?: AbortSignal,
): Promise<T> {
  return new Promise((resolve, reject) => {
    let xhr: XMLHttpRequest;
    try {
      xhr = new XMLHttpRequest();
      xhr.open("POST", `${baseUrl()}${path}`);
    } catch (error) {
      reject(error);
      return;
    }

    const abort = () => {
      xhr.abort();
      reject(new DOMException("Request aborted", "AbortError"));
    };
    signal?.addEventListener("abort", abort, { once: true });

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      signal?.removeEventListener("abort", abort);
      const body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as T);
        return;
      }
      reject(new ApiError(body?.detail || `Upload failed with status ${xhr.status}`, classify(xhr.status), xhr.status, body));
    };
    xhr.onerror = () => {
      signal?.removeEventListener("abort", abort);
      reject(new ApiError("API unavailable. Check that the FastAPI contract service is running.", "backend_unavailable"));
    };
    xhr.send(formData);
  });
}
