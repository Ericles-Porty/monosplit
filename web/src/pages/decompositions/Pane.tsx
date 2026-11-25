import type { ReactNode } from "react";

import type { ClassInfo, Decomposition, GraphPayload } from "../../api/types";
import { Swatch } from "../../components/Swatch";
import { Term } from "../../components/Term";
import type { LayoutMode } from "../../graph/elements";
import { GraphPane, type HoverTarget } from "../../graph/GraphPane";
import type { ViewportSync } from "../../graph/viewportSync";
import { useI18n } from "../../i18n/I18n";
import { methodGroup, methodHelp, methodLabel } from "../../lib/methods";
import type { Palette } from "../../theme/Theme";

export interface PaneProps {
  index: number;
  method: string;
  methods: string[];
  ahSelected: string | null;
  onMethod: (method: string) => void;
  graph: GraphPayload;
  decomposition: Decomposition | undefined;
  slots: number[];
  palette: Palette;
  mode: LayoutMode;
  crossOnly: boolean;
  classLabel: (info: ClassInfo) => string;
  serviceLabel: (serviceIndex: number) => string;
  collapsed: ReadonlySet<number>;
  onCollapsed: (next: ReadonlySet<number>) => void;
  focusService: number | null;
  onFocus: (service: number | null) => void;
  hovered: string | null;
  selected: string | null;
  changed: ReadonlySet<string>;
  sync: ViewportSync | null;
  fitSignal: number;
  onFit: () => void;
  onHover: (classId: string | null) => void;
  onSelect: (classId: string | null) => void;
  tooltip: (target: HoverTarget, decomposition: Decomposition, slots: number[]) => ReactNode;
}

export function Pane(props: PaneProps) {
  const { t, fmt } = useI18n();
  const { decomposition: d, slots, palette } = props;
  const groups = (["treatment", "controls", "references"] as const).map((group) => ({
    group,
    label: { treatment: t.methods.groupTreatment, controls: t.methods.groupControls, references: t.methods.groupReferences }[group],
    methods: props.methods.filter((m) => methodGroup(m) === group),
  }));

  const toggleCollapse = (service: number) => {
    const next = new Set(props.collapsed);
    if (next.has(service)) next.delete(service);
    else next.add(service);
    props.onCollapsed(next);
  };
  const services = d ? [...d.services].sort((a, b) => slots[a.index] - slots[b.index]) : [];

  return (
    <section className="pane" aria-label={t.decompositions.pane(props.index + 1)}>
      <div className="pane-head">
        <span className="pane-number">
          <Term k="panel">{t.decompositions.pane(props.index + 1)}</Term>
        </span>
        <select
          aria-label={`${t.decompositions.pane(props.index + 1)}: ${t.decompositions.method}`}
          value={props.method}
          onChange={(event) => props.onMethod(event.target.value)}
        >
          {!props.methods.includes(props.method) ? <option value={props.method}>{methodLabel(t, props.method, props.ahSelected)}</option> : null}
          {groups
            .filter((g) => g.methods.length)
            .map((g) => (
              <optgroup key={g.group} label={g.label}>
                {g.methods.map((m) => (
                  <option key={m} value={m}>
                    {methodLabel(t, m, props.ahSelected)}
                  </option>
                ))}
              </optgroup>
            ))}
        </select>
      </div>

      {d ? (
        <>
          <div className="pane-summary">
            <span>
              <Term k={methodHelp(props.method, props.ahSelected)}>{t.decompositions.method}</Term>
            </span>
            <span>
              <Term k="k">{t.metrics.k}</Term> <strong>{d.k}</strong>
            </span>
            <span>
              <Term k="sm">{t.metrics.sm}</Term> <strong>{fmt.number(d.metrics.sm)}</strong>
            </span>
            <span>
              <Term k="ifn">{t.metrics.ifn}</Term> <strong>{fmt.number(d.metrics.ifn)}</strong>
            </span>
            <span>
              <Term k="icp">{t.metrics.icp}</Term> <strong>{fmt.number(d.metrics.icp)}</strong>
            </span>
            <span>
              <Term k="ned">{t.metrics.ned}</Term> <strong>{fmt.number(d.metrics.ned)}</strong>
            </span>
          </div>
          <div style={{ position: "relative" }}>
            <div className="graph-tools">
              {props.mode === "grouped" ? (
                <>
                  <button type="button" className="icon-button" onClick={() => props.onCollapsed(new Set(d.services.map((s) => s.index)))}>
                    {t.decompositions.collapseAll}
                  </button>
                  <button type="button" className="icon-button" onClick={() => props.onCollapsed(new Set())} disabled={props.collapsed.size === 0}>
                    {t.decompositions.expandAll}
                  </button>
                </>
              ) : null}
              <button type="button" className="icon-button" onClick={props.onFit} title="Fit">
                ⤢
              </button>
            </div>
            <GraphPane
              paneId={`pane-${props.index}`}
              graph={props.graph}
              decomposition={d}
              slots={slots}
              palette={palette}
              mode={props.mode}
              crossOnly={props.crossOnly}
              showTags={props.mode === "fixed" && d.k > 3}
              classLabel={props.classLabel}
              serviceLabel={props.serviceLabel}
              collapsed={props.collapsed}
              hovered={props.hovered}
              selected={props.selected}
              focusService={props.focusService}
              changed={props.method === "llm" ? props.changed : EMPTY}
              sync={props.sync}
              fitSignal={props.fitSignal}
              onHover={props.onHover}
              onSelect={props.onSelect}
              onToggleCollapse={toggleCollapse}
              tooltip={(target) => props.tooltip(target, d, slots)}
            />
          </div>
          <div className="legend">
            <span className="legend-title">
              <Term k="services">{t.decompositions.legendTitle}</Term>
            </span>
            <ul className="legend-list" aria-label={t.decompositions.legendTitle}>
              {services.map((service) => (
                <li key={service.index}>
                  <button
                    type="button"
                    className="legend-item"
                    aria-pressed={props.focusService === service.index}
                    onClick={() => props.onFocus(props.focusService === service.index ? null : service.index)}
                    onDoubleClick={() => (props.mode === "grouped" ? toggleCollapse(service.index) : undefined)}
                  >
                    <Swatch palette={palette} slot={slots[service.index]} />
                    <span className="legend-name">{props.serviceLabel(service.index)}</span>
                    <span className="legend-meta">
                      {t.decompositions.legendSize(service.size)} · {t.decompositions.legendInterfaces(service.interfaces.length)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : (
        <div className="graph-wrap">
          <p className="graph-message">{t.decompositions.unavailable}</p>
        </div>
      )}
    </section>
  );
}

const EMPTY: ReadonlySet<string> = new Set();
