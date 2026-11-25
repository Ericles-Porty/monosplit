import cytoscape, { type Core, type EventObject, type LayoutOptions } from "cytoscape";
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";

import type { ClassInfo, Decomposition, GraphPayload } from "../api/types";
import { slotColor, type Palette } from "../theme/Theme";
import { buildElements, serviceNodeId, type LayoutMode } from "./elements";
import { buildStyle } from "./style";
import type { Viewport, ViewportSync } from "./viewportSync";

export type HoverTarget =
  | { kind: "class"; id: string }
  | { kind: "service"; service: number }
  | { kind: "edge"; source: string; target: string; calls: number; edges: number };

export interface GraphPaneProps {
  paneId: string;
  graph: GraphPayload;
  decomposition: Decomposition;
  slots: number[];
  palette: Palette;
  mode: LayoutMode;
  crossOnly: boolean;
  showTags: boolean;
  classLabel: (info: ClassInfo) => string;
  serviceLabel: (serviceIndex: number) => string;
  collapsed: ReadonlySet<number>;
  hovered: string | null;
  selected: string | null;
  focusService: number | null;
  changed: ReadonlySet<string>;
  sync: ViewportSync | null;
  fitSignal: number;
  onHover: (classId: string | null) => void;
  onSelect: (classId: string | null) => void;
  onToggleCollapse: (service: number) => void;
  tooltip: (target: HoverTarget) => ReactNode;
}

const FCOSE: LayoutOptions = {
  name: "fcose",
  quality: "proof",
  randomize: false,
  animate: false,
  fit: false,
  nodeDimensionsIncludeLabels: true,
  packComponents: true,
  nodeRepulsion: 4500,
  idealEdgeLength: 50,
  edgeElasticity: 0.45,
  nestingFactor: 0.2,
  gravity: 0.4,
  gravityCompound: 1.5,
  gravityRangeCompound: 1.2,
  numIter: 2500,
  tile: true,
} as unknown as LayoutOptions;

const PADDING = 28;

/** Place the tooltip beside the pointer, on the side with more room. */
function tipPosition(x: number, y: number, box: HTMLElement | null): CSSProperties {
  const width = box?.clientWidth ?? 0;
  const height = box?.clientHeight ?? 0;
  const horizontal = x > width / 2 ? { right: width - x + 14 } : { left: x + 14 };
  const vertical = y > height / 2 ? { bottom: height - y + 14 } : { top: y + 14 };
  return { ...horizontal, ...vertical };
}

function sameViewport(cy: Core, viewport: Viewport): boolean {
  const pan = cy.pan();
  return Math.abs(cy.zoom() - viewport.zoom) < 1e-4 && Math.abs(pan.x - viewport.pan.x) < 0.5 && Math.abs(pan.y - viewport.pan.y) < 0.5;
}

