import type { Decomposition } from "../../api/types";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";
import type { HelpKey } from "../../i18n/messages-help";
import { methodLabel } from "../../lib/methods";

export interface PaneEntry {
  method: string;
  decomposition: Decomposition | undefined;
}

type Column = { key: "k" | "sm" | "ifn" | "icp" | "ned" | "cross" | "interfaces"; better: "max" | "min" | null };

const COLUMNS: Column[] = [
  { key: "k", better: null },
  { key: "sm", better: "max" },
  { key: "ifn", better: "min" },
  { key: "icp", better: "min" },
  { key: "ned", better: "min" },
  { key: "cross", better: null },
  { key: "interfaces", better: null },
];

const HELP: Record<Column["key"], HelpKey> = {
  k: "k",
  sm: "sm",
  ifn: "ifn",
  icp: "icp",
  ned: "ned",
  cross: "crossCalls",
  interfaces: "interfaces",
};

function value(d: Decomposition, key: Column["key"]): number | null {
  if (key === "k") return d.k;
  if (key === "cross") return d.cross_calls;
  if (key === "interfaces") return d.interfaces.length;
  return d.metrics[key];
}

/** Metric values of the panes; the best value of each metric is bold when the panes differ. */
export function MetricsTable({ panes, ahSelected }: { panes: PaneEntry[]; ahSelected: string | null }) {
  const { t, fmt } = useI18n();
  const present = panes.filter((p): p is { method: string; decomposition: Decomposition } => Boolean(p.decomposition));
  const best = new Map<string, number>();
  for (const column of COLUMNS) {
    if (!column.better) continue;
    const values = present.map((p) => value(p.decomposition, column.key)).filter((v): v is number => v !== null);
    if (new Set(values).size > 1) best.set(column.key, column.better === "max" ? Math.max(...values) : Math.min(...values));
  }
  const header = (column: Column) => {
    if (column.key === "cross") return t.metrics.crossCalls;
    if (column.key === "interfaces") return t.metrics.interfaces;
    return t.metrics[column.key];
  };
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th>
              <Term k="panel">{t.decompositions.panel}</Term>
            </th>
            <th>
              <Term k="method">{t.decompositions.method}</Term>
            </th>
            {COLUMNS.map((column) => (
              <th key={column.key} className="num">
                <Term k={HELP[column.key]}>{header(column)}</Term>
                {column.better ? <span className="direction">{column.better === "max" ? `↑ ${t.metrics.higher}` : `↓ ${t.metrics.lower}`}</span> : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {panes.map((pane, index) => (
            <tr key={index}>
              <td>{index + 1}</td>
              <td>{methodLabel(t, pane.method, ahSelected)}</td>
              {COLUMNS.map((column) => {
                if (!pane.decomposition) return <td key={column.key} className="num">{t.common.dash}</td>;
                const v = value(pane.decomposition, column.key);
                const integer = column.key === "k" || column.key === "cross" || column.key === "interfaces";
                const isBest = best.get(column.key) === v && v !== null;
                return (
                  <td key={column.key} className={isBest ? "num best" : "num"}>
                    {integer ? fmt.integer(v) : fmt.number(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
