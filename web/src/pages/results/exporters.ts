// CSV and LaTeX versions of the Results tables. CSV keeps every value at full precision;
// LaTeX follows the cells of report.md (median [Q1; Q3]) in the interface language.

import type { ResultApp, ResultsPayload, TestSet } from "../../api/types";
import { toCsv } from "../../export/files";
import { escapeLatex, latexNumber, latexTable } from "../../export/latex";
import type { Formatters } from "../../i18n/I18n";
import type { Messages } from "../../i18n/messages";
import { methodLabel } from "../../lib/methods";
import { CONTROLS, METRICS, differenceSummary, figureMethods, kDigits, metricSummary, scopeApps } from "./data";

export interface ExportContext {
  t: Messages;
  fmt: Formatters;
  data: ResultsPayload;
  /** "experiment study, profile gpt-…", used in captions. */
  setLabel: string;
  /** First line of every .tex file. */
  source: string;
}

function slug(...parts: string[]): string {
  return parts.join("-").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

/** Method name for a table cell: "AH, neighbours, complete linkage" instead of the interface's middle dots. */
function methodText(t: Messages, method: string): string {
  return escapeLatex(methodLabel(t, method).replace(/ · /g, ", "));
}

function variantText(t: Messages, variant: string): string {
  return (t.variants[variant] ?? variant).toLowerCase();
}

/** p-value cell: three decimals, or "< 0.001". */
export function formatP(fmt: Formatters, p: number | null): string {
  if (p === null) return "—";
  return p < 0.001 ? `< ${fmt.number(0.001, 3)}` : fmt.number(p, 3);
}

// ---------------------------------------------------------------- metrics by method

export function metricsCsv(data: ResultsPayload, app: string, variant: string): string {
  const rows = data.metrics.filter((r) => r.app === app && (r.variant === variant || r.variant === null));
  return toCsv(
    ["experiment", "profile", "app", "variant", "run", "method", "k", "sm", "ifn", "icp", "ned", "seed", "noise_points"],
    rows.map((r) => ({ ...r, experiment: data.experiment, profile: data.profile, variant: r.variant ?? "" })),
  );
}

export function metricsLatex(c: ExportContext, app: ResultApp, variant: string, allAh: boolean): string {
  const { t, fmt, data } = c;
  const methods = figureMethods(data, app, allAh);
  const num = (value: number, digits = 3) => latexNumber(fmt.number(value, digits));
  const cell = (method: string, metric: "k" | (typeof METRICS)[number]): string => {
    if (method.startsWith("hdbscan:")) {
      const row = data.metrics.find((r) => r.app === app.app && r.method === method && r.variant === null);
      const value = row?.[metric];
      return value === null || value === undefined ? "" : num(value, metric === "k" ? 0 : 3);
    }
    const s = metricSummary(data, app.app, variant, method, metric);
    if (!s) return "";
    const digits = metric === "k" ? kDigits(s) : 3;
    return `${num(s.median, digits)} [${num(s.q1, digits)}; ${num(s.q3, digits)}]`;
  };
  const groupStarts = methods.map((m, i) => (i > 0 && methods[i - 1].group !== m.group ? i : -1)).filter((i) => i > 0);
  const llm = metricSummary(data, app.app, variant, "llm", "sm");
  return latexTable({
    source: c.source,
    caption: t.results.distributions.caption(app.name, variantText(t, variant), c.setLabel, String(llm?.n ?? "")),
    label: `tab:${slug(data.experiment, app.app, variant, "metrics")}`,
    align: "lrrrrr",
    header: [
      t.results.distributions.method,
      "K",
      ...METRICS.map((m) => `${t.metrics[m]} ${data.analysis.direction[m] > 0 ? "↑" : "↓"}`),
    ],
    rows: methods.map(({ method }) => [methodText(t, method), cell(method, "k"), ...METRICS.map((m) => cell(method, m))]),
    groupStarts,
  });
}

// ---------------------------------------------------------------- paired differences

export function differencesCsv(data: ResultsPayload, scope: string, variant: string): string {
  const apps = scopeApps(data, scope);
  return toCsv(
    ["experiment", "profile", "app", "variant", "run", "control", "control_method", "k", "d_sm", "d_ifn", "d_icp", "d_ned"],
    data.differences
      .filter((d) => apps.includes(d.app) && d.variant === variant)
      .map((d) => ({ ...d, experiment: data.experiment, profile: data.profile })),
  );
}

export function differencesLatex(c: ExportContext, scope: string, variant: string, scopeLabel: string): string {
  const { t, fmt, data } = c;
  const d = t.results.differences;
  const st = t.results.stats;
  const num = (value: number) => latexNumber(fmt.number(value, 3));
  const rows: string[][] = [];
  for (const control of CONTROLS) {
    for (const metric of METRICS) {
      const s = differenceSummary(data, scope, variant, control, metric);
      if (!s) continue;
      rows.push([
        escapeLatex(d.controlLabel[control]),
        escapeLatex(t.metrics[metric]),
        String(s.n),
        num(s.median),
        num(s.q1),
        num(s.q3),
        num(s.min),
        num(s.max),
        `${s.positive} / ${s.negative} / ${s.zero}`,
      ]);
    }
  }
  const groupStarts = rows.map((row, i) => (i > 0 && rows[i - 1][0] !== row[0] ? i : -1)).filter((i) => i > 0);
  return latexTable({
    source: c.source,
    caption: d.caption(scopeLabel, variantText(t, variant), c.setLabel),
    label: `tab:${slug(data.experiment, scope, variant, "differences")}`,
    align: "llrrrrrrc",
    header: [d.control, d.metric, st.n, st.median, st.q1, st.q3, st.min, st.max, d.signs],
    rows,
    groupStarts,
  });
}

// ---------------------------------------------------------------- tests

export function testsCsv(data: ResultsPayload, set: TestSet): string {
  return toCsv(
    ["experiment", "profile", "scope", "variant", "control", "metric", "n", "n_nonzero", "normality_p", "normal", "test",
      "statistic", "p_value", "p_holm", "significant", "median_diff", "mean_diff", "cliffs_delta", "magnitude", "favours"],
    set.comparisons.map((row) => ({ ...row, experiment: data.experiment, profile: data.profile, scope: set.scope, variant: set.variant })),
  );
}

export function testsLatex(c: ExportContext, set: TestSet, scopeLabel: string): string {
  const { t, fmt, data } = c;
  const x = t.results.tests;
  const num = (value: number | null, digits = 3) => (value === null ? "--" : latexNumber(fmt.number(value, digits)));
  const p = (value: number | null) => (value === null ? "--" : escapeLatex(formatP(fmt, value)));
  const rows = set.comparisons.map((row) => [
    escapeLatex(t.results.differences.controlLabel[row.control]),
    escapeLatex(t.metrics[row.metric]),
    String(row.n),
    p(row.normality_p),
    escapeLatex(x.testNames[row.test] ?? row.test),
    num(row.statistic, 3),
    p(row.p_value),
    p(row.p_holm),
    num(row.cliffs_delta, 3),
    escapeLatex(row.magnitude ? (x.magnitudes[row.magnitude] ?? row.magnitude) : "--"),
  ]);
  const groupStarts = rows.map((row, i) => (i > 0 && rows[i - 1][0] !== row[0] ? i : -1)).filter((i) => i > 0);
  return latexTable({
    source: c.source,
    caption: x.caption(scopeLabel, variantText(t, set.variant), c.setLabel),
    label: `tab:${slug(data.experiment, set.scope, set.variant, "tests")}`,
    align: "llrrlrrrrl",
    header: [x.cols.control, x.cols.metric, x.cols.n, x.cols.normality, x.cols.test, x.cols.statistic, x.cols.p, x.cols.pHolm, x.cols.delta, x.cols.magnitude],
    rows,
    groupStarts,
  });
}
