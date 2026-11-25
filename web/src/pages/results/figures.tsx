import { useMemo, useRef, useState, type ReactNode } from "react";

import type { ResultApp, ResultsPayload } from "../../api/types";
import { PRINT_PALETTE, methodColor, readChartPalette, type ChartPalette } from "../../charts/palette";
import { StripFigure, type LegendEntry, type StripFigureProps, type StripPanel, type StripRow } from "../../charts/StripFigure";
import { useWidth } from "../../charts/useWidth";
import { Term } from "../../components/Term";
import { downloadBlob, downloadText, svgDocument, svgToPng } from "../../export/files";
import { useI18n, type Formatters } from "../../i18n/I18n";
import type { Messages } from "../../i18n/messages";
import { methodHelp, methodLabel } from "../../lib/methods";
import { useTheme } from "../../theme/Theme";
import { CONTROLS, METRICS, differenceSummary, figureMethods, metricSummary, scopeApps } from "./data";

export type FigureSpec = Omit<StripFigureProps, "palette" | "width" | "interactive" | "svgRef" | "title" | "columns">;
export type SpecBuilder = (palette: ChartPalette) => FigureSpec;

/**
 * Exported figures: two panels per row, 900 px wide. At the text width of an article
 * (about 16 cm) the 12 px labels print at about 8 pt.
 */
export const EXPORT_WIDTH = 900;
const EXPORT_COLUMNS = 2;

// ---------------------------------------------------------------- figure specs

function arrow(t: Messages, direction: number): string {
  return direction > 0 ? `↑ ${t.metrics.higher}` : `↓ ${t.metrics.lower}`;
}

export function distributionSpec(t: Messages, fmt: Formatters, data: ResultsPayload, app: ResultApp, variant: string, allAh: boolean): SpecBuilder {
  const r = t.results.distributions;
  const methods = figureMethods(data, app, allAh);
  const groups = { treatment: r.groupTreatment, controls: r.groupControls, other: r.groupOther, references: r.groupReferences };
  return (palette) => {
    const rows: StripRow[] = methods.map(({ method, group }) => ({
      key: method,
      label: methodLabel(t, method),
      group: groups[group],
      color: methodColor(palette, method, app.ah_selected),
      shape: group === "references" ? "diamond" : "dot",
      strong: method === "llm",
    }));
    const panels: StripPanel[] = METRICS.map((metric) => ({
      key: metric,
      title: t.metrics[metric],
      subtitle: `${t.metrics.names[metric]} · ${arrow(t, data.analysis.direction[metric])}`,
    }));
    const cells = METRICS.map((metric) =>
      methods.map(({ method, group }) => {
        const label = methodLabel(t, method);
        const reference = group === "references";
        const values = data.metrics.filter(
          (row) => row.app === app.app && row.method === method && (reference ? row.variant === null : row.variant === variant),
        );
        return {
          points: values
            .filter((row) => row[metric] !== null)
            .map((row) => ({
              value: row[metric] as number,
              tip: reference ? r.referenceTip(label, row.k) : r.pointTip(label, row.run ?? 0, row.k),
            })),
          summary: reference ? null : (metricSummary(data, app.app, variant, method, metric) ?? null),
        };
      }),
    );
    const h = t.help;
    const keyed: [LegendEntry, string][] = [
      [{ label: r.legendLlm, color: palette.llm, mark: "dot" }, h.llm.text],
      [{ label: r.legendAh, color: palette.ah, mark: "dot" }, h.ahSelected.text],
      [{ label: r.legendRandom, color: palette.random, mark: "dot" }, h.random.text],
      ...(methods.some((m) => m.group === "other")
        ? [[{ label: r.legendOtherAh, color: palette.other, mark: "dot" as const }, h.otherAh.text] as [LegendEntry, string]]
        : []),
      ...(methods.some((m) => m.group === "references")
        ? [[{ label: r.legendHdbscan, color: palette.other, mark: "diamond" as const }, h.hdbscan.text] as [LegendEntry, string]]
        : []),
      [{ label: r.legendIqr, color: palette.text2, mark: "band" }, h.q1q3.text],
      [{ label: r.legendMedian, color: palette.text, mark: "median" }, h.median.text],
    ];
    return {
      panels,
      rows,
      cells,
      legend: keyed.map(([entry]) => entry),
      format: (value, digits) => fmt.number(value, digits),
      summaryTip: (summary) => r.summaryTip(summary.n),
      label: r.figureTitle(app.name, t.variants[variant] ?? variant),
      notes: {
        panels: METRICS.map((metric) => h[metric].text),
        rows: methods.map(({ method }) => h[methodHelp(method, app.ah_selected)].text),
        legend: keyed.map(([, note]) => note),
      },
    };
  };
}