export function GraphPane(props: GraphPaneProps) {
  const container = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const latest = useRef(props);
  latest.current = props;
  const applying = useRef(false);
  const [version, setVersion] = useState(0);
  const [tip, setTip] = useState<{ x: number; y: number; target: HoverTarget } | null>(null);

  // One Cytoscape instance per pane; events read the latest props through a ref.
  useEffect(() => {
    const cy = cytoscape({
      container: container.current,
      elements: [],
      style: buildStyle(latest.current.palette),
      minZoom: 0.15,
      maxZoom: 4,
      boxSelectionEnabled: false,
      selectionType: "single",
    });
    cyRef.current = cy;
    // Test hook for scripts/screenshot.mjs: off unless localStorage "monosplit.debug" is "1".
    const debug = localStorage.getItem("monosplit.debug") === "1";
    const registry = debug ? ((window as unknown as { __monosplitCy?: Record<string, Core> }).__monosplitCy ??= {}) : null;
    if (registry) registry[latest.current.paneId] = cy;

    const classOf = (event: EventObject): string | null => {
      const target = event.target;
      if (target.hasClass?.("cls")) return target.id();
      return null;
    };
    cy.on("mouseover", "node", (event) => {
      const node = event.target;
      const position = node.renderedPosition();
      if (node.hasClass("cls")) {
        latest.current.onHover(node.id());
        setTip({ x: position.x, y: position.y, target: { kind: "class", id: node.id() } });
      } else if (node.hasClass("svc-collapsed")) {
        setTip({ x: position.x, y: position.y, target: { kind: "service", service: node.data("service") } });
      }
    });
    cy.on("mouseout", "node", () => {
      latest.current.onHover(null);
      setTip(null);
    });
    cy.on("mouseover", "edge", (event) => {
      const edge = event.target;
      const midpoint = edge.renderedMidpoint();
      setTip({
        x: midpoint.x,
        y: midpoint.y,
        target: { kind: "edge", source: edge.data("source"), target: edge.data("target"), calls: edge.data("calls"), edges: edge.data("edges") },
      });
    });
    cy.on("mouseout", "edge", () => setTip(null));
    cy.on("tap", "node", (event) => {
      const id = classOf(event);
      if (id) latest.current.onSelect(id);
    });
    cy.on("tap", (event) => {
      if (event.target === cy) latest.current.onSelect(null);
    });
    cy.on("dbltap", "node.svc, node.svc-collapsed", (event) => latest.current.onToggleCollapse(event.target.data("service")));
    cy.on("viewport", () => {
      setTip(null);
      const { sync, mode, paneId } = latest.current;
      if (!applying.current && sync && mode === "fixed") sync.publish(paneId, { zoom: cy.zoom(), pan: { ...cy.pan() } });
    });

    const observer = new ResizeObserver(() => cy.resize());
    if (container.current) observer.observe(container.current);
    return () => {
      observer.disconnect();
      if (registry && registry[latest.current.paneId] === cy) delete registry[latest.current.paneId];
      cy.destroy();
      cyRef.current = null;
    };
  }, []);

  // Zoom and pan follow the other panes in fixed mode.
  useEffect(() => {
    const { sync, paneId } = props;
    if (!sync || props.mode !== "fixed") return;
    return sync.subscribe(paneId, (viewport) => {
      const cy = cyRef.current;
      if (!cy || sameViewport(cy, viewport)) return;
      applying.current = true;
      cy.viewport(viewport);
      applying.current = false;
    });
  }, [props.sync, props.paneId, props.mode]);

  const { graph, decomposition, slots, mode, crossOnly, showTags, classLabel, serviceLabel, collapsed } = props;
  const elements = useMemo(
    () => buildElements({ graph, decomposition, slots, mode, collapsed, crossOnly, showTags, classLabel, serviceLabel }),
    [graph, decomposition, slots, mode, collapsed, crossOnly, showTags, classLabel, serviceLabel],
  );

  const fit = () => {
    const cy = cyRef.current;
    if (!cy) return;
    applying.current = true;
    cy.fit(undefined, PADDING);
    applying.current = false;
  };

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    // Removed nodes never fire mouseout: drop any hover state that pointed at them.
    setTip(null);
    latest.current.onHover(null);
    cy.batch(() => {
      cy.elements().remove();
      cy.add(elements);
      cy.nodes().forEach((node) => {
        node.data("color", slotColor(latest.current.palette, node.data("slot")));
      });
    });
    if (mode === "fixed") {
      cy.layout({ name: "preset", fit: false, animate: false }).run();
      fit();
      setVersion((v) => v + 1);
    } else {
      const layout = cy.layout(FCOSE);
      layout.one("layoutstop", () => {
        fit();
        setVersion((v) => v + 1);
      });
      layout.run();
    }
  }, [elements]);

  useEffect(() => {
    if (props.fitSignal > 0) fit();
  }, [props.fitSignal]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.style(buildStyle(props.palette));
    cy.batch(() => {
      cy.nodes().forEach((node) => {
        node.data("color", slotColor(props.palette, node.data("slot")));
      });
    });
  }, [props.palette]);

  const { hovered, selected, focusService, changed } = props;
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const nodeFor = (classId: string) => {
      const node = cy.getElementById(classId);
      if (node.nonempty()) return node;
      const service = decomposition.assignment[classId];
      return service === undefined ? node : cy.getElementById(serviceNodeId(service));
    };
    cy.batch(() => {
      cy.elements().removeClass("faded lit picked changed");
      for (const id of changed) cy.getElementById(id).addClass("changed");
      const compounds = cy.nodes(".svc");
      if (focusService !== null) {
        const members = cy.nodes().filter((n) => n.data("service") === focusService);
        cy.elements().not(members).not(members.connectedEdges()).not(compounds).addClass("faded");
      }
      if (hovered) {
        const node = nodeFor(hovered);
        if (node.nonempty()) {
          cy.elements().not(node.closedNeighborhood()).not(compounds).addClass("faded");
          node.addClass("lit");
          node.connectedEdges().addClass("lit");
        }
      }
      if (selected) nodeFor(selected).addClass("picked");
    });
  }, [hovered, selected, focusService, changed, version, decomposition]);

  return (
    <div className="graph-wrap">
      <div className="graph" ref={container} />
      {tip ? (
        <div className="tooltip" style={tipPosition(tip.x, tip.y, container.current)}>
          {props.tooltip(tip.target)}
        </div>
      ) : null}
    </div>
  );
}
