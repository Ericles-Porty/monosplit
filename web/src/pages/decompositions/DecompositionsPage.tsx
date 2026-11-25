import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { useResource } from "../../api/client";
import type { ClassInfo, Decomposition, GraphPayload, IndexPayload, RunPayload, StudyPayload } from "../../api/types";
import { navigate, type Params } from "../../app/router";
import { Term } from "../../components/Term";
import type { LayoutMode } from "../../graph/elements";
import type { HoverTarget } from "../../graph/GraphPane";
import { canonicalSlots, matchedSlots } from "../../graph/matching";
import { ViewportSync } from "../../graph/viewportSync";
import { useI18n } from "../../i18n/I18n";
import { sortMethods } from "../../lib/methods";
import { readPalette, useTheme } from "../../theme/Theme";
import { ClassDetails, type PaneView } from "./ClassDetails";
import { ClassTable } from "./ClassTable";
import { MetricsTable } from "./MetricsTable";
import { ModelOutput } from "./ModelOutput";
import { Pane } from "./Pane";

const PANES = [0, 1, 2];
const emptySets = (): ReadonlySet<number>[] => PANES.map(() => new Set<number>());

/** Runs grouped by identical partition (ARI = 1), labelled A, B, C… */
function partitionLetters(stability: StudyPayload["variants"][number]["stability"]): Map<number, string> {
  const letters = new Map<number, string>();
  if (!stability) return letters;
  const groups: number[][] = [];
  stability.runs.forEach((run, i) => {
    const group = groups.find((g) => stability.ari[stability.runs.indexOf(g[0])][i] === 1);
    if (group) group.push(run);
    else groups.push([run]);
  });
  groups.forEach((group, g) => group.forEach((run) => letters.set(run, String.fromCharCode(65 + g))));
  return letters;
}

