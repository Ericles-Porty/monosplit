import { describe, expect, it } from "vitest";

import type { Decomposition } from "../api/types";
import { assignMax, canonicalSlots, matchedSlots } from "./matching";

const ORDER = ["A", "B", "C", "D", "E", "F"];

function decomposition(groups: string[][]): Decomposition {
  const assignment: Record<string, number> = {};
  groups.forEach((group, i) => group.forEach((c) => (assignment[c] = i)));
  return {
    method: "test",
    seed: null,
    k: groups.length,
    metrics: { sm: null, ifn: null, icp: null, ned: null },
    services: groups.map((classes, index) => ({
      index,
      name: null,
      classes,
      size: classes.length,
      internal_edges: 0,
      internal_calls: 0,
      calls_out: 0,
      calls_in: 0,
      interfaces: [],
    })),
    assignment,
    interfaces: [],
    service_edges: [],
    cross_calls: 0,
    cross_edges: 0,
  };
}

describe("assignMax", () => {
  it("maximises the total weight", () => {
    expect(assignMax([[1, 5], [4, 1]])).toEqual([1, 0]);
    expect(assignMax([[3, 2, 1], [3, 3, 0], [0, 1, 4]])).toEqual([0, 1, 2]);
  });

  it("leaves extra rows unassigned when there are more rows than columns", () => {
    const result = assignMax([[1], [5], [2]]);
    expect(result.filter((c) => c === 0)).toHaveLength(1);
    expect(result[1]).toBe(0);
  });
});

describe("colour slots", () => {
  it("orders reference services by their first class", () => {
    expect(canonicalSlots(decomposition([["D", "E"], ["A", "B"], ["C", "F"]]), ORDER)).toEqual([2, 0, 1]);
  });

  it("gives a matched service the slot of the reference service it overlaps most", () => {
    const reference = decomposition([["A", "B", "C"], ["D", "E", "F"]]);
    const target = decomposition([["D", "E", "C"], ["A", "B", "F"]]);
    expect(matchedSlots(reference, canonicalSlots(reference, ORDER), target, ORDER)).toEqual([1, 0]);
  });

  it("gives unmatched services new slots", () => {
    const reference = decomposition([["A", "B", "C", "D", "E", "F"], []]);
    const target = decomposition([["A", "B"], ["C", "D"], ["E", "F"]]);
    const slots = matchedSlots(reference, [0, 1], target, ORDER);
    expect(new Set(slots).size).toBe(3);
    expect(slots[0]).toBe(0);
  });
});
