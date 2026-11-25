import type {
  ControlKey,
  DifferenceSummary,
  IndexPayload,
  MetricKey,
  MetricSummary,
  ResultApp,
  ResultsPayload,
  Summary,
} from "../../api/types";

export const METRICS: MetricKey[] = ["sm", "ifn", "icp", "ned"];
export const CONTROLS: ControlKey[] = ["ah", "random"];

/** One (experiment, profile) pair: the unit of the Results page, across applications. */
export interface ResultSet {
  id: string;
  experiment: string;
  profile: string;
  apps: string[];
  evaluated: boolean;
  fake: boolean;
}

export function resultSets(index: IndexPayload): ResultSet[] {
  const sets = new Map<string, ResultSet>();
  for (const study of index.studies) {
    const id = `${study.experiment}/${study.profile}`;
    const set = sets.get(id) ?? { id, experiment: study.experiment, profile: study.profile, apps: [], evaluated: false, fake: false };
    set.apps.push(study.app);
    set.evaluated ||= study.evaluated;
    set.fake ||= study.provider === "fake";
    sets.set(id, set);
  }
  // Experiments with real models first, then dry runs; alphabetical inside each group.
  return [...sets.values()].sort((a, b) => Number(a.fake) - Number(b.fake) || a.id.localeCompare(b.id));
}

export type RowGroup = "treatment" | "controls" | "other" | "references";

export interface MethodRow {
  method: string;
  group: RowGroup;
}

/** Rows of the distribution figure: LLM, selected AH, random, other AH variants (optional), HDBSCAN. */
export function figureMethods(data: ResultsPayload, app: ResultApp, allAh: boolean): MethodRow[] {
  const present = new Set(data.metrics.filter((r) => r.app === app.app).map((r) => r.method));
  const rows: MethodRow[] = [];
  if (present.has("llm")) rows.push({ method: "llm", group: "treatment" });
  if (app.ah_selected && present.has(app.ah_selected)) rows.push({ method: app.ah_selected, group: "controls" });
  if (present.has("random")) rows.push({ method: "random", group: "controls" });
  if (allAh) {
    const others = [...present].filter((m) => m.startsWith("ah:") && m !== app.ah_selected);
    const order = app.ah_selection.map((s) => s.variant);
    others.sort((a, b) => order.indexOf(a) - order.indexOf(b) || a.localeCompare(b));
    rows.push(...others.map((method) => ({ method, group: "other" as const })));
  }
  rows.push(
    ...[...present]
      .filter((m) => m.startsWith("hdbscan:"))
      .sort()
      .map((method) => ({ method, group: "references" as const })),
  );
  return rows;
}

export function metricSummary(data: ResultsPayload, app: string, variant: string, method: string, metric: MetricKey | "k"): MetricSummary | undefined {
  return data.metric_summaries.find((s) => s.app === app && s.variant === variant && s.method === method && s.metric === metric);
}

export function differenceSummary(data: ResultsPayload, scope: string, variant: string, control: ControlKey, metric: MetricKey): DifferenceSummary | undefined {
  return data.difference_summaries.find((s) => s.scope === scope && s.variant === variant && s.control === control && s.metric === metric);
}

/** Applications that belong to a scope ("all" or one application id). */
export function scopeApps(data: ResultsPayload, scope: string): string[] {
  return scope === "all" ? data.apps.map((a) => a.app) : [scope];
}

/** "median [Q1; Q3]", the cell format of report.md. */
export function summaryCell(summary: Summary | undefined | null, format: (value: number) => string): string {
  if (!summary) return "";
  return `${format(summary.median)} [${format(summary.q1)}; ${format(summary.q3)}]`;
}

/** Decimal places for K: none when every value is an integer. */
export function kDigits(summary: Summary): number {
  return [summary.median, summary.q1, summary.q3].every(Number.isInteger) ? 0 : 1;
}

/** "missing_class=2; unknown_class=1" -> [["missing_class", 2], ["unknown_class", 1]] */
export function parseReasons(text: string): [string, number][] {
  return text
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const [reason, count] = part.split("=");
      return [reason.trim(), Number(count)] as [string, number];
    });
}
