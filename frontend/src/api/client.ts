export type ErrorDetails = Record<string, unknown>;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ErrorDetails;

  constructor(status: number, code: string, message: string, details?: ErrorDetails | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details ?? {};
  }
}

type ErrorEnvelope = {
  error?: {
    code?: unknown;
    message?: unknown;
    details?: unknown;
  };
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    throw await parseError(res);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

async function parseError(res: Response): Promise<ApiError> {
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    let payload: unknown;
    try {
      payload = await res.json();
    } catch {
      payload = null;
    }
    const envelope = (payload ?? {}) as ErrorEnvelope;
    const err = envelope.error;
    if (err && typeof err === "object") {
      const code = typeof err.code === "string" ? err.code : "error";
      const message = typeof err.message === "string" && err.message ? err.message : res.statusText;
      const details =
        err.details && typeof err.details === "object" && !Array.isArray(err.details)
          ? (err.details as ErrorDetails)
          : {};
      return new ApiError(res.status, code, message, details);
    }
    // 非约定包络的 JSON（如旧版 {"detail": ...}）：尽力降级，不假设形状
    const fallback =
      err && typeof err === "object" && typeof (err as { detail?: unknown }).detail === "string"
        ? ((err as { detail: string }).detail as string)
        : res.statusText;
    return new ApiError(res.status, "error", fallback);
  }
  // 非 JSON（网关/代理的 HTML 错误页等）：用文本，避免把整页 HTML 塞进提示
  const text = await res.text().catch(() => "");
  return new ApiError(res.status, "error", text || res.statusText);
}
