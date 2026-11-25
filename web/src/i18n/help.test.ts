import { describe, expect, it } from "vitest";

import { isWikiPage, wikiSource } from "../wiki/content";
import { slug } from "../wiki/markdown";
import { enHelp, ptHelp, type HelpKey } from "./messages-help";

const HELP = { pt: ptHelp, en: enHelp } as const;

function sectionIds(lang: keyof typeof HELP, page: string): string[] {
  if (!isWikiPage(page)) return [];
  return wikiSource(lang, page)
    .split("\n")
    .filter((line) => line.startsWith("## "))
    .map((line) => slug(line.slice(3)));
}

describe("help texts", () => {
  it("have a title and a text for every term, in both languages", () => {
    for (const help of Object.values(HELP)) {
      for (const [key, entry] of Object.entries(help)) {
        expect(entry.title.trim(), key).not.toBe("");
        expect(entry.text.trim().length, key).toBeGreaterThan(20);
      }
    }
  });

  it("are translated", () => {
    for (const key of Object.keys(ptHelp) as HelpKey[]) {
      expect(enHelp[key].text, key).not.toBe(ptHelp[key].text);
    }
  });

  it("link to wiki sections that exist, on the same page in both languages", () => {
    for (const [lang, help] of Object.entries(HELP) as [keyof typeof HELP, typeof ptHelp][]) {
      for (const [key, entry] of Object.entries(help)) {
        if (!entry.wiki) continue;
        const [page, section] = entry.wiki.split("#");
        expect(sectionIds(lang, page), `${lang}/${key} -> ${entry.wiki}`).toContain(section);
      }
    }
    for (const key of Object.keys(ptHelp) as HelpKey[]) {
      expect(enHelp[key].wiki?.split("#")[0], key).toBe(ptHelp[key].wiki?.split("#")[0]);
    }
  });
});
