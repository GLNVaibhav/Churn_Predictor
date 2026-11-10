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
  const configuredUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  const isLocalApi = configuredUrl ? /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(configuredUrl) : false;
  const isLocalBrowser = typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname);

  // Production and local same-origin traffic uses the Next proxy, so backend origins
  // remain server-side configuration and browser requests do not bypass the proxy.
  if (!configuredUrl || !isLocalBrowser || isLocalApi) return "/api/backend";
  return configuredUrl;
}

function classify(status: number): ApiErrorKind {
  if (status === 400 || status === 422) return "validation";
  if (status === 503) return "backend_unavailable";
  if (status >= 500) return "execution";
  return "unknown";
}

function parseTextBody(text: string) {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function parseBody(res: Response) {
  return parseTextBody(await res.text());
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
  let res: Response;
  const timeoutSignal = AbortSignal.timeout(30_000);
  const requestSignal = signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal;
  try {
    res = await fetch(`${baseUrl()}${path}`, {
      ...init,
      signal: requestSignal,
      cache: "no-store",
      headers: {
        ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...init.headers,
      },
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    if (timeoutSignal.aborted) throw new ApiError("API request timed out. Please retry.", "network");
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
      xhr.timeout = 120_000;
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
      const body = parseTextBody(xhr.responseText);
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
    xhr.ontimeout = () => {
      signal?.removeEventListener("abort", abort);
      reject(new ApiError("Dataset upload timed out. Please retry.", "network"));
    };
    xhr.send(formData);
  });
}
