import type { ElementDefinition } from "cytoscape";

import type { ClassInfo, Decomposition, GraphPayload } from "../api/types";

export type LayoutMode = "fixed" | "grouped";

export interface BuildInput {
  graph: GraphPayload;
  decomposition: Decomposition;
  /** Colour slot of each service, by service index. */
  slots: number[];
  mode: LayoutMode;
  /** Services drawn as a single node (grouped mode only). */
  collapsed: ReadonlySet<number>;
  crossOnly: boolean;
  /** Append the service number to class labels (composite encoding past three services). */
  showTags: boolean;
  classLabel: (info: ClassInfo) => string;
  serviceLabel: (serviceIndex: number) => string;
}

export const serviceNodeId = (service: number) => `svc:${service}`;

/** Width of an edge: hairline inside a service, growing with the call count between services. */
export function edgeWidth(calls: number, cross: boolean): number {
  if (!cross) return 1;
  return Math.min(9, 1.5 + 1.25 * Math.log2(Math.max(1, calls)));
}

/**
 * Cytoscape elements of one decomposition. Class nodes keep the fixed positions of the
 * graph payload; in grouped mode each service is a compound node, or a single node when
 * collapsed, and edges touching a collapsed service are summed per pair of endpoints.
 */
export function buildElements(input: BuildInput): ElementDefinition[] {
  const { graph, decomposition, slots, crossOnly, showTags } = input;
  const grouped = input.mode === "grouped";
  const collapsed = grouped ? input.collapsed : new Set<number>();
  const assignment = decomposition.assignment;
  const interfaces = new Set(decomposition.interfaces);
  const positions = graph.layout.positions;
  const elements: ElementDefinition[] = [];

  if (grouped) {
    for (const service of decomposition.services) {
      const slot = slots[service.index];
      if (collapsed.has(service.index)) {
        const points = service.classes.map((c) => positions[c]).filter(Boolean);
        const x = points.reduce((sum, p) => sum + p[0], 0) / Math.max(1, points.length);
        const y = points.reduce((sum, p) => sum + p[1], 0) / Math.max(1, points.length);
        elements.push({
          group: "nodes",
          data: {
            id: serviceNodeId(service.index),
            service: service.index,
            slot,
            size: service.size,
            label: `${input.serviceLabel(service.index)} (${service.size})`,
          },
          position: { x, y },
          classes: "svc-collapsed",
        });
      } else {
        elements.push({
          group: "nodes",
          data: { id: serviceNodeId(service.index), service: service.index, slot, label: input.serviceLabel(service.index) },
          classes: "svc",
        });
      }
    }
  }

  for (const info of graph.classes) {
    const service = assignment[info.id];
    if (collapsed.has(service)) continue;
    const position = positions[info.id];
    const base = input.classLabel(info);
    elements.push({
      group: "nodes",
      data: {
        id: info.id,
        cls: info.id,
        service,
        slot: slots[service],
        label: showTags ? `${base} · ${slots[service] + 1}` : base,
        ...(grouped ? { parent: serviceNodeId(service) } : {}),
      },
      position: position ? { x: position[0], y: position[1] } : undefined,
      classes: interfaces.has(info.id) ? "cls iface" : "cls",
    });
  }

  const represent = (c: string) => (collapsed.has(assignment[c]) ? serviceNodeId(assignment[c]) : c);
  const merged = new Map<string, { source: string; target: string; calls: number; edges: number; cross: boolean }>();
  for (const edge of graph.edges) {
    const cross = assignment[edge.source] !== assignment[edge.target];
    if (crossOnly && !cross) continue;
    const source = represent(edge.source);
    const target = represent(edge.target);
    if (source === target) continue;
    const key = `${source}\u0000${target}`;
    const entry = merged.get(key) ?? { source, target, calls: 0, edges: 0, cross };
    entry.calls += edge.calls;
    entry.edges += 1;
    merged.set(key, entry);
  }
  for (const [key, edge] of merged) {
    const aggregated = edge.source.startsWith("svc:") && edge.target.startsWith("svc:");
    elements.push({
      group: "edges",
      data: {
        id: `e:${key}`,
        source: edge.source,
        target: edge.target,
        calls: edge.calls,
        edges: edge.edges,
        width: edgeWidth(edge.calls, edge.cross),
        label: aggregated ? String(edge.calls) : "",
      },
      classes: edge.cross ? "cross" : "intra",
    });
  }
  return elements;
}
