// Linear scales with round tick values (steps of 1, 2, 2.5 or 5 times a power of ten).

export interface Axis {
  domain: [number, number];
  ticks: number[];
  /** Decimal places that show every tick without rounding. */
  digits: number;
}

export function niceStep(span: number, count: number): number {
  const raw = span / Math.max(1, count);
  const power = 10 ** Math.floor(Math.log10(raw));
  const error = raw / power;
  const factor = error >= 7.5 ? 10 : error >= 3.5 ? 5 : error >= 2.25 ? 2.5 : error >= 1.5 ? 2 : 1;
  return factor * power;
}

function decimals(step: number): number {
  for (let digits = 0; digits < 10; digits += 1) {
    if (Math.abs(Math.round(step * 10 ** digits) - step * 10 ** digits) < 1e-9) return digits;
  }
  return 10;
}

/** Domain rounded outward to whole steps, with about `count` intervals. */
export function niceAxis(min: number, max: number, count = 4, includeZero = false): Axis {
  let lo = includeZero ? Math.min(0, min) : min;
  let hi = includeZero ? Math.max(0, max) : max;
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) {
    lo = 0;
    hi = 1;
  }
  if (hi - lo < 1e-12) {
    const pad = Math.abs(lo) > 1e-12 ? Math.abs(lo) * 0.1 : 0.5;
    lo -= pad;
    hi += pad;
  }
  const step = niceStep(hi - lo, count);
  const digits = decimals(step);
  const start = Math.floor(lo / step + 1e-9) * step;
  const end = Math.ceil(hi / step - 1e-9) * step;
  const ticks: number[] = [];
  for (let i = 0; start + i * step <= end + step / 2; i += 1) {
    ticks.push(Number((start + i * step).toFixed(digits)));
  }
  return { domain: [ticks[0], ticks[ticks.length - 1]], ticks, digits };
}

export function linear(domain: [number, number], range: [number, number]): (value: number) => number {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const span = d1 - d0 || 1;
  return (value) => r0 + ((value - d0) / span) * (r1 - r0);
}

/**
 * Vertical offsets that keep dots of radius `r` apart inside a row: dots closer than
 * one diameter on the x axis are stacked, alternating above and below the centre line.
 * Returns the offset of each point, in the input order, and the largest offset used.
 */
export function stackOffsets(xs: number[], r: number): { offsets: number[]; extent: number } {
  const order = xs.map((x, i) => ({ x, i })).sort((a, b) => a.x - b.x || a.i - b.i);
  const step = r * 1.15;
  const placed: { x: number; y: number }[] = [];
  const offsets = new Array<number>(xs.length).fill(0);
  let extent = 0;
  for (const { x, i } of order) {
    for (let k = 0; ; k += 1) {
      const y = k === 0 ? 0 : (k % 2 === 1 ? -1 : 1) * Math.ceil(k / 2) * step;
      const clash = placed.some((p) => Math.abs(p.x - x) < r * 2 - 0.5 && Math.abs(p.y - y) < step - 0.01);
      if (!clash) {
        placed.push({ x, y });
        offsets[i] = y;
        extent = Math.max(extent, Math.abs(y));
        break;
      }
    }
  }
  return { offsets, extent };
}
