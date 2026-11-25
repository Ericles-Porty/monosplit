import { describe, expect, it } from "vitest";

import { linear, niceAxis, niceStep, stackOffsets } from "./scale";

describe("niceAxis", () => {
  it("rounds the domain outward to whole steps", () => {
    const axis = niceAxis(-0.047, 0.142, 4);
    expect(axis.ticks).toEqual([-0.05, 0, 0.05, 0.1, 0.15]);
    expect(axis.domain).toEqual([-0.05, 0.15]);
    expect(axis.digits).toBe(2);
  });

  it("includes zero when asked, for differences", () => {
    const axis = niceAxis(0.02, 0.17, 4, true);
    expect(axis.ticks[0]).toBe(0);
    expect(axis.ticks[axis.ticks.length - 1]).toBeGreaterThanOrEqual(0.17);
  });

  it("widens a domain with a single value", () => {
    const axis = niceAxis(0.25, 0.25, 4);
    expect(axis.domain[0]).toBeLessThan(0.25);
    expect(axis.domain[1]).toBeGreaterThan(0.25);
  });

  it("uses steps of 1, 2, 2.5 or 5 times a power of ten", () => {
    expect(niceStep(1, 4)).toBe(0.25);
    expect(niceStep(10, 4)).toBe(2.5);
    expect(niceStep(0.9, 5)).toBe(0.2);
  });
});

describe("linear", () => {
  it("maps the domain onto the range", () => {
    const x = linear([0, 10], [100, 200]);
    expect(x(0)).toBe(100);
    expect(x(5)).toBe(150);
    expect(x(10)).toBe(200);
  });
});

describe("stackOffsets", () => {
  it("leaves separate dots on the centre line", () => {
    expect(stackOffsets([0, 50, 100], 4)).toEqual({ offsets: [0, 0, 0], extent: 0 });
  });

  it("stacks equal values above and below the centre line", () => {
    const { offsets, extent } = stackOffsets([10, 10, 10], 4);
    expect(new Set(offsets).size).toBe(3);
    expect(offsets[0]).toBe(0);
    expect(Math.sign(offsets[1])).toBe(-Math.sign(offsets[2]));
    expect(extent).toBeGreaterThan(0);
  });
});
