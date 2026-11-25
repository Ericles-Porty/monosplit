// Markdown of the wiki pages, with formulas between $...$ (inline) and $$...$$ (display)
// rendered by KaTeX. The pages are files of this repository, written by the authors; the
// output is inserted as HTML.

import "katex/dist/katex.min.css";

import katex from "katex";
import { Marked, type TokenizerAndRendererExtension } from "marked";

function tex(source: string, displayMode: boolean): string {
  return katex.renderToString(source, { displayMode, throwOnError: false, output: "htmlAndMathml" });
}

const displayMath: TokenizerAndRendererExtension = {
  name: "displayMath",
  level: "block",
  start(src) {
    const index = src.indexOf("$$");
    return index < 0 ? undefined : index;
  },
  tokenizer(src) {
    const match = /^\$\$([\s\S]+?)\$\$[ \t]*(?:\n+|$)/.exec(src);
    return match ? { type: "displayMath", raw: match[0], text: match[1].trim() } : undefined;
  },
  renderer(token) {
    return `<div class="math-display">${tex(token.text as string, true)}</div>\n`;
  },
};

const inlineMath: TokenizerAndRendererExtension = {
  name: "inlineMath",
  level: "inline",
  start(src) {
    const index = src.indexOf("$");
    return index < 0 ? undefined : index;
  },
  tokenizer(src) {
    const match = /^\$(?!\$)((?:\\.|[^\\$\n])+?)\$/.exec(src);
    return match ? { type: "inlineMath", raw: match[0], text: match[1] } : undefined;
  },
  renderer(token) {
    return tex(token.text as string, false);
  },
};

/** Heading id: lower case, accents removed, words joined by dashes. */
export function slug(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

const marked = new Marked({
  gfm: true,
  extensions: [displayMath, inlineMath],
  renderer: {
    heading({ tokens, depth, text }) {
      return `<h${depth} id="${slug(text)}">${this.parser.parseInline(tokens)}</h${depth}>\n`;
    },
  },
});

export function renderMarkdown(source: string): string {
  return marked.parse(source, { async: false });
}
