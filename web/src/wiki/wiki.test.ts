import { describe, expect, it } from "vitest";

import { WIKI_PAGES, wikiSource, wikiTitle } from "./content";
import { renderMarkdown, slug } from "./markdown";

const LANGS = ["pt", "en"] as const;
const APP_PAGES = ["overview", "decompositions", "results", "wiki", "config", "execution", "data"];

describe("wiki pages", () => {
  it("exist in both languages, with a title", () => {
    for (const lang of LANGS) {
      for (const page of WIKI_PAGES) {
        expect(wikiTitle(wikiSource(lang, page)), `${lang}/${page}`).not.toBe("");
      }
    }
  });

  it("have the same sections in Portuguese and English", () => {
    for (const page of WIKI_PAGES) {
      const count = (lang: (typeof LANGS)[number]) => wikiSource(lang, page).split("\n").filter((l) => l.startsWith("## ")).length;
      expect(count("en"), page).toBe(count("pt"));
    }
  });

  it("link only to pages that exist", () => {
    for (const lang of LANGS) {
      for (const page of WIKI_PAGES) {
        for (const [, target, query] of wikiSource(lang, page).matchAll(/\]\(#\/([a-z]+)(\?[^)]*)?\)/g)) {
          expect(APP_PAGES, `${lang}/${page} -> ${target}`).toContain(target);
          const linked = /page=([a-z]+)/.exec(query ?? "")?.[1];
          if (target === "wiki" && linked) expect(WIKI_PAGES as readonly string[], `${lang}/${page}`).toContain(linked);
        }
      }
    }
  });

  it("render every formula without a KaTeX error", () => {
    for (const lang of LANGS) {
      for (const page of WIKI_PAGES) {
        const html = renderMarkdown(wikiSource(lang, page));
        expect(html, `${lang}/${page}`).not.toContain("katex-error");
        expect(html.replace(/<annotation[^>]*>[\s\S]*?<\/annotation>/g, ""), `${lang}/${page}`).not.toMatch(/\$\$|\\frac|\\sum/);
      }
    }
  });
});

describe("renderMarkdown", () => {
  it("renders inline and display formulas, tables and heading ids", () => {
    const html = renderMarkdown("## Métricas e índice\n\nTexto com $\\mu_i$ e *ênfase*.\n\n$$\nx = \\frac{1}{2}\n$$\n\n| a | b |\n|---|---|\n| 1 | 2 |\n");
    expect(html).toContain('<h2 id="metricas-e-indice">');
    expect(html).toContain('class="katex"');
    expect(html).toContain('class="math-display"');
    expect(html).toContain("<table>");
    expect(html).toContain("<em>ênfase</em>");
  });

  it("leaves an escaped dollar sign as text", () => {
    expect(renderMarkdown("Custo em US\\$ 3")).toContain("US$ 3");
  });

  it("makes heading ids without accents", () => {
    expect(slug("Questões de pesquisa")).toBe("questoes-de-pesquisa");
  });
});
