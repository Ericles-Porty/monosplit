import { queryPath, useResource } from "../../api/client";
import type { AttemptDetail, AttemptPage, DataStudy } from "../../api/types";
import { Field } from "../../components/forms";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";
import { useDataRoute, utcText } from "./DataPage";

const LIMIT = 50;
const STATUSES = ["accepted", "invalid", "api_error"];
const VARIANTS = ["original", "obfuscated"];

function unique(values: string[]): string[] {
  return [...new Set(values)].sort();
}

export function AttemptsTab({ database, params }: { database: string; params: Record<string, string> }) {
  const { t, fmt } = useI18n();
  const a = t.data.attempts;
  const go = useDataRoute(params);
  const studies = useResource<{ studies: DataStudy[] }>(`data/${database}/studies`);
  const skip = Math.max(0, Number(params.skip) || 0);
  const filters = {
    experiment: params.experiment ?? "",
    app: params.app ?? "",
    profile: params.profile ?? "",
    variant: params.variant ?? "",
    status: params.status ?? "",
  };
  const page = useResource<AttemptPage>(
    queryPath(`data/${database}/attempts`, {
      experiment: filters.experiment,
      app_id: filters.app,
      profile: filters.profile,
      variant: filters.variant,
      status: filters.status,
      skip,
      limit: LIMIT,
    }),
  );
  const selected = params.attempt ? params.attempt.split("/") : null;
  const list = studies.data?.studies ?? [];
  const options = {
    experiment: unique(list.map((s) => s.experiment)),
    app: unique(list.map((s) => s.app)),
    profile: unique(list.map((s) => s.profile)),
  };

  const select = (key: keyof typeof filters, values: string[], label: string, help: Parameters<typeof Term>[0]["k"], names?: Record<string, string>) => (
    <Field label={label} help={help}>
      <select value={filters[key]} onChange={(event) => go({ [key]: event.target.value || null, skip: null, attempt: null })}>
        <option value="">{a.all}</option>
        {values.map((value) => (
          <option key={value} value={value}>
            {names?.[value] ?? value}
          </option>
        ))}
      </select>
    </Field>
  );

  const rows = page.data?.rows ?? [];
  const total = page.data?.total ?? 0;
  return (
    <>
      <div className="filters">
        {select("experiment", options.experiment, a.experiment, "experiment")}
        {select("app", options.app, t.data.edges.app, "app")}
        {select("profile", options.profile, a.profile, "profile")}
        {select("variant", VARIANTS, t.data.studies.variant, "variant", t.variantsShort)}
        {select("status", STATUSES, a.status, "attemptStatus", a.statuses)}
      </div>
      <p className="note">{a.readOnly}</p>
      {page.error ? <p className="error">{page.error.message}</p> : null}
      <div className="split wide-left">
        <div>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>
                    <Term k="study">{t.data.studies.study}</Term>
                  </th>
                  <th className="num">
                    <Term k="attempt">{a.attempt}</Term>
                  </th>
                  <th className="num">
                    <Term k="run">{a.run}</Term>
                  </th>
                  <th className="num">
                    <Term k="tryNumber">{a.try}</Term>
                  </th>
                  <th>
                    <Term k="attemptStatus">{a.status}</Term>
                  </th>
                  <th>
                    <Term k="reasons">{a.reason}</Term>
                  </th>
                  <th className="num">
                    <Term k="k">{a.k}</Term>
                  </th>
                  <th className="num">
                    <Term k="tokens">{a.tokens}</Term>
                  </th>
                  <th className="num">
                    <Term k="cost">{a.cost}</Term>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const id = `${row.experiment}/${row.app}/${row.profile}/${row.variant}/${row.attempt}`;
                  return (
                    <tr
                      key={id}
                      className={`clickable${params.attempt === id ? " selected" : ""}`}
                      tabIndex={0}
                      onClick={() => go({ attempt: id })}
                      onKeyDown={(event) => (event.key === "Enter" ? go({ attempt: id }) : undefined)}
                    >
                      <td className="nowrap">
                        <span className="mono pkg">
                          {row.experiment}/{row.app}/{row.profile}
                        </span>{" "}
                        · {t.variantsShort[row.variant] ?? row.variant}
                      </td>
                      <td className="num">{row.attempt}</td>
                      <td className="num">{row.run ?? t.common.dash}</td>
                      <td className="num">{row.try ?? t.common.dash}</td>
                      <td>{a.statuses[row.status] ?? row.status}</td>
                      <td className="mono pkg">{row.reason ?? ""}</td>
                      <td className="num">{row.k ?? t.common.dash}</td>
                      <td className="num">
                        {fmt.integer(row.input_tokens)} / {fmt.integer(row.output_tokens)}
                      </td>
                      <td className="num">{fmt.number(row.cost_usd, 4)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {page.data && !rows.length ? <p className="note">{a.none}</p> : null}
          {total ? (
            <div className="inline" style={{ marginTop: 8 }}>
              <span className="note">{a.range(skip + 1, Math.min(skip + LIMIT, total), total)}</span>
              <button type="button" className="button" disabled={skip === 0} onClick={() => go({ skip: Math.max(0, skip - LIMIT) || null })}>
                {a.previous}
              </button>
              <button type="button" className="button" disabled={skip + LIMIT >= total} onClick={() => go({ skip: skip + LIMIT })}>
                {a.next}
              </button>
            </div>
          ) : null}
        </div>
        <div className="panel">
          {selected && selected.length === 5 ? <AttemptPanel database={database} id={selected} /> : <p className="note">{a.pick}</p>}
        </div>
      </div>
    </>
  );
}

function AttemptPanel({ database, id }: { database: string; id: string[] }) {
  const { t, fmt } = useI18n();
  const a = t.data.attempts;
  const [experiment, app, profile, variant, attempt] = id;
  const detail = useResource<AttemptDetail>(`data/${database}/attempt/${experiment}/${app}/${profile}/${variant}/${attempt}`);
  if (detail.error) return <p className="error">{detail.error.message}</p>;
  if (!detail.data) return <p className="note">{t.common.loading}</p>;
  const doc = detail.data;
  const partition = [...(doc.accepted?.partition ?? [])].sort((x, y) => x.service - y.service || x.class.localeCompare(y.class));
  const text = typeof doc.raw?.text === "string" ? doc.raw.text : "";
  return (
    <div>
      <h3>{a.detailTitle(doc.attempt, t.variantsShort[doc.variant] ?? doc.variant)}</h3>
      <table className="data">
        <tbody>
          <tr>
            <th>
              <Term k="attemptStatus">{a.status}</Term>
            </th>
            <td>
              {a.statuses[doc.status] ?? doc.status}
              {doc.reason ? ` · ${doc.reason}` : ""}
            </td>
          </tr>
          {doc.detail ? (
            <tr>
              <th>{a.detail}</th>
              <td className="mono pkg">{doc.detail}</td>
            </tr>
          ) : null}
          <tr>
            <th>
              <Term k="modelReported">{a.model}</Term>
            </th>
            <td className="mono">{doc.model_returned ?? t.common.dash}</td>
          </tr>
          <tr>
            <th>{a.finish}</th>
            <td className="mono">{String(doc.finish_reason ?? t.common.dash)}</td>
          </tr>
          <tr>
            <th>
              <Term k="tokens">{a.tokens}</Term>
            </th>
            <td>
              {fmt.integer(doc.input_tokens)} / {fmt.integer(doc.output_tokens)}
            </td>
          </tr>
          <tr>
            <th>
              <Term k="latency">{a.latency}</Term>
            </th>
            <td>{fmt.number(doc.latency_s, 1)}</td>
          </tr>
          <tr>
            <th>{a.when}</th>
            <td>{utcText(doc.timestamp_utc)}</td>
          </tr>
        </tbody>
      </table>
      <h4 style={{ margin: "14px 0 0" }}>
        <Term k="answerText">{a.answer}</Term>
      </h4>
      <pre className="output wrap">{text || t.common.dash}</pre>
      {partition.length ? (
        <>
          <h4 style={{ margin: "14px 0 6px" }}>
            <Term k="acceptedPartition">{a.partition}</Term>
          </h4>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>{a.service}</th>
                  <th>{a.className}</th>
                </tr>
              </thead>
              <tbody>
                {partition.map((item) => (
                  <tr key={item.class}>
                    <td>
                      {item.service + 1}
                      {doc.accepted?.services[item.service] ? ` · ${doc.accepted.services[item.service]}` : ""}
                    </td>
                    <td className="mono pkg">{item.class}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
      <details className="block">
        <summary>
          <Term k="rawResponse">{a.rawResponse}</Term>
        </summary>
        <div className="block-body">
          <pre className="output">{JSON.stringify(doc.raw?.raw ?? doc.raw, null, 2)}</pre>
        </div>
      </details>
    </div>
  );
}
