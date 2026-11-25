// LaTeX tables for the article: booktabs, one tabular inside a table float. Text is escaped
// and the few Unicode symbols of the interface become LaTeX commands, so the output
// compiles with pdfLaTeX (inputenc utf8) and with XeTeX alike.

const SPECIAL: Record<string, string> = {
  "\\": "\\textbackslash{}",
  "&": "\\&",
  "%": "\\%",
  $: "\\$",
  "#": "\\#",
  _: "\\_",
  "{": "\\{",
  "}": "\\}",
  "~": "\\textasciitilde{}",
  "^": "\\textasciicircum{}",
};

const SYMBOLS: Record<string, string> = {
  "−": "$-$",
  "δ": "$\\delta$",
  "α": "$\\alpha$",
  "≥": "$\\geq$",
  "≤": "$\\leq$",
  "×": "$\\times$",
  "→": "$\\rightarrow$",
  "←": "$\\leftarrow$",
  "–": "--",
  "—": "---",
  "·": "\\textperiodcentered{}",
  "…": "\\ldots{}",
  "↑": "$\\uparrow$",
  "↓": "$\\downarrow$",
  // Not special to LaTeX, but printed as ¡ and ¿ by the default OT1 font encoding.
  "<": "$<$",
  ">": "$>$",
};

export function escapeLatex(text: string): string {
  const escaped = text.replace(/[\\&%$#_{}~^]/g, (c) => SPECIAL[c]);
  return escaped.replace(/[−δα≥≤×→←–—·…↑↓<>]/g, (c) => SYMBOLS[c]);
}

/**
 * A formatted number for a text-mode cell. The minus sign goes through math mode; the
 * decimal separator is the one of the interface language.
 */
export function latexNumber(formatted: string): string {
  const text = formatted.replace(/−/g, "-");
  return text.startsWith("-") ? `$-$${escapeLatex(text.slice(1))}` : escapeLatex(text);
}

export interface LatexTable {
  caption: string;
  label: string;
  /** Column alignment, e.g. "llrrrr". */
  align: string;
  /** Header cells, plain text (escaped here). */
  header: string[];
  /** Body cells already in LaTeX: pass text through escapeLatex and numbers through latexNumber. */
  rows: string[][];
  /** Indices of rows that start a new group (a \midrule goes before them). */
  groupStarts?: number[];
  source: string;
}

export function latexTable(table: LatexTable): string {
  const line = (cells: string[]) => `    ${cells.join(" & ")} \\\\`;
  const body: string[] = [];
  table.rows.forEach((row, i) => {
    if (i > 0 && table.groupStarts?.includes(i)) body.push("    \\midrule");
    body.push(line(row));
  });
  return [
    `% ${table.source}`,
    "% Requires \\usepackage{booktabs}.",
    "\\begin{table}[htbp]",
    "  \\centering",
    `  \\caption{${escapeLatex(table.caption)}}`,
    `  \\label{${table.label}}`,
    `  \\begin{tabular}{@{}${table.align}@{}}`,
    "    \\toprule",
    line(table.header.map(escapeLatex)),
    "    \\midrule",
    ...body,
    "    \\bottomrule",
    "  \\end{tabular}",
    "\\end{table}",
    "",
  ].join("\n");
}