export function differenceSpec(t: Messages, fmt: Formatters, data: ResultsPayload, scope: string, variant: string, scopeLabel: string): SpecBuilder {
  const d = t.results.differences;
  const apps = scopeApps(data, scope);
  const names = new Map(data.apps.map((a) => [a.app, a.name]));
  return (palette) => {
    const color = { ah: palette.ah, random: palette.random };
    const rows: StripRow[] = CONTROLS.map((control) => ({ key: control, label: d.controlLabel[control], group: "", color: color[control], shape: "dot" }));
    const panels: StripPanel[] = METRICS.map((metric) => ({
      key: metric,
      title: `d ${t.metrics[metric]}`,
      subtitle: t.metrics.names[metric],
      includeZero: true,
      favour: { side: data.analysis.direction[metric] > 0 ? "right" : "left", text: d.favoursLlm },
    }));
    const cells = METRICS.map((metric) =>
      CONTROLS.map((control) => {
        const key = `d_${metric}` as const;
        return {
          points: data.differences
            .filter((row) => apps.includes(row.app) && row.variant === variant && row.control === control && row[key] !== null)
            .map((row) => ({ value: row[key] as number, tip: d.pointTip(names.get(row.app) ?? row.app, row.run, row.k) })),
          summary: differenceSummary(data, scope, variant, control, metric) ?? null,
        };
      }),
    );
    const h = t.help;
    const legend: LegendEntry[] = [
      { label: d.controlLabel.ah, color: palette.ah, mark: "dot" },
      { label: d.controlLabel.random, color: palette.random, mark: "dot" },
      { label: t.results.distributions.legendIqr, color: palette.text2, mark: "band" },
      { label: t.results.distributions.legendMedian, color: palette.text, mark: "median" },
    ];
    return {
      panels,
      rows,
      cells,
      legend,
      format: (value, digits) => fmt.number(value, digits),
      summaryTip: (summary) => t.results.distributions.summaryTip(summary.n),
      label: d.figureTitle(scopeLabel, t.variants[variant] ?? variant),
      notes: {
        panels: METRICS.map((metric) => `${h[metric].text} ${h.pairedDifference.text}`),
        rows: CONTROLS.map(() => h.pairedDifference.text),
        legend: [h.ahSelected.text, h.random.text, h.q1q3.text, h.median.text],
      },
    };
  };
}

// ---------------------------------------------------------------- export

async function figureSvg(build: SpecBuilder, title: string): Promise<string> {
  const { renderToStaticMarkup } = await import("react-dom/server");
  const markup = renderToStaticMarkup(
    <StripFigure {...build(PRINT_PALETTE)} palette={PRINT_PALETTE} width={EXPORT_WIDTH} columns={EXPORT_COLUMNS} title={title} />,
  );
  return svgDocument(markup);
}

function svgSize(svg: string): { width: number; height: number } {
  const match = /<svg[^>]*?\swidth="([\d.]+)"[^>]*?\sheight="([\d.]+)"/.exec(svg);
  return { width: Number(match?.[1] ?? EXPORT_WIDTH), height: Number(match?.[2] ?? 600) };
}

export interface ExportAction {
  label: string;
  run: () => void | Promise<void>;
  /** Short confirmation shown after the action, e.g. "Copied". */
  done?: string;
}

export function ExportBar({ actions }: { actions: ExportAction[] }) {
  const { t } = useI18n();
  const [status, setStatus] = useState<string | null>(null);
  const click = async (action: ExportAction) => {
    try {
      await action.run();
      setStatus(action.done ?? null);
    } catch (error) {
      setStatus(`${t.results.export.failed}: ${error instanceof Error ? error.message : String(error)}`);
    }
    if (action.done) setTimeout(() => setStatus(null), 2000);
  };
  if (!actions.length) return null;
  return (
    <div className="export-bar">
      <span className="export-label">
        <Term k="export">{t.results.export.label}</Term>
      </span>
      {actions.map((action) => (
        <button key={action.label} type="button" className="button small" onClick={() => click(action)}>
          {action.label}
        </button>
      ))}
      {status ? <span className="note" role="status">{status}</span> : null}
    </div>
  );
}

/** Text actions shared by figures and tables: CSV, LaTeX and LaTeX to the clipboard. */
export function tableActions(t: Messages, fileBase: string, csv: () => string, latex?: () => string): ExportAction[] {
  const e = t.results.export;
  const actions: ExportAction[] = [{ label: e.csv, run: () => downloadText(`${fileBase}.csv`, csv(), "text/csv") }];
  if (latex) {
    actions.push({ label: e.latex, run: () => downloadText(`${fileBase}.tex`, latex(), "application/x-tex") });
    actions.push({
      label: e.copyLatex,
      done: e.copied,
      run: async () => {
        if (!navigator.clipboard) throw new Error("clipboard unavailable");
        await navigator.clipboard.writeText(latex());
      },
    });
  }
  return actions;
}

export function FigureBlock(props: { title: string; build: SpecBuilder; fileBase: string; actions?: ExportAction[]; children?: ReactNode }) {
  const { t } = useI18n();
  const { theme } = useTheme();
  const palette = useMemo(() => readChartPalette(), [theme]);
  const frame = useRef<HTMLDivElement>(null);
  const width = useWidth(frame);
  const spec = props.build(palette);
  const e = t.results.export;
  const figureActions: ExportAction[] = [
    {
      label: e.svg,
      run: async () => downloadText(`${props.fileBase}.svg`, await figureSvg(props.build, props.title), "image/svg+xml"),
    },
    {
      label: e.png,
      run: async () => {
        const svg = await figureSvg(props.build, props.title);
        const size = svgSize(svg);
        downloadBlob(`${props.fileBase}.png`, await svgToPng(svg, size.width, size.height, 2));
      },
    },
  ];
  return (
    <div className="figure-block">
      <div className="figure-head">
        <h3>{props.title}</h3>
        <ExportBar actions={[...(props.actions ?? []), ...figureActions]} />
      </div>
      <div ref={frame} className="figure-frame">
        {width > 0 ? <StripFigure {...spec} palette={palette} width={width} interactive /> : null}
      </div>
      {props.children}
    </div>
  );
}
