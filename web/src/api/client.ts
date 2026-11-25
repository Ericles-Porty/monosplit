import { useEffect, useState } from "react";

/** True in the site written by `monosplit web export`, which has no server. */
export const isStatic = typeof window !== "undefined" && window.MONOSPLIT_STATIC === true;

export interface ErrorDetail {
  message: string;
  field: string | null;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly field: string | null = null,
  ) {
    super(message);
  }
}

/**
 * API path (e.g. "run/study/jpetstore/gpt-5.6-luna/original/1") to a URL of this deployment.
 * A query string (from queryPath) goes to the server as is; the static site has none.
 */
export function apiUrl(path: string): string {
  const [route, query] = path.split("?", 2);
  const encoded = route.split("/").map(encodeURIComponent).join("/");
  if (isStatic) return `./data/${encoded}.json`;
  return `/api/${encoded}${query ? `?${query}` : ""}`;
}

/** `path` with the non-empty `params` as a query string. */
export function queryPath(path: string, params: Record<string, string | number | null | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `${path}?${text}` : path;
}

async function failure(response: Response): Promise<ApiError> {
  const text = await response.text();
  try {
    const detail = JSON.parse(text).detail;
    if (detail && typeof detail === "object") return new ApiError(response.status, detail.message ?? text, detail.field ?? null);
    if (typeof detail === "string") return new ApiError(response.status, detail);
  } catch {
    // not JSON
  }
  return new ApiError(response.status, text || response.statusText);
}

const cache = new Map<string, Promise<unknown>>();
const listeners = new Set<() => void>();
let version = 0;

export function fetchJson<T>(path: string): Promise<T> {
  let request = cache.get(path);
  if (!request) {
    request = fetch(apiUrl(path)).then(async (response) => {
      if (!response.ok) throw await failure(response);
      return response.json();
    });
    request.catch(() => cache.delete(path));
    cache.set(path, request);
  }
  return request as Promise<T>;
}

/** Uncached GET, for data that changes while the page is open (jobs). */
export async function getFresh<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path), { cache: "no-store" });
  if (!response.ok) throw await failure(response);
  return response.json();
}

/** Drop cached responses, so every open view fetches fresh data. */
export function invalidate(): void {
  cache.clear();
  version += 1;
  for (const listener of listeners) listener();
}

/**
 * POST, PUT or DELETE to the local API. The X-MonoSplit-Request header is what the server
 * requires on every change; pages from other sites cannot send it.
 */
export async function send<T>(method: "POST" | "PUT" | "DELETE", path: string, body?: unknown): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method,
    headers: { "Content-Type": "application/json", "X-MonoSplit-Request": "1" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw await failure(response);
  return response.json();
}

export interface Resource<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
}

/** Fetch `path`; while a new path loads, the previous data stays, so views do not jump. */
export function useResource<T>(path: string | null): Resource<T> {
  const [state, setState] = useState<{ key: string | null; data?: T; error?: Error }>({ key: null });
  const [current, setCurrent] = useState(version);
  useEffect(() => {
    const update = () => setCurrent(version);
    listeners.add(update);
    return () => {
      listeners.delete(update);
    };
  }, []);
  const key = path === null ? null : `${current}:${path}`;
  useEffect(() => {
    if (path === null) return;
    let active = true;
    fetchJson<T>(path).then(
      (data) => active && setState({ key, data }),
      (error: Error) => active && setState((previous) => ({ key, data: previous.data, error })),
    );
    return () => {
      active = false;
    };
  }, [path, key]);
  return { data: state.data, error: state.key === key ? state.error : undefined, loading: state.key !== key };
}
