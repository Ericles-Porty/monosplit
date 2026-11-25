// Wiki pages: one Markdown file per page and language, in content/<lang>/<page>.md.

import type { Lang } from "../i18n/messages";

export const WIKI_PAGES = ["overview", "design", "variables", "metrics", "graph", "treatment", "controls", "analysis", "tool", "glossary"] as const;
export type WikiPageId = (typeof WIKI_PAGES)[number];

const files = import.meta.glob("./content/*/*.md", { query: "?raw", import: "default", eager: true }) as Record<string, string>;

export function isWikiPage(value: string | undefined): value is WikiPageId {
  return (WIKI_PAGES as readonly string[]).includes(value ?? "");
}

export function wikiSource(lang: Lang, page: WikiPageId): string {
  return files[`./content/${lang}/${page}.md`] ?? files[`./content/pt/${page}.md`] ?? "";
}

/** Text of the first "# " heading. */
export function wikiTitle(source: string): string {
  const line = source.split("\n").find((l) => l.startsWith("# "));
  return line ? line.slice(2).trim() : "";
}