export function DecompositionsPage({ index, params }: { index: IndexPayload; params: Record<string, string> }) {
  const { t, fmt } = useI18n();
  const { theme } = useTheme();
  const palette = useMemo(() => readPalette(), [theme]);

  const studies = index.studies.filter((s) => s.has_graph);
  const study = studies.find((s) => s.id === params.study) ?? studies[0];
  const variant = study?.variants.find((v) => v.variant === params.variant) ?? study?.variants[0];
  const runRef = variant?.runs.find((r) => String(r.run) === params.run) ?? variant?.runs[0];
  const mode: LayoutMode = params.layout === "grouped" ? "grouped" : "fixed";
  const crossOnly = params.cross === "1";
  const labelMode = params.labels === "prompt" && variant?.variant === "obfuscated" ? "prompt" : "class";
  const compare = params.compare ? Number(params.compare) : null;
  const defaults = ["llm", study?.ah_selected ?? "random", "random"];
  const methods = PANES.map((i) => params[`p${i + 1}`] || defaults[i]);
  const methodsKey = methods.join(",");

  const graphRes = useResource<GraphPayload>(study ? `graph/${study.app}` : null);
  const studyRes = useResource<StudyPayload>(study ? `study/${study.id}` : null);
  const runRes = useResource<RunPayload>(study && variant && runRef ? `run/${study.id}/${variant.variant}/${runRef.run}` : null);
  const graph = graphRes.data?.app === study?.app ? graphRes.data : undefined;
  const studyData = studyRes.data?.id === study?.id ? studyRes.data : undefined;
  const run = runRes.data?.study === study?.id ? runRes.data : undefined;

  const update = (patch: Params, push = false) =>
    navigate(
      "decompositions",
      {
        study: study?.id,
        variant: variant?.variant,
        run: runRef?.run,
        layout: params.layout,
        cross: params.cross,
        labels: params.labels,
        compare: params.compare,
        p1: params.p1,
        p2: params.p2,
        p3: params.p3,
        ...patch,
      },
      !push,
    );

  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [focus, setFocus] = useState<(number | null)[]>(PANES.map(() => null));
  const [collapsed, setCollapsed] = useState<ReadonlySet<number>[]>(emptySets);
  const [fitSignals, setFitSignals] = useState<number[]>(PANES.map(() => 0));
  const sync = useMemo(() => new ViewportSync(), []);

  const viewKey = `${study?.id}|${variant?.variant}|${runRef?.run}|${methodsKey}|${mode}`;
  useEffect(() => {
    setFocus(PANES.map(() => null));
    setCollapsed(emptySets());
  }, [viewKey]);

  const decompositions = useMemo<(Decomposition | undefined)[]>(
    () =>
      methodsKey.split(",").map(
        (method) => run?.decompositions.find((d) => d.method === method) ?? studyData?.references.find((d) => d.method === method),
      ),
    [run, studyData, methodsKey],
  );
  const classOrder = useMemo(() => graph?.classes.map((c) => c.id) ?? [], [graph]);
  const slots = useMemo(() => {
    const reference = decompositions[0];
    const referenceSlots = reference ? canonicalSlots(reference, classOrder) : [];
    return decompositions.map((d, i) => {
      if (!d) return [];
      if (i === 0 || !reference) return canonicalSlots(d, classOrder);
      return matchedSlots(reference, referenceSlots, d, classOrder);
    });
  }, [decompositions, classOrder]);

  const promptNames = run?.prompt_names;
  const classLabel = useCallback(
    (info: ClassInfo) => (labelMode === "prompt" ? (promptNames?.[info.id] ?? info.simple) : info.simple),
    [labelMode, promptNames],
  );
  const serviceLabels = useMemo(
    () =>
      decompositions.map((d, pane) => (serviceIndex: number) => {
        const name = d?.services[serviceIndex]?.name;
        return name ? name : t.decompositions.service((slots[pane]?.[serviceIndex] ?? serviceIndex) + 1);
      }),
    [decompositions, slots, t],
  );

  const stability = studyData?.variants.find((v) => v.variant === variant?.variant)?.stability ?? null;
  const letters = useMemo(() => partitionLetters(stability), [stability]);
  const runNumber = runRef?.run;
  const changed = useMemo<ReadonlySet<string>>(() => {
    if (!stability || compare === null || runNumber === undefined) return new Set();
    return new Set(stability.moved[String(runNumber)]?.[String(compare)] ?? []);
  }, [stability, compare, runNumber]);
  const ari =
    stability && compare !== null && runNumber !== undefined
      ? stability.ari[stability.runs.indexOf(runNumber)]?.[stability.runs.indexOf(compare)]
      : undefined;

  const classById = useMemo(() => new Map(graph?.classes.map((c) => [c.id, c]) ?? []), [graph]);
  const totals = useMemo(() => {
    const out = new Map<string, number>();
    const inn = new Map<string, number>();
    for (const e of graph?.edges ?? []) {
      out.set(e.source, (out.get(e.source) ?? 0) + e.calls);
      inn.set(e.target, (inn.get(e.target) ?? 0) + e.calls);
    }
    return { out, inn };
  }, [graph]);

  const tooltip = (target: HoverTarget, d: Decomposition, serviceLabel: (i: number) => string): ReactNode => {
    const name = (id: string) => (id.startsWith("svc:") ? serviceLabel(Number(id.slice(4))) : (classById.get(id)?.simple ?? id));
    if (target.kind === "class") {
      return (
        <>
          <div className="tt-value">{classById.get(target.id)?.simple}</div>
          <div className="tt-label">
            {t.decompositions.tooltipService}: {serviceLabel(d.assignment[target.id])}
          </div>
          <div>
            <span className="tt-value">{fmt.integer(totals.out.get(target.id) ?? 0)}</span>{" "}
            <span className="tt-label">{t.decompositions.tooltipOut}</span> ·{" "}
            <span className="tt-value">{fmt.integer(totals.inn.get(target.id) ?? 0)}</span>{" "}
            <span className="tt-label">{t.decompositions.tooltipIn}</span>
          </div>
        </>
      );
    }
    if (target.kind === "service") {
      const service = d.services[target.service];
      return (
        <>
          <div className="tt-value">{serviceLabel(target.service)}</div>
          <div className="tt-label">
            {t.common.classes(service.size)} · {t.decompositions.legendCalls(service.calls_out, service.calls_in)}
          </div>
        </>
      );
    }
    return (
      <>
        <div>
          <span className="tt-value">{t.common.calls(target.calls)}</span>{" "}
          <span className="tt-label">{target.edges > 1 ? `(${t.common.edges(target.edges)})` : ""}</span>
        </div>
        <div className="tt-label">
          {name(target.source)} → {name(target.target)}
        </div>
      </>
    );
  };

  if (!study || !variant) {
    return <p className="note">{t.overview.noStudies}</p>;
  }
  const runs = variant.runs;
  const position = runs.findIndex((r) => r.run === runNumber);
  const availableMethods = sortMethods(
    [...(run?.decompositions.map((d) => d.method) ?? []), ...(studyData?.references.map((d) => d.method) ?? [])],
    study.ah_selected,
  );
  const paneViews: PaneView[] = PANES.map((i) => ({
    method: methods[i],
    decomposition: decompositions[i],
    slots: slots[i],
    serviceLabel: serviceLabels[i],
  }));

  return (
    <>
      <div className="control-row">
        <label className="field">
          <span className="label">
            <Term k="study">{t.decompositions.study}</Term>
          </span>
          <select value={study.id} onChange={(event) => navigate("decompositions", { study: event.target.value })}>
            {studies.map((s) => (
              <option key={s.id} value={s.id}>
                {s.experiment} · {s.app} · {s.profile}
              </option>
            ))}
          </select>
        </label>

        <div className="field">
          <span className="label">
            <Term k="variant">{t.decompositions.variant}</Term>
          </span>
          <div className="segmented">
            {study.variants.map((v) => (
              <button
                key={v.variant}
                type="button"
                aria-pressed={v.variant === variant.variant}
                onClick={() => update({ variant: v.variant, run: v.runs[0]?.run, compare: undefined, labels: undefined }, true)}
              >
                {t.variants[v.variant] ?? v.variant}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <span className="label">
            <Term k="run">{t.decompositions.run}</Term>
          </span>
          <div className="runs">
            <button
              type="button"
              className="icon-button"
              aria-label={t.decompositions.previousRun}
              disabled={position <= 0}
              onClick={() => update({ run: runs[position - 1].run, compare: undefined }, true)}
            >
              ‹
            </button>
            {runs.map((r) => (
              <button
                key={r.run}
                type="button"
                className="run-button"
                aria-pressed={r.run === runNumber}
                aria-label={t.decompositions.runButton(r.run, r.k)}
                title={letters.get(r.run) ? t.decompositions.partitionLetter(letters.get(r.run)!) : undefined}
                onClick={() => update({ run: r.run, compare: params.compare === String(r.run) ? undefined : params.compare }, true)}
              >
                <span className="run-number">{r.run}</span>
                <span className="run-meta">
                  K={r.k}
                  {letters.get(r.run) ? ` · ${letters.get(r.run)}` : ""}
                </span>
              </button>
            ))}
            <button
              type="button"
              className="icon-button"
              aria-label={t.decompositions.nextRun}
              disabled={position < 0 || position >= runs.length - 1}
              onClick={() => update({ run: runs[position + 1].run, compare: undefined }, true)}
            >
              ›
            </button>
          </div>
        </div>

        <div className="field">
          <span className="label">
            <Term k="layout">{t.decompositions.layout}</Term>
          </span>
          <div className="segmented">
            <button type="button" aria-pressed={mode === "fixed"} onClick={() => update({ layout: undefined })}>
              {t.decompositions.layoutFixed}
            </button>
            <button type="button" aria-pressed={mode === "grouped"} onClick={() => update({ layout: "grouped" })}>
              {t.decompositions.layoutGrouped}
            </button>
          </div>
        </div>

        <label className="field">
          <span className="label">
            <Term k="compare">{t.decompositions.compare}</Term>
          </span>
          <select value={compare ?? ""} onChange={(event) => update({ compare: event.target.value || undefined })}>
            <option value="">{t.decompositions.compareNone}</option>
            {runs
              .filter((r) => r.run !== runNumber)
              .map((r) => (
                <option key={r.run} value={r.run}>
                  {t.decompositions.compareRun(r.run)}
                </option>
              ))}
          </select>
        </label>

        {variant.variant === "obfuscated" ? (
          <div className="field">
            <span className="label">
              <Term k="labels">{t.decompositions.labels}</Term>
            </span>
            <div className="segmented">
              <button type="button" aria-pressed={labelMode === "class"} onClick={() => update({ labels: undefined })}>
                {t.decompositions.labelClass}
              </button>
              <button type="button" aria-pressed={labelMode === "prompt"} onClick={() => update({ labels: "prompt" })}>
                {t.decompositions.labelPrompt}
              </button>
            </div>
          </div>
        ) : null}

        <label className="check">
          <input type="checkbox" checked={crossOnly} onChange={(event) => update({ cross: event.target.checked ? "1" : undefined })} />
          <Term k="crossOnly">{t.decompositions.crossOnly}</Term>
        </label>
      </div>

      <div className="status-line">
        {compare !== null && ari !== undefined
          ? t.decompositions.moved(changed.size, fmt.number(ari, 2))
          : letters.size
            ? t.decompositions.partitionNote
            : null}
        {studyData && !studyData.evaluated ? <span className="error"> {t.decompositions.notEvaluated}</span> : null}
        {graphRes.error || runRes.error || studyRes.error ? <span className="error"> {t.common.loadError}</span> : null}
      </div>

      {!runs.length ? (
        <p className="note">{t.decompositions.noRuns}</p>
      ) : !graph || !run ? (
        <p className="note">{t.common.loading}</p>
      ) : (
        <>
          <div className="panes">
            {PANES.map((i) => (
              <Pane
                key={i}
                index={i}
                method={methods[i]}
                methods={availableMethods}
                ahSelected={study.ah_selected}
                onMethod={(method) => update({ [`p${i + 1}`]: method })}
                graph={graph}
                decomposition={decompositions[i]}
                slots={slots[i]}
                palette={palette}
                mode={mode}
                crossOnly={crossOnly}
                classLabel={classLabel}
                serviceLabel={serviceLabels[i]}
                collapsed={collapsed[i]}
                onCollapsed={(next) => setCollapsed((all) => all.map((set, j) => (j === i ? next : set)))}
                focusService={focus[i]}
                onFocus={(service) => setFocus((all) => all.map((value, j) => (j === i ? service : value)))}
                hovered={hovered}
                selected={selected}
                changed={changed}
                sync={mode === "fixed" ? sync : null}
                fitSignal={fitSignals[i]}
                onFit={() => setFitSignals((all) => all.map((value, j) => (mode === "fixed" || j === i ? value + 1 : value)))}
                onHover={setHovered}
                onSelect={setSelected}
                tooltip={(target, d) => tooltip(target, d, serviceLabels[i])}
              />
            ))}
          </div>

          <div className="keys">
            <span className="key">
              <span className="key-ring" /> <Term k="interfaces">{t.decompositions.keyInterface}</Term>
            </span>
            <span className="key">
              <span className="key-line" /> <Term k="crossCalls">{t.decompositions.keyCross}</Term>
            </span>
            <span className="key">
              <span className="key-line intra" /> {t.decompositions.keyIntra}
            </span>
            {compare !== null ? (
              <span className="key">
                <span className="key-dashed" /> {t.decompositions.keyChanged}
              </span>
            ) : null}
            <span className="key">{t.decompositions.keyColors}</span>
            {mode === "fixed" ? <span className="key">{t.decompositions.keyTags}</span> : <span className="key">{t.decompositions.dblclickHint}</span>}
            <span className="key">{t.decompositions.focusHint}</span>
          </div>

          <div className="lower">
            <div>
              <h3 style={{ marginBottom: 8 }}>
                <Term k="metricsByMethod">{t.decompositions.metricsTitle}</Term>
              </h3>
              <MetricsTable panes={paneViews} ahSelected={study.ah_selected} />
              <ClassTable
                graph={graph}
                panes={paneViews}
                ahSelected={study.ah_selected}
                palette={palette}
                selected={selected}
                onSelect={setSelected}
              />
              <ModelOutput run={run} />
            </div>
            <ClassDetails
              classId={selected ?? hovered}
              graph={graph}
              panes={paneViews}
              promptName={variant.variant === "obfuscated" ? run.prompt_names[(selected ?? hovered) ?? ""] : undefined}
              ahSelected={study.ah_selected}
              palette={palette}
            />
          </div>
        </>
      )}
    </>
  );
}
