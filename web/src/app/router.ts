import { useEffect, useState } from "react";

// Hash routes (#/page?key=value), so the static export needs no server-side rewrites.

export interface Route {
  page: string;
  params: Record<string, string>;
}

export type Params = Record<string, string | number | null | undefined>;

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#\/?/, "");
  const [path, query = ""] = raw.split("?");
  const params: Record<string, string> = {};
  new URLSearchParams(query).forEach((value, key) => {
    params[key] = value;
  });
  return { page: path || "overview", params };
}

export function hrefFor(page: string, params: Params = {}): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") query.set(key, String(value));
  }
  const text = query.toString();
  return `#/${page}${text ? `?${text}` : ""}`;
}

export function navigate(page: string, params: Params = {}, replace = false): void {
  const href = hrefFor(page, params);
  if (replace) {
    history.replaceState(null, "", href);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  } else {
    window.location.hash = href;
  }
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const update = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}
