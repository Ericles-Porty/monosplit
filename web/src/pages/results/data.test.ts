import { describe, expect, it } from "vitest";

import type { IndexPayload, ResultApp, ResultsPayload, StudyEntry } from "../../api/types";
import { figureMethods, parseReasons, resultSets, summaryCell } from "./data";

function study(experiment: string, app: string, profile: string, provider = "openai"): StudyEntry {
  return {
    id: `${experiment}/${app}/${profile}`,
    experiment,
    app,
    profile,
    provider,
    model: "m",
    temperature: null,
    request_options: {},
    prompt_template: null,
    created_utc: null,
    evaluated: true,
    ah_selected: null,
    has_graph: true,
    variants: [],
  };
}

describe("resultSets", () => {
  it("groups the applications of an experiment and profile, dry runs last", () => {
    const index: IndexPayload = {
      version: "0",
      apps: [],
      studies: [study("dry-run", "jpetstore", "fake", "fake"), study("full", "jpetstore", "m1"), study("full", "acmeair", "m1")],
    };
    const sets = resultSets(index);
    expect(sets.map((s) => s.id)).toEqual(["full/m1", "dry-run/fake"]);
    expect(sets[0].apps).toEqual(["jpetstore", "acmeair"]);
    expect(sets[1].fake).toBe(true);
  });
});

describe("figureMethods", () => {
  const app: ResultApp = {
    app: "toy",
    name: "Toy",
    graph: null,
    evaluated: true,
    ah_selected: "ah:neighbors:complete",
    ah_selection: [
      { variant: "ah:calls:average", runs: 5, median_sm: 0.05, selected: false, rule: "" },
      { variant: "ah:neighbors:complete", runs: 5, median_sm: 0.1, selected: true, rule: "" },
    ],
    variants: [],
  };
  const methods = ["llm", "ah:calls:average", "ah:neighbors:complete", "random", "hdbscan:neighbors", "hdbscan:calls"];
  const data = {
    metrics: methods.map((method) => ({ app: "toy", method })),
  } as unknown as ResultsPayload;

  it("puts the treatment, then the two controls, then the references", () => {
    expect(figureMethods(data, app, false).map((m) => m.method)).toEqual([
      "llm",
      "ah:neighbors:complete",
      "random",
      "hdbscan:calls",
      "hdbscan:neighbors",
    ]);
  });

  it("adds the other AH variants before the references when asked", () => {
    const rows = figureMethods(data, app, true);
    expect(rows.map((m) => m.method)).toContain("ah:calls:average");
    expect(rows.find((m) => m.method === "ah:calls:average")?.group).toBe("other");
    expect(rows[rows.length - 1].group).toBe("references");
  });
});

describe("helpers", () => {
  it("reads the rejection reasons of report.py", () => {
    expect(parseReasons("missing_class=2; unknown_class=1")).toEqual([
      ["missing_class", 2],
      ["unknown_class", 1],
    ]);
    expect(parseReasons("")).toEqual([]);
  });

  it("writes median [Q1; Q3] like report.md", () => {
    const summary = { n: 5, median: 0.5, q1: 0.25, q3: 0.75, iqr: 0.5, min: 0, max: 1 };
    expect(summaryCell(summary, (v) => v.toFixed(3))).toBe("0.500 [0.250; 0.750]");
    expect(summaryCell(undefined, String)).toBe("");
  });
});
