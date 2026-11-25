import type { Decomposition } from "../api/types";

/**
 * Hungarian algorithm (Kuhn-Munkres, O(n^2 m)) for a rows x cols cost matrix with rows <= cols.
 * Returns, for each row, the column assigned to it, minimising the total cost.
 */
function hungarianMin(cost: number[][]): number[] {
  const n = cost.length;
  const m = n ? cost[0].length : 0;
  const u = new Array<number>(n + 1).fill(0);
  const v = new Array<number>(m + 1).fill(0);
  const p = new Array<number>(m + 1).fill(0);
  const way = new Array<number>(m + 1).fill(0);
  for (let i = 1; i <= n; i++) {
    p[0] = i;
    let j0 = 0;
    const minv = new Array<number>(m + 1).fill(Number.POSITIVE_INFINITY);
    const used = new Array<boolean>(m + 1).fill(false);
    do {
      used[j0] = true;
      const i0 = p[j0];
      let delta = Number.POSITIVE_INFINITY;
      let j1 = 0;
      for (let j = 1; j <= m; j++) {
        if (used[j]) continue;
        const current = cost[i0 - 1][j - 1] - u[i0] - v[j];
        if (current < minv[j]) {
          minv[j] = current;
          way[j] = j0;
        }
        if (minv[j] < delta) {
          delta = minv[j];
          j1 = j;
        }
      }
      for (let j = 0; j <= m; j++) {
        if (used[j]) {
          u[p[j]] += delta;
          v[j] -= delta;
        } else {
          minv[j] -= delta;
        }
      }
      j0 = j1;
    } while (p[j0] !== 0);
    do {
      const j1 = way[j0];
      p[j0] = p[j1];
      j0 = j1;
    } while (j0);
  }
  const assignment = new Array<number>(n).fill(-1);
  for (let j = 1; j <= m; j++) if (p[j] !== 0) assignment[p[j] - 1] = j - 1;
  return assignment;
}

/** One-to-one assignment of rows to columns maximising the total weight; -1 = unassigned. */
export function assignMax(weights: number[][]): number[] {
  const rows = weights.length;
  const cols = rows ? weights[0].length : 0;
  if (!rows || !cols) return new Array<number>(rows).fill(-1);
  if (rows <= cols) return hungarianMin(weights.map((row) => row.map((w) => -w)));
  const transposed = Array.from({ length: cols }, (_, j) => weights.map((row) => -row[j]));
  const byColumn = hungarianMin(transposed);
  const result = new Array<number>(rows).fill(-1);
  byColumn.forEach((row, col) => {
    if (row >= 0) result[row] = col;
  });
  return result;
}

/** Colour slots of a reference decomposition: services ordered by their first class in graph order. */
export function canonicalSlots(decomposition: Decomposition, classOrder: string[]): number[] {
  const rank = new Map(classOrder.map((c, i) => [c, i]));
  const firsts = decomposition.services.map((service, index) => ({
    index,
    first: Math.min(...service.classes.map((c) => rank.get(c) ?? Number.POSITIVE_INFINITY)),
  }));
  firsts.sort((a, b) => a.first - b.first);
  const slots = new Array<number>(decomposition.services.length);
  firsts.forEach((entry, order) => {
    slots[entry.index] = order;
  });
  return slots;
}

/**
 * Slots of `target` that reuse the slot of the reference service with which it shares the
 * most classes (one-to-one). Services without overlap get the next unused slots.
 */
export function matchedSlots(
  reference: Decomposition,
  referenceSlots: number[],
  target: Decomposition,
  classOrder: string[],
): number[] {
  const referenceSets = reference.services.map((s) => new Set(s.classes));
  const overlap = target.services.map((s) => referenceSets.map((set) => s.classes.filter((c) => set.has(c)).length));
  const assignment = assignMax(overlap);
  const slots = assignment.map((col, row) => (col >= 0 && overlap[row][col] > 0 ? referenceSlots[col] : -1));
  const used = new Set(slots.filter((s) => s >= 0));
  const order = canonicalSlots(target, classOrder);
  const unmatched = slots
    .map((slot, index) => ({ slot, index }))
    .filter((entry) => entry.slot < 0)
    .sort((a, b) => order[a.index] - order[b.index]);
  let next = 0;
  for (const entry of unmatched) {
    while (used.has(next)) next++;
    slots[entry.index] = next;
    used.add(next);
  }
  return slots;
}
