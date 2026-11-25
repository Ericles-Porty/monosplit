import type { ControlKey, CriterionResult, ResultApp, ResultsPayload, TestSet } from "../../api/types";
import { hrefFor } from "../../app/router";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";
import { methodLabel } from "../../lib/methods";
import { CONTROLS, METRICS, differenceSummary, figureMethods, kDigits, metricSummary, parseReasons, summaryCell } from "./data";
import { formatP } from "./exporters";

// ---------------------------------------------------------------- LLM runs

export function RunsTable({ data }: { data: ResultsPayload }) {
  const { t, fmt } = useI18n();
  const r = t.results.runs;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th><Term k="app">{r.cols.app}</Term></th>
            <th><Term k="variant">{r.cols.variant}</Term></th>
            <th className="num"><Term k="accepted">{r.cols.accepted}</Term></th>
            <th className="num"><Term k="attempt">{r.cols.attempts}</Term></th>
            <th className="num"><Term k="invalid">{r.cols.invalid}</Term></th>
            <th><Term k="reasons">{r.cols.reasons}</Term></th>
            <th className="num"><Term k="apiErrors">{r.cols.apiErrors}</Term></th>
            <th><Term k="kPerRun">{r.cols.ks}</Term></th>
            <th className="num"><Term k="tokens">{r.cols.tokens}</Term></th>
            <th className="num"><Term k="latency">{r.cols.latency}</Term></th>
            <th className="num"><Term k="cost">{r.cols.cost}</Term></th>
          </tr>
        </thead>
        <tbody>
          {data.apps.flatMap((app) =>
            app.variants.map((v, i) => (
              <tr key={`${app.app}/${v.variant}`}>
                {i === 0 ? <td rowSpan={app.variants.length}>{app.name}</td> : null}
                <td>{t.variants[v.variant] ?? v.variant}</td>
                <td className="num">{fmt.integer(v.accepted)}</td>
                <td className="num">{fmt.integer(v.attempts)}</td>
                <td className="num">{fmt.integer(v.invalid)}</td>
                <td>
                  {parseReasons(v.invalid_reasons)
                    .map(([reason, count]) => `${r.reasons[reason] ?? reason} (${count})`)
                    .join(", ") || t.common.dash}
                </td>
                <td className="num">{fmt.integer(v.api_errors)}</td>
                <td className="mono">{v.k_accepted || t.common.dash}</td>
                <td className="num">
                  {fmt.integer(v.input_tokens)} / {fmt.integer(v.output_tokens)}
                </td>
                <td className="num">{fmt.number(v.latency_s, 1)}</td>
                <td className="num">{fmt.number(v.cost_usd, 4)}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------- metrics by method

export function MetricsSummaryTable({ data, app, variant, allAh }: { data: ResultsPayload; app: ResultApp; variant: string; allAh: boolean }) {
  const { t, fmt } = useI18n();
  const r = t.results.distributions;
  const methods = figureMethods(data, app, allAh);
  const groups = { treatment: r.groupTreatment, controls: r.groupControls, other: r.groupOther, references: r.groupReferences };
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th><Term k="method">{r.method}</Term></th>
            <th className="num"><Term k="n">{t.results.stats.n}</Term></th>
            <th className="num"><Term k="k">K</Term></th>
            {METRICS.map((m) => (
              <th key={m} className="num">
                <Term k={m}>{t.metrics[m]}</Term>
                <span className="direction">{data.analysis.direction[m] > 0 ? `↑ ${t.metrics.higher}` : `↓ ${t.metrics.lower}`}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {methods.map(({ method, group }, i) => {
            const reference = group === "references";
            const row = reference ? data.metrics.find((x) => x.app === app.app && x.method === method && x.variant === null) : undefined;
            const k = reference ? undefined : metricSummary(data, app.app, variant, method, "k");
            const startsGroup = i > 0 && methods[i - 1].group !== group;
            return (
              <tr key={method} className={startsGroup ? "group-start" : undefined}>
                <td>
                  {methodLabel(t, method)}
                  <span className="pkg"> · {groups[group]}</span>
                </td>
                <td className="num">{reference ? 1 : fmt.integer(k?.n)}</td>
                <td className="num">{reference ? fmt.integer(row?.k) : k ? summaryCell(k, (v) => fmt.number(v, kDigits(k))) : t.common.dash}</td>
                {METRICS.map((m) => (
                  <td key={m} className="num">
                    {reference
                      ? fmt.number(row?.[m] ?? null)
                      : summaryCell(metricSummary(data, app.app, variant, method, m), (v) => fmt.number(v, 3)) || t.common.dash}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function ValuesTable({ data, app, variant, allAh }: { data: ResultsPayload; app: ResultApp; variant: string; allAh: boolean }) {
  const { t, fmt } = useI18n();
  const r = t.results.distributions;
  const order = figureMethods(data, app, allAh)
    .filter((m) => m.group !== "references")
    .map((m) => m.method);
  const rows = data.metrics
    .filter((x) => x.app === app.app && x.variant === variant && order.includes(x.method))
    .sort((a, b) => (a.run ?? 0) - (b.run ?? 0) || order.indexOf(a.method) - order.indexOf(b.method));
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th className="num"><Term k="run">{r.run}</Term></th>
            <th><Term k="method">{r.method}</Term></th>
            <th className="num"><Term k="k">{r.k}</Term></th>
            {METRICS.map((m) => (
              <th key={m} className="num">
                <Term k={m}>{t.metrics[m]}</Term>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((x, i) => (
            <tr key={`${x.run}/${x.method}`} className={i > 0 && rows[i - 1].run !== x.run ? "group-start" : undefined}>
              <td className="num">{x.run}</td>
              <td>{methodLabel(t, x.method)}</td>
              <td className="num">{x.k}</td>
              {METRICS.map((m) => (
                <td key={m} className="num">
                  {fmt.number(x[m])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------- paired differences

export function DifferencesTable({ data, scope, variant }: { data: ResultsPayload; scope: string; variant: string }) {
  const { t, fmt } = useI18n();
  const d = t.results.differences;
  const st = t.results.stats;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th><Term k="control">{d.control}</Term></th>
            <th>{d.metric}</th>
            <th className="num"><Term k="n">{st.n}</Term></th>
            <th className="num"><Term k="median">{st.median}</Term></th>
            <th className="num"><Term k="q1q3">{st.q1}</Term></th>
            <th className="num"><Term k="q1q3">{st.q3}</Term></th>
            <th className="num"><Term k="minmax">{st.min}</Term></th>
            <th className="num"><Term k="minmax">{st.max}</Term></th>
            <th className="num"><Term k="signs">{d.signs}</Term></th>
          </tr>
        </thead>
        <tbody>
          {CONTROLS.flatMap((control, c) =>
            METRICS.map((metric, m) => {
              const s = differenceSummary(data, scope, variant, control, metric);
              return (
                <tr key={`${control}/${metric}`} className={c > 0 && m === 0 ? "group-start" : undefined}>
                  {m === 0 ? <td rowSpan={METRICS.length}>{d.controlLabel[control]}</td> : null}
                  <td title={t.metrics.names[metric]}>
                    {t.metrics[metric]}
                    <span className="pkg"> · {data.analysis.direction[metric] > 0 ? `${d.favoursLlm}: d > 0` : `${d.favoursLlm}: d < 0`}</span>
                  </td>
                  <td className="num">{fmt.integer(s?.n)}</td>
                  <td className="num">{fmt.number(s?.median)}</td>
                  <td className="num">{fmt.number(s?.q1)}</td>
                  <td className="num">{fmt.number(s?.q3)}</td>
                  <td className="num">{fmt.number(s?.min)}</td>
                  <td className="num">{fmt.number(s?.max)}</td>
                  <td className="num">{s ? `${s.positive} / ${s.negative} / ${s.zero}` : t.common.dash}</td>
                </tr>
              );
            }),
          )}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------- tests

function Condition({ ok, label, detail }: { ok: boolean; label: string; detail: string }) {
  const { t } = useI18n();
  const x = t.results.tests;
  return (
    <li className={ok ? "condition ok" : "condition no"}>
      <span aria-hidden="true">{ok ? "✓" : "✗"}</span> {label}: <strong>{ok ? x.met : x.notMet}</strong>
      <span className="pkg"> ({detail})</span>
    </li>
  );
}

function CriterionBlock({ set, control, result }: { set: TestSet; control: ControlKey; result: CriterionResult | null | undefined }) {
  const { t, fmt } = useI18n();
  const x = t.results.tests;
  const row = (metric: string) => set.comparisons.find((c) => c.control === control && c.metric === metric);
  const sm = row("sm");
  const unfavourableIn = (metrics: string[]) =>
    metrics
      .map(row)
      .filter((c) => c && c.significant && c.favours === "control")
      .map((c) => `${t.metrics[c!.metric]} (p (Holm) = ${formatP(fmt, c!.p_holm)})`)
      .join(", ");
  const unfavourable = unfavourableIn(["ifn", "icp"]);
  return (
    <div className="criterion">
      <h4>{t.results.differences.controlLabel[control]}</h4>
      {result && sm ? (
        <>
          <ul>
            <Condition ok={result.sm_favours_llm} label={x.conditions[0]} detail={x.detailSm(formatP(fmt, sm.p_holm), x.favours[sm.favours] ?? sm.favours)} />
            <Condition
              ok={result.sm_effect_at_least_small}
              label={x.conditions[1]}
              detail={x.detailDelta(fmt.number(sm.cliffs_delta), sm.magnitude ? (x.magnitudes[sm.magnitude] ?? sm.magnitude) : t.common.dash)}
            />
            <Condition ok={result.no_unfavourable_ifn_icp} label={x.conditions[2]} detail={x.detailUnfavourable(unfavourable)} />
            <Condition ok={result.no_unfavourable_ned} label={x.conditions[3]} detail={x.detailUnfavourable(unfavourableIn(["ned"]))} />
          </ul>
          <p className="verdict">
            <Term k="criterion">{x.adoptedLabel}</Term>: {result.llm_superior ? x.verdictYes : x.verdictNo}
          </p>
          <p className="pkg">
            <Term k="criterionRoteiro">{x.roteiroLabel}</Term>: {result.llm_superior_roteiro ? x.verdictYes : x.verdictNo}
          </p>
        </>
      ) : (
        <p className="note">{x.notEvaluable}</p>
      )}
    </div>
  );
}

export function TestsTable({ set }: { set: TestSet }) {
  const { t, fmt } = useI18n();
  const x = t.results.tests;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th><Term k="control">{x.cols.control}</Term></th>
            <th>{x.cols.metric}</th>
            <th className="num"><Term k="n">{x.cols.n}</Term></th>
            <th className="num"><Term k="shapiro">{x.cols.normality}</Term></th>
            <th><Term k="testUsed">{x.cols.test}</Term></th>
            <th className="num"><Term k="statistic">{x.cols.statistic}</Term></th>
            <th className="num"><Term k="pValue">{x.cols.p}</Term></th>
            <th className="num"><Term k="pHolm">{x.cols.pHolm}</Term></th>
            <th><Term k="significant">{x.cols.significant}</Term></th>
            <th className="num"><Term k="location">{x.cols.location}</Term></th>
            <th className="num"><Term k="cliff">{x.cols.delta}</Term></th>
            <th><Term k="magnitude">{x.cols.magnitude}</Term></th>
            <th><Term k="favours">{x.cols.favours}</Term></th>
          </tr>
        </thead>
        <tbody>
          {set.comparisons.map((row, i) => {
            const location = row.test === "t" ? row.mean_diff : row.median_diff;
            return (
              <tr key={`${row.control}/${row.metric}`} className={i > 0 && set.comparisons[i - 1].control !== row.control ? "group-start" : undefined}>
                <td>{t.results.differences.controlLabel[row.control]}</td>
                <td>{t.metrics[row.metric]}</td>
                <td className="num">{fmt.integer(row.n)}</td>
                <td className="num">{formatP(fmt, row.normality_p)}</td>
                <td>{x.testNames[row.test] ?? row.test}</td>
                <td className="num">{fmt.number(row.statistic)}</td>
                <td className="num">{formatP(fmt, row.p_value)}</td>
                <td className={row.significant ? "num best" : "num"}>{formatP(fmt, row.p_holm)}</td>
                <td>{row.p_holm === null ? t.common.dash : row.significant ? t.common.yes : t.common.no}</td>
                <td className="num">
                  {fmt.number(location)}
                  {row.test in x.locationKind ? <span className="pkg"> ({x.locationKind[row.test]})</span> : null}
                </td>
                <td className="num">{fmt.number(row.cliffs_delta)}</td>
                <td>{row.magnitude ? (x.magnitudes[row.magnitude] ?? row.magnitude) : t.common.dash}</td>
                <td>{x.favours[row.favours] ?? row.favours}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function CriterionSection({ set }: { set: TestSet }) {
  const { t } = useI18n();
  const x = t.results.tests;
  return (
    <div className="criteria">
      <h3>
        <Term k="criterion">{x.criterionTitle}</Term>
      </h3>
      <p className="note">{x.criterionText}</p>
      <div className="criteria-grid">
        {CONTROLS.map((control) => (
          <CriterionBlock key={control} set={set} control={control} result={set.criterion[control]} />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- AH selection and stability

export function AhSelectionTable({ data }: { data: ResultsPayload }) {
  const { t, fmt } = useI18n();
  const a = t.results.ahSelection;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th><Term k="app">{a.cols.app}</Term></th>
            <th><Term k="ahVariant">{a.cols.variant}</Term></th>
            <th className="num"><Term k="run">{a.cols.runs}</Term></th>
            <th className="num"><Term k="medianSm">{a.cols.medianSm}</Term></th>
            <th><Term k="ahSelected">{a.cols.selected}</Term></th>
            <th><Term k="rule">{a.cols.rule}</Term></th>
          </tr>
        </thead>
        <tbody>
          {data.apps.flatMap((app) =>
            app.ah_selection.map((row, i) => (
              <tr key={`${app.app}/${row.variant}`} className={row.selected ? "hl" : undefined}>
                {i === 0 ? <td rowSpan={app.ah_selection.length}>{app.name}</td> : null}
                <td>{methodLabel(t, row.variant)}</td>
                <td className="num">{fmt.integer(row.runs)}</td>
                <td className={row.selected ? "num best" : "num"}>{fmt.number(row.median_sm)}</td>
                <td>{row.selected ? t.common.yes : t.common.no}</td>
                <td>{a.rules[row.rule] ?? row.rule}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </div>
  );
}

export function StabilityTable({ data }: { data: ResultsPayload }) {
  const { t, fmt } = useI18n();
  const s = t.results.stability;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th><Term k="app">{s.cols.app}</Term></th>
            <th><Term k="variant">{s.cols.variant}</Term></th>
            <th className="num"><Term k="run">{s.cols.runs}</Term></th>
            <th className="num"><Term k="distinctPartitions">{s.cols.distinct}</Term></th>
            <th><Term k="groupsOfRuns">{s.cols.groups}</Term></th>
            <th className="num"><Term k="ari">{s.cols.meanAri}</Term></th>
            <th className="num"><Term k="ari">{s.cols.minAri}</Term></th>
            <th />
          </tr>
        </thead>
        <tbody>
          {data.apps.flatMap((app) =>
            app.variants.map((v, i) => (
              <tr key={`${app.app}/${v.variant}`}>
                {i === 0 ? <td rowSpan={app.variants.length}>{app.name}</td> : null}
                <td>{t.variants[v.variant] ?? v.variant}</td>
                <td className="num">{fmt.integer(v.stability?.runs)}</td>
                <td className="num">{fmt.integer(v.stability?.distinct_partitions)}</td>
                <td className="mono">{v.stability?.groups_of_runs || t.common.dash}</td>
                <td className="num">{fmt.number(v.stability?.mean_ari ?? null)}</td>
                <td className="num">{fmt.number(v.stability?.min_ari ?? null)}</td>
                <td>
                  <a href={hrefFor("decompositions", { study: `${data.experiment}/${app.app}/${data.profile}`, variant: v.variant })}>{s.open}</a>
                </td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </div>
  );
}
