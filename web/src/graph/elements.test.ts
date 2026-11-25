import { describe, expect, it } from "vitest";

import type { Decomposition, GraphPayload } from "../api/types";
import { buildElements, edgeWidth, type BuildInput } from "./elements";

// Same graph as tests/conftest.py and docs/metrics_worked_example.md.
const EDGES: [string, string, number][] = [
  ["A", "B", 3],
  ["B", "A", 1],
  ["A", "C", 2],
  ["C", "D", 1],
  ["D", "E", 4],
  ["E", "F", 2],
  ["F", "D", 1],
  ["B", "E", 1],
];

const graph: GraphPayload = {
  app: "toy",
  meta: {},
  stats: { classes: 6 },
  classes: "ABCDEF".split("").map((id) => ({ id, simple: id, package: "", kind: "class", source: "" })),
  edges: EDGES.map(([source, target, calls]) => ({ source, target, calls })),
  layout: { seed: 0, positions: Object.fromEntries("ABCDEF".split("").map((c, i) => [c, [i * 10, i * 5] as [number, number]])) },
};

// P1 of the worked example: {A, B, C}, {D, E}, {F}.
const p1: Decomposition = {
  method: "llm",
  seed: null,
  k: 3,
  metrics: { sm: -1 / 36, ifn: 1, icp: 1 / 3, ned: 1 },
  services: [
    { index: 0, name: "s1", classes: ["A", "B", "C"], size: 3, internal_edges: 3, internal_calls: 6, calls_out: 2, calls_in: 0, interfaces: [] },
    { index: 1, name: "s2", classes: ["D", "E"], size: 2, internal_edges: 1, internal_calls: 4, calls_out: 2, calls_in: 3, interfaces: ["D", "E"] },
    { index: 2, name: "s3", classes: ["F"], size: 1, internal_edges: 0, internal_calls: 0, calls_out: 1, calls_in: 2, interfaces: ["F"] },
  ],
  assignment: { A: 0, B: 0, C: 0, D: 1, E: 1, F: 2 },
  interfaces: ["D", "E", "F"],
  service_edges: [],
  cross_calls: 5,
  cross_edges: 4,
};

const input = (changes: Partial<BuildInput> = {}): BuildInput => ({
  graph,
  decomposition: p1,
  slots: [0, 1, 2],
  mode: "fixed",
  collapsed: new Set(),
  crossOnly: false,
  showTags: false,
  classLabel: (info) => info.simple,
  serviceLabel: (i) => `S${i + 1}`,
  ...changes,
});

const nodes = (els: ReturnType<typeof buildElements>) => els.filter((e) => e.group === "nodes");
const edges = (els: ReturnType<typeof buildElements>) => els.filter((e) => e.group === "edges");

describe("buildElements", () => {
  it("draws every class and every edge at the fixed positions", () => {
    const els = buildElements(input());
    expect(nodes(els)).toHaveLength(6);
    expect(edges(els)).toHaveLength(8);
    expect(nodes(els).find((n) => n.data.id === "B")?.position).toEqual({ x: 10, y: 5 });
    expect(edges(els).filter((e) => e.classes === "cross")).toHaveLength(4);
    expect(nodes(els).filter((n) => String(n.classes).includes("iface")).map((n) => n.data.id)).toEqual(["D", "E", "F"]);
  });

  it("keeps only edges between services on request", () => {
    expect(edges(buildElements(input({ crossOnly: true })))).toHaveLength(4);
  });

  it("adds the service number to labels", () => {
    expect(nodes(buildElements(input({ showTags: true }))).find((n) => n.data.id === "F")?.data.label).toBe("F · 3");
  });

  it("nests classes in service boxes in grouped mode", () => {
    const els = buildElements(input({ mode: "grouped" }));
    expect(nodes(els).filter((n) => n.classes === "svc")).toHaveLength(3);
    expect(nodes(els).find((n) => n.data.id === "A")?.data.parent).toBe("svc:0");
  });

  it("sums the edges of a collapsed service", () => {
    const els = buildElements(input({ mode: "grouped", collapsed: new Set([1]) }));
    expect(nodes(els).some((n) => n.data.id === "D")).toBe(false);
    const byPair = new Map(edges(els).map((e) => [`${e.data.source}>${e.data.target}`, e.data]));
    // C->D and B->E both become edges into the collapsed service; D->E disappears inside it.
    expect(byPair.get("C>svc:1")?.calls).toBe(1);
    expect(byPair.get("B>svc:1")?.calls).toBe(1);
    expect(byPair.get("svc:1>F")?.calls).toBe(2);
    expect(byPair.get("F>svc:1")?.calls).toBe(1);
    expect(edges(els)).toHaveLength(7);
  });

  it("joins edges between two collapsed services", () => {
    const els = buildElements(input({ mode: "grouped", collapsed: new Set([0, 1, 2]) }));
    const byPair = new Map(edges(els).map((e) => [`${e.data.source}>${e.data.target}`, e.data]));
    expect(byPair.get("svc:0>svc:1")).toMatchObject({ calls: 2, edges: 2, label: "2" });
    expect(edges(els)).toHaveLength(3);
  });
});

describe("edgeWidth", () => {
  it("is a hairline inside services and grows with calls between them", () => {
    expect(edgeWidth(10, false)).toBe(1);
    expect(edgeWidth(1, true)).toBeCloseTo(1.5);
    expect(edgeWidth(4, true)).toBeCloseTo(4);
    expect(edgeWidth(10_000, true)).toBe(9);
  });
});
