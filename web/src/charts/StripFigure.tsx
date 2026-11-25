import { useState, type Ref } from "react";

import type { Summary } from "../api/types";
import type { ChartPalette } from "./palette";
import { linear, niceAxis, stackOffsets, type Axis } from "./scale";

// Small multiples of horizontal strip plots: one panel per metric, one row per method (or
// control), one dot per run, with the interquartile band and the median of each row. The
// same component draws the page view (interactive) and the exported SVG (static).

export interface StripPoint {
  value: number;
  /** Second line of the tooltip; the first line is the value. */
  tip: string;
}

export interface StripCell {
  points: StripPoint[];
  summary: Summary | null;
}

export interface StripRow {
  key: string;
  label: string;
  group: string;
  color: string;
  shape: "dot" | "diamond";
  strong?: boolean;
}

export interface StripPanel {
  key: string;
  title: string;
  subtitle: string;
  includeZero?: boolean;
  /** Side of the axis where the LLM is better, for differences. */
  favour?: { side: "left" | "right"; text: string } | null;
}

export interface LegendEntry {
  label: string;
  color: string;
  mark: "dot" | "diamond" | "median" | "band";
}

export interface StripFigureProps {
  panels: StripPanel[];
  rows: StripRow[];
  /** cells[panel][row] */
  cells: StripCell[][];
  legend: LegendEntry[];
  palette: ChartPalette;
  width: number;
  format: (value: number, digits: number) => string;
  summaryTip: (summary: Summary) => string;
  /** Drawn inside the SVG; used by exported figures. */
  title?: string;
  columns?: number;
  interactive?: boolean;
  label: string;
  svgRef?: Ref<SVGSVGElement>;
  /**
   * Explanations shown when the pointer is over a panel title, a row label or a legend
   * item (interactive figures only), in the order of panels, rows and legend.
   */
  notes?: { panels?: (string | null)[]; rows?: (string | null)[]; legend?: (string | null)[] };
}

const PAD = 12;
const GAP = 22;
const R = 4;
const FONT = 12;
const SMALL = 11;
const AXIS = 20;
const HINT = 16;
const GROUP = 18;
const ROW_MIN = 26;

/** Rough text width for layout; SVG text cannot be measured before it is in the page. */
export function textWidth(text: string, size = FONT): number {
  return text.length * size * 0.58;
}

