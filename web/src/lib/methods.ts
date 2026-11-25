import type { Messages } from "../i18n/messages";
import type { HelpKey } from "../i18n/messages-help";

/** Interface label of a method id: llm, random, ah:<distance>:<linkage>, hdbscan:<distance>. */
export function methodLabel(t: Messages, method: string, ahSelected?: string | null): string {
  if (method === "llm") return t.methods.llm;
  if (method === "random") return t.methods.random;
  if (method.startsWith("ah:")) {
    const [, distance, linkage] = method.split(":");
    const label = t.methods.ah(t.methods.distances[distance] ?? distance, t.methods.linkages[linkage] ?? linkage);
    return method === ahSelected ? `${label} (${t.methods.selectedControl})` : label;
  }
  if (method.startsWith("hdbscan:")) {
    const [, distance] = method.split(":");
    return t.methods.hdbscan(t.methods.distances[distance] ?? distance);
  }
  return method;
}

/** Explanation of a method, for <Term>. */
export function methodHelp(method: string, ahSelected?: string | null): HelpKey {
  if (method === "llm") return "llm";
  if (method === "random") return "random";
  if (method.startsWith("hdbscan:")) return "hdbscan";
  if (method.startsWith("ah:")) return method === ahSelected ? "ahSelected" : "ahVariant";
  return "method";
}

export function methodGroup(method: string): "treatment" | "controls" | "references" {
  if (method === "llm") return "treatment";
  if (method.startsWith("hdbscan:")) return "references";
  return "controls";
}

/** Order of the method menu: LLM, the selected AH, the other AH variants, random, references. */
export function sortMethods(methods: string[], ahSelected: string | null): string[] {
  const rank = (m: string) => {
    if (m === "llm") return 0;
    if (m === ahSelected) return 1;
    if (m.startsWith("ah:")) return 2;
    if (m === "random") return 3;
    return 4;
  };
  return [...methods].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}
