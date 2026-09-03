import type { Shortage } from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  shortages: Shortage[];

  constructor(status: number, detail: unknown) {
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object" && "message" in detail
          ? String((detail as { message: string }).message)
          : `Request failed (${status})`;
    super(message);
    this.status = status;
    this.detail = detail;
    this.shortages =
      detail && typeof detail === "object" && "shortages" in detail
        ? ((detail as { shortages: Shortage[] }).shortages ?? [])
        : [];
  }
}

async function parse(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type") && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { credentials: "include", ...init, headers });
  const body = await parse(res);
  if (!res.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : body;
    if (res.status === 401 && path !== "/api/operator/login" && path !== "/api/operator/setup") {
      const msg = typeof detail === "string" ? detail : "";
      if (msg === "Login required") {
        window.dispatchEvent(new Event("im-auth-lost"));
      }
    }
    throw new ApiError(res.status, detail);
  }
  return body as T;
}
