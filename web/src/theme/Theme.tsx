import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type ThemeName = "light" | "dark";

const STORAGE_KEY = "monosplit.theme";

interface ThemeValue {
  theme: ThemeName;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeValue | null>(null);

function initialTheme(): ThemeName {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Set before React renders, so components that read CSS variables see the new theme. */
function applyTheme(theme: ThemeName): void {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(STORAGE_KEY, theme);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeName>(() => {
    const value = initialTheme();
    applyTheme(value);
    return value;
  });
  const value = useMemo<ThemeValue>(
    () => ({
      theme,
      toggle: () => {
        const next = theme === "light" ? "dark" : "light";
        applyTheme(next);
        setTheme(next);
      },
    }),
    [theme],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeValue {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme outside ThemeProvider");
  return value;
}

/** Colours of the graph views, read from the CSS variables of the current theme. */
export interface Palette {
  slots: string[];
  other: string;
  surface: string;
  text: string;
  text2: string;
  muted: string;
  accent: string;
  edgeIntra: string;
  edgeCross: string;
  ring: string;
  onFill: string;
  onYellow: string;
  font: string;
}

export function readPalette(): Palette {
  const style = getComputedStyle(document.documentElement);
  const get = (name: string) => style.getPropertyValue(name).trim();
  return {
    slots: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => get(`--series-${i}`)),
    other: get("--series-other"),
    surface: get("--surface"),
    text: get("--text"),
    text2: get("--text-2"),
    muted: get("--muted"),
    accent: get("--accent"),
    edgeIntra: get("--edge-intra"),
    edgeCross: get("--edge-cross"),
    ring: get("--ring-interface"),
    onFill: "#ffffff",
    onYellow: "#0b0b0b",
    font: get("--font-sans"),
  };
}

export function slotColor(palette: Palette, slot: number): string {
  return slot >= 0 && slot < palette.slots.length ? palette.slots[slot] : palette.other;
}
