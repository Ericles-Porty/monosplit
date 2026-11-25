import { describe, expect, it } from "vitest";

import { textWidth, wrapText } from "./StripFigure";

describe("wrapText", () => {
  it("keeps a subtitle that fits on one line", () => {
    expect(wrapText("SM · ↑ maior é melhor", 400)).toEqual(["SM · ↑ maior é melhor"]);
  });

  it("breaks at the middle dot before breaking between words", () => {
    const text = "Comunicação entre partições · ↓ menor é melhor";
    const width = textWidth("Comunicação entre partições", 11) + 4;
    expect(wrapText(text, width)).toEqual(["Comunicação entre partições", "↓ menor é melhor"]);
  });

  it("breaks a long part between words", () => {
    const lines = wrapText("Distribuição não extrema", textWidth("Distribuição", 11) + 2);
    expect(lines).toEqual(["Distribuição", "não extrema"]);
  });
});
