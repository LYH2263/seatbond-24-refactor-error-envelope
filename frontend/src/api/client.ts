export type ErrorDetails = Record<string, unknown>;

/** Error raised for non-2xx responses, carrying the backend error envelope. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: ErrorDetails;

  constructor(status: number, code: string, message: string, details?: ErrorDetails) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function parseEnvelope(data: unknown): { code: string; message: string; details?: ErrorDetails } | null {
  if (data && typeof data === "object") {
    const d = data as { code?: unknown; message?: unknown; details?: unknown };
    if (typeof d.code === "string" && typeof d.message === "string") {
      return {
        code: d.code,
        message: d.message,
        details: d.details && typeof d.details === "object" ? (d.details as ErrorDetails) : undefined,
      };
    }
  }
  return null;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    let envelope: ReturnType<typeof parseEnvelope> = null;
    try {
      envelope = parseEnvelope(JSON.parse(text));
    } catch {
      // non-JSON error body (proxy page, etc.) — fall through to generic error
    }
    if (envelope) {
      throw new ApiError(res.status, envelope.code, envelope.message, envelope.details);
    }
    throw new ApiError(res.status, `HTTP_${res.status}`, text || res.statusText || "请求失败");
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}