function wrapWords(text: string, width: number, size: number): string[] {
  const lines: string[] = [];
  let line = "";
  for (const word of text.split(" ")) {
    const candidate = line ? `${line} ${word}` : word;
    if (line && textWidth(candidate, size) > width) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines;
}

/**
 * Lines no wider than `width`. Breaks go first at " · " (metric name, then direction),
 * then at spaces; a single long word keeps its own line.
 */
export function wrapText(text: string, width: number, size = SMALL): string[] {
  const lines: string[] = [];
  let line = "";
  for (const part of text.split(" · ")) {
    const candidate = line ? `${line} · ${part}` : part;
    if (textWidth(candidate, size) <= width) {
      line = candidate;
      continue;
    }
    if (line) lines.push(line);
    const words = wrapWords(part, width, size);
    line = words.pop() ?? "";
    lines.push(...words);
  }
  if (line) lines.push(line);
  return lines;
}

/** The axis with the most ticks whose labels do not touch at this width. */
function fitAxis(min: number, max: number, includeZero: boolean, width: number, format: (value: number, digits: number) => string): Axis {
  for (let count = Math.max(2, Math.floor(width / 45)); count > 2; count -= 1) {
    const axis = niceAxis(min, max, count, includeZero);
    const widest = Math.max(...axis.ticks.map((tick) => textWidth(format(tick, axis.digits), SMALL)));
    if ((width - 16) / Math.max(1, axis.ticks.length - 1) >= widest + 10) return axis;
  }
  return niceAxis(min, max, 2, includeZero);
}

interface Tip {
  x: number;
  y: number;
  value: string;
  label: string;
  /** An explanation (wraps, opens below the element) rather than a value. */
  note?: boolean;
}

interface LegendItemLayout {
  entry: LegendEntry;
  x: number;
  y: number;
}

function layoutLegend(entries: LegendEntry[], width: number): { items: LegendItemLayout[]; height: number } {
  const items: LegendItemLayout[] = [];
  let x = PAD;
  let y = 0;
  for (const entry of entries) {
    const w = 18 + textWidth(entry.label, SMALL) + 18;
    if (x + w > width - PAD && x > PAD) {
      x = PAD;
      y += 18;
    }
    items.push({ entry, x, y });
    x += w;
  }
  return { items, height: entries.length ? y + 18 + 8 : 0 };
}

function Mark({ entry, x, y, palette }: { entry: LegendEntry; x: number; y: number; palette: ChartPalette }) {
  if (entry.mark === "median") return <line x1={x + 6} x2={x + 6} y1={y - 6} y2={y + 6} stroke={palette.text} strokeWidth={2} strokeLinecap="round" />;
  if (entry.mark === "band") return <rect x={x} y={y - 4} width={14} height={8} rx={2} fill={entry.color} opacity={0.22} />;
  if (entry.mark === "diamond") return <path d={diamond(x + 6, y, 5)} fill={entry.color} />;
  return <circle cx={x + 6} cy={y} r={R} fill={entry.color} />;
}

function diamond(cx: number, cy: number, half: number): string {
  return `M${cx} ${cy - half}L${cx + half} ${cy}L${cx} ${cy + half}L${cx - half} ${cy}Z`;
}

export function StripFigure(props: StripFigureProps) {
  const { panels, rows, cells, palette, width, format } = props;
  const [tip, setTip] = useState<Tip | null>(null);
  const interactive = props.interactive ?? false;

  // ---------------------------------------------------------------- layout
  const labelW = Math.min(
    250,
    Math.max(96, ...rows.map((r) => textWidth(r.label, FONT) + (r.strong ? 6 : 0)), ...rows.map((r) => textWidth(r.group, SMALL))) + 14,
  );
  const fits = (columns: number) => (width - 2 * PAD - labelW - (columns - 1) * GAP) / columns;
  const columns = props.columns ?? (fits(4) >= 165 || panels.length < 4 ? Math.min(4, panels.length) : fits(2) >= 150 ? 2 : 1);
  const panelW = Math.max(120, fits(columns));
  const titleH = props.title ? 26 : 0;
  const legend = layoutLegend(props.legend, width);
  const hasHint = panels.some((p) => p.favour);

  const axes: Axis[] = panels.map((panel, p) => {
    const values = cells[p].flatMap((cell) => [
      ...cell.points.map((pt) => pt.value),
      ...(cell.summary ? [cell.summary.min, cell.summary.max] : []),
    ]);
    if (!values.length) return niceAxis(0, 1, 4, panel.includeZero);
    return fitAxis(Math.min(...values), Math.max(...values), panel.includeZero ?? false, panelW, format);
  });
  const subtitles = panels.map((panel) => wrapText(panel.subtitle, panelW, SMALL));
  const header = 20 + 13 * Math.max(1, ...subtitles.map((lines) => lines.length)) + 4;
  const scales = panels.map((_, p) => linear(axes[p].domain, [8, panelW - 8]));

  // Row heights: tall enough for the largest stack of dots in any panel.
  const stacks = panels.map((_, p) => rows.map((_, r) => stackOffsets(cells[p][r].points.map((pt) => scales[p](pt.value)), R)));
  const rowH = rows.map((_, r) => Math.max(ROW_MIN, ...stacks.map((s) => 2 * s[r].extent + 2 * R + 12)));
  const rowY: number[] = [];
  const groupY: { label: string; y: number }[] = [];
  let cursor = 0;
  rows.forEach((row, r) => {
    if (r === 0 || rows[r - 1].group !== row.group) {
      if (row.group) {
        groupY.push({ label: row.group, y: cursor });
        cursor += GROUP;
      } else if (r > 0) cursor += 8;
    }
    rowY.push(cursor + rowH[r] / 2);
    cursor += rowH[r];
  });
  const plotH = cursor;
  const blockH = header + plotH + AXIS + (hasHint ? HINT : 0);
  const blocks = Math.ceil(panels.length / columns);
  const top = titleH + legend.height;
  const height = top + blocks * blockH + (blocks - 1) * 18 + 6;

  const panelOrigin = (p: number) => {
    const block = Math.floor(p / columns);
    const column = p % columns;
    return { x: PAD + labelW + column * (panelW + GAP), y: top + block * (blockH + 18) };
  };

  const show = (event: { currentTarget: Element }, value: string, label: string) => {
    if (!interactive) return;
    const svg = (event.currentTarget as SVGElement).ownerSVGElement;
    const box = (event.currentTarget as SVGGraphicsElement).getBoundingClientRect();
    const frame = svg?.getBoundingClientRect();
    if (!frame) return;
    setTip({ x: box.left - frame.left + box.width / 2, y: box.top - frame.top, value, label });
  };
  const showNote = (event: { currentTarget: Element }, value: string, label: string) => {
    if (!interactive) return;
    const svg = (event.currentTarget as SVGElement).ownerSVGElement;
    const box = (event.currentTarget as SVGGraphicsElement).getBoundingClientRect();
    const frame = svg?.getBoundingClientRect();
    if (!frame) return;
    setTip({ x: box.left - frame.left, y: box.bottom - frame.top, value, label, note: true });
  };
  const hide = () => setTip(null);
  /** Transparent area over a text with an explanation. */
  const noteArea = (key: string, x: number, y: number, w: number, h: number, title: string, note: string | null | undefined) =>
    interactive && note ? (
      <rect
        key={key}
        x={x}
        y={y}
        width={w}
        height={h}
        fill="transparent"
        style={{ cursor: "help" }}
        onMouseEnter={(event) => showNote(event, title, note)}
        onMouseLeave={hide}
      />
    ) : null;

  const font = { fontFamily: palette.font };

  const svg = (
    <svg
      ref={props.svgRef}
      xmlns="http://www.w3.org/2000/svg"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="group"
      aria-label={props.label}
      style={interactive ? { display: "block", overflow: "visible" } : undefined}
      {...font}
    >
      <rect x={0} y={0} width={width} height={height} fill={palette.surface} />
      {props.title ? (
        <text x={PAD} y={17} fontSize={13} fontWeight={600} fill={palette.text}>
          {props.title}
        </text>
      ) : null}

      <g transform={`translate(0 ${titleH + 9})`}>
        {legend.items.map(({ entry, x, y }, i) => (
          <g key={entry.label}>
            <Mark entry={entry} x={x} y={y} palette={palette} />
            <text x={x + 18} y={y + 4} fontSize={SMALL} fill={palette.text2}>
              {entry.label}
            </text>
            {noteArea("note", x - 2, y - 9, 22 + textWidth(entry.label, SMALL), 18, entry.label, props.notes?.legend?.[i])}
          </g>
        ))}
      </g>

      {Array.from({ length: blocks }, (_, block) => {
        const y0 = top + block * (blockH + 18) + header;
        return (
          <g key={`labels-${block}`}>
            {groupY.map((g) => (
              <text key={g.label} x={PAD} y={y0 + g.y + 13} fontSize={SMALL} fill={palette.muted}>
                {g.label}
              </text>
            ))}
            {rows.map((row, r) => (
              <text key={row.key} x={PAD} y={y0 + rowY[r] + 4} fontSize={FONT} fontWeight={row.strong ? 600 : 400} fill={palette.text}>
                {row.label}
              </text>
            ))}
            {rows.map((row, r) =>
              noteArea(`note-${row.key}`, PAD - 2, y0 + rowY[r] - 9, textWidth(row.label, FONT) + 8, 18, row.label, props.notes?.rows?.[r]),
            )}
          </g>
        );
      })}

      {panels.map((panel, p) => {
        const origin = panelOrigin(p);
        const axis = axes[p];
        const x = scales[p];
        const plotTop = origin.y + header;
        const plotBottom = plotTop + plotH;
        return (
          <g key={panel.key} transform={`translate(${origin.x} 0)`}>
            <text x={0} y={origin.y + 13} fontSize={FONT} fontWeight={600} fill={palette.text}>
              {panel.title}
            </text>
            {subtitles[p].map((line, i) => (
              <text key={i} x={0} y={origin.y + 27 + i * 13} fontSize={SMALL} fill={palette.text2}>
                {line}
              </text>
            ))}
            {noteArea(
              "note",
              -2,
              origin.y,
              Math.min(panelW, Math.max(textWidth(panel.title, FONT), ...subtitles[p].map((line) => textWidth(line, SMALL))) + 6),
              header - 6,
              panel.title,
              props.notes?.panels?.[p],
            )}
            {axis.ticks.map((tick) => (
              <line key={tick} x1={x(tick)} x2={x(tick)} y1={plotTop} y2={plotBottom} stroke={palette.grid} strokeWidth={1} />
            ))}
            {panel.includeZero ? <line x1={x(0)} x2={x(0)} y1={plotTop} y2={plotBottom} stroke={palette.axis} strokeWidth={1.5} /> : null}
            <line x1={0} x2={panelW} y1={plotBottom} y2={plotBottom} stroke={palette.axis} strokeWidth={1} />
            {axis.ticks.map((tick, i) => (
              <text
                key={tick}
                x={x(tick)}
                y={plotBottom + 14}
                fontSize={SMALL}
                fill={palette.muted}
                textAnchor={i === 0 && x(tick) < 14 ? "start" : i === axis.ticks.length - 1 && x(tick) > panelW - 14 ? "end" : "middle"}
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {format(tick, axis.digits)}
              </text>
            ))}
            {panel.favour ? (
              <text
                x={panel.favour.side === "right" ? panelW : 0}
                y={plotBottom + AXIS + 11}
                fontSize={SMALL}
                fill={palette.text2}
                textAnchor={panel.favour.side === "right" ? "end" : "start"}
              >
                {panel.favour.side === "right" ? `${panel.favour.text} →` : `← ${panel.favour.text}`}
              </text>
            ) : null}

            {rows.map((row, r) => {
              const cell = cells[p][r];
              const cy = plotTop + rowY[r];
              const s = cell.summary;
              const offsets = stacks[p][r].offsets;
              return (
                <g key={row.key}>
                  {interactive && s ? (
                    <rect
                      x={0}
                      y={cy - rowH[r] / 2}
                      width={panelW}
                      height={rowH[r]}
                      fill="transparent"
                      tabIndex={0}
                      aria-label={`${row.label}, ${panel.title}: ${format(s.median, 3)} (${props.summaryTip(s)})`}
                      onMouseEnter={(event) => show(event, format(s.median, 3), `${row.label} · ${props.summaryTip(s)}`)}
                      onFocus={(event) => show(event, format(s.median, 3), `${row.label} · ${props.summaryTip(s)}`)}
                      onMouseLeave={hide}
                      onBlur={hide}
                    />
                  ) : null}
                  {s && s.q3 > s.q1 ? (
                    <rect x={x(s.q1)} y={cy - 4} width={Math.max(1, x(s.q3) - x(s.q1))} height={8} rx={2} fill={row.color} opacity={0.22} pointerEvents="none" />
                  ) : null}
                  {cell.points.map((point, i) =>
                    row.shape === "diamond" ? (
                      <path
                        key={i}
                        d={diamond(x(point.value), cy + offsets[i], 5.5)}
                        fill={row.color}
                        stroke={palette.surface}
                        strokeWidth={4}
                        paintOrder="stroke"
                        pointerEvents="none"
                      />
                    ) : (
                      <circle
                        key={i}
                        cx={x(point.value)}
                        cy={cy + offsets[i]}
                        r={R}
                        fill={row.color}
                        stroke={palette.surface}
                        strokeWidth={4}
                        paintOrder="stroke"
                        pointerEvents="none"
                      />
                    ),
                  )}
                  {s && s.n > 1 ? (
                    <line
                      x1={x(s.median)}
                      x2={x(s.median)}
                      y1={cy - rowH[r] / 2 + 3}
                      y2={cy + rowH[r] / 2 - 3}
                      stroke={palette.text}
                      strokeWidth={2}
                      strokeLinecap="round"
                      pointerEvents="none"
                    />
                  ) : null}
                  {interactive
                    ? cell.points.map((point, i) => (
                        <circle
                          key={`hit-${i}`}
                          cx={x(point.value)}
                          cy={cy + offsets[i]}
                          r={12}
                          fill="transparent"
                          onMouseEnter={(event) => show(event, format(point.value, 3), point.tip)}
                          onMouseLeave={hide}
                        />
                      ))
                    : null}
                </g>
              );
            })}
          </g>
        );
      })}
    </svg>
  );

  if (!interactive) return svg;
  return (
    <div className="strip-figure" style={{ position: "relative", width }}>
      {svg}
      {tip ? (
        <div
          className={tip.note ? "tooltip note" : "tooltip"}
          style={
            tip.note
              ? { left: Math.max(0, Math.min(tip.x, width - 320)), top: tip.y + 6 }
              : { left: Math.min(tip.x + 10, width - 230), top: Math.max(0, tip.y - 44) }
          }
        >
          <div className="tt-value">{tip.value}</div>
          <div className="tt-label">{tip.label}</div>
        </div>
      ) : null}
    </div>
  );
}
