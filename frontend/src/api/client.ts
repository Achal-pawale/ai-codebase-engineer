import { ApiError } from "@/types/api";

const BASE_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");

const DEFAULT_TIMEOUT_MS = 30_000;

interface RequestOptions {
  /** Milliseconds before the request is aborted. Long-running AI calls get more. */
  timeoutMs?: number;
}

function extractDetailMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    // FastAPI/pydantic 422 shape: [{ loc, msg, type }, ...]
    const messages = detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : null))
      .filter((msg): msg is string => Boolean(msg));

    if (messages.length > 0) return messages.join(" ");
  }

  return null;
}

async function request<T>(path: string, init: RequestInit, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? DEFAULT_TIMEOUT_MS);

  let response: Response;

  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(init.headers || {}),
      },
    });
  } catch (error) {
    clearTimeout(timeout);

    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("timeout", "The backend didn't respond in time. It may still be working — try again shortly.");
    }

    throw new ApiError(
      "network",
      `Couldn't reach the backend at ${BASE_URL}. Make sure the FastAPI server is running.`
    );
  }

  clearTimeout(timeout);

  let body: unknown = null;
  const text = await response.text();

  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (response.status === 429) {
    throw new ApiError("rate_limit", "Too many requests in a short window. Wait a moment and try again.", 429, body);
  }

  if (response.status === 422) {
    const detail = body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : body;

    throw new ApiError("validation", extractDetailMessage(detail) ?? "The backend rejected the request.", 422, body);
  }

  if (!response.ok) {
    const detail = body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : null;

    throw new ApiError(
      "http",
      extractDetailMessage(detail) ?? `Backend returned ${response.status} ${response.statusText}.`,
      response.status,
      body
    );
  }

  return body as T;
}

export const apiClient = {
  get<T>(path: string, options?: RequestOptions): Promise<T> {
    return request<T>(path, { method: "GET" }, options);
  },

  post<T>(path: string, payload: unknown, options?: RequestOptions): Promise<T> {
    return request<T>(path, { method: "POST", body: JSON.stringify(payload) }, options);
  },
};

export const API_BASE_URL = BASE_URL;

/** AI calls (ask/investigate/plan/propose-change) run through Gemini and can take longer. */
export const AI_TIMEOUT_MS = 60_000;
