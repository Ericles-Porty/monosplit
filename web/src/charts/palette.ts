// Colours of the result charts. On screen they come from the CSS variables of the current
// theme; exported figures use PRINT_PALETTE, which repeats the light theme of app.css.

export interface ChartPalette {
  surface: string;
  text: string;
  text2: string;
  muted: string;
  grid: string;
  axis: string;
  font: string;
  /** Method identity: slots 1 to 3 of the validated categorical palette, then the neutral "other". */
  llm: string;
  ah: string;
  random: string;
  other: string;
}

export const PRINT_PALETTE: ChartPalette = {
  surface: "#ffffff",
  text: "#19202a",
  text2: "#5c6571",
  muted: "#7a838f",
  grid: "#dadee5",
  axis: "#b9bfc9",
  font: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  llm: "#2a78d6",
  ah: "#eb6834",
  random: "#1baf7a",
  other: "#898781",
};

export function readChartPalette(): ChartPalette {
  const style = getComputedStyle(document.documentElement);
  const get = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
  return {
    surface: get("--surface", PRINT_PALETTE.surface),
    text: get("--text", PRINT_PALETTE.text),
    text2: get("--text-2", PRINT_PALETTE.text2),
    muted: get("--muted", PRINT_PALETTE.muted),
    grid: get("--border", PRINT_PALETTE.grid),
    axis: get("--edge-intra", PRINT_PALETTE.axis),
    font: get("--font-sans", PRINT_PALETTE.font),
    llm: get("--series-1", PRINT_PALETTE.llm),
    ah: get("--series-2", PRINT_PALETTE.ah),
    random: get("--series-3", PRINT_PALETTE.random),
    other: get("--series-other", PRINT_PALETTE.other),
  };
}

/** Colour of a method: the LLM, the selected AH and the random partition keep fixed slots. */
export function methodColor(palette: ChartPalette, method: string, ahSelected: string | null): string {
  if (method === "llm") return palette.llm;
  if (method === "random") return palette.random;
  if (method === ahSelected) return palette.ah;
  return palette.other;
}
