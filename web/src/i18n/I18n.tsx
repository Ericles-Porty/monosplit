import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import { messages, type Lang, type Messages } from "./messages";

const STORAGE_KEY = "monosplit.lang";

export interface Formatters {
  /** Decimal number with a fixed number of digits, in the interface language. */
  number: (value: number | null | undefined, digits?: number) => string;
  integer: (value: number | null | undefined) => string;
  /** A duration in seconds, as "45 s", "12 min" or "3 h 05 min". */
  duration: (seconds: number | null | undefined) => string;
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, "0")} min`;
}

interface I18nValue {
  lang: Lang;
  t: Messages;
  fmt: Formatters;
  setLang: (lang: Lang) => void;
}

const I18nContext = createContext<I18nValue | null>(null);

function initialLang(): Lang {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "pt" || stored === "en") return stored;
  return navigator.language.toLowerCase().startsWith("pt") ? "pt" : "en";
}

function applyLang(lang: Lang): void {
  document.documentElement.lang = messages[lang].meta.locale;
  localStorage.setItem(STORAGE_KEY, lang);
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const value = initialLang();
    applyLang(value);
    return value;
  });

  const value = useMemo<I18nValue>(() => {
    const t = messages[lang];
    const formats = new Map<number, Intl.NumberFormat>();
    const decimal = (digits: number) => {
      let format = formats.get(digits);
      if (!format) {
        format = new Intl.NumberFormat(t.meta.locale, { minimumFractionDigits: digits, maximumFractionDigits: digits });
        formats.set(digits, format);
      }
      return format;
    };
    const integer = new Intl.NumberFormat(t.meta.locale, { maximumFractionDigits: 0 });
    return {
      lang,
      t,
      fmt: {
        number: (v, digits = 3) => (v === null || v === undefined || Number.isNaN(v) ? t.common.dash : decimal(digits).format(v)),
        integer: (v) => (v === null || v === undefined ? t.common.dash : integer.format(v)),
        duration: (v) => (v === null || v === undefined || Number.isNaN(v) ? t.common.dash : formatDuration(v)),
      },
      setLang: (next: Lang) => {
        applyLang(next);
        setLangState(next);
      },
    };
  }, [lang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n outside I18nProvider");
  return value;
}
