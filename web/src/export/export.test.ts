import { describe, expect, it } from "vitest";

import { fileName, toCsv } from "./files";
import { escapeLatex, latexNumber, latexTable } from "./latex";

describe("toCsv", () => {
  it("quotes cells with commas, quotes or line breaks and keeps full precision", () => {
    const text = toCsv(["a", "b", "c"], [{ a: 'say "hi", twice', b: 0.12114890400604686, c: null }]);
    expect(text).toBe('a,b,c\r\n"say ""hi"", twice",0.12114890400604686,\r\n');
  });
});

describe("fileName", () => {
  it("keeps letters, digits, dots, dashes and underscores", () => {
    expect(fileName("monosplit", "study", "gpt-5.6-luna", "all apps")).toBe("monosplit_study_gpt-5.6-luna_all-apps");
  });
});

describe("LaTeX", () => {
  it("escapes special characters and turns symbols into commands", () => {
    expect(escapeLatex("50% & d_sm #1")).toBe("50\\% \\& d\\_sm \\#1");
    expect(escapeLatex("LLM − AH, δ ≥ 0,147")).toBe("LLM $-$ AH, $\\delta$ $\\geq$ 0,147");
    expect(escapeLatex("d > 0 / d < 0")).toBe("d $>$ 0 / d $<$ 0");
  });

  it("writes the minus sign of numbers in math mode", () => {
    expect(latexNumber("-0,014")).toBe("$-$0,014");
    expect(latexNumber("−0,014")).toBe("$-$0,014");
    expect(latexNumber("0,121")).toBe("0,121");
  });

  it("builds a booktabs table with a rule before each group", () => {
    const tex = latexTable({
      caption: "Métricas · estudo",
      label: "tab:x",
      align: "lr",
      header: ["Método", "SM ↑"],
      rows: [["LLM", "0,121"], ["AH", "0,100"], ["Aleatória", "$-$0,014"]],
      groupStarts: [1],
      source: "test",
    });
    expect(tex).toContain("\\caption{Métricas \\textperiodcentered{} estudo}");
    expect(tex).toContain("Método & SM $\\uparrow$ \\\\");
    const lines = tex.split("\n").map((line) => line.trim());
    // toprule, header, header midrule, first row, group midrule.
    expect(lines.indexOf("\\midrule", lines.indexOf("\\toprule") + 3)).toBe(lines.indexOf("LLM & 0,121 \\\\") + 1);
    expect(lines).toContain("\\bottomrule");
  });
});
