import { useEffect, useMemo, useState } from "react";

import { send, useResource } from "../../api/client";
import type { ConfigSummary, Estimate, IndexPayload } from "../../api/types";
import { Notice, toFormError } from "../../components/forms";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";
import { JobsList } from "./JobsList";
import { useJobs } from "./useJobs";

type Operation = "full" | "llm" | "evaluate";

export function ExecutionPage({ params }: { params: Record<string, string> }) {
  const { t } = useI18n();
  const x = t.execution;
  const summary = useResource<ConfigSummary>("config");
  const index = useResource<IndexPayload>("index");
  const jobs = useJobs();
  const knownStudies = new Set(index.data?.studies.map((s) => s.id) ?? []);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const submit = async (body: Record<string, unknown>) => {
    setMessage(null);
    try {
      await send("POST", "jobs", body);
      setMessage({ kind: "ok", text: jobs.busy ? x.queuedNote : x.submitted });
      jobs.refresh();
    } catch (error) {
      setMessage({ kind: "error", text: toFormError(error).message });
    }
  };

  return (
    <>
      <h2>{x.title}</h2>
      <p className="lead">{x.intro}</p>
      {message ? (
        <div style={{ marginTop: 10 }}>
          <Notice kind={message.kind}>{message.text}</Notice>
        </div>
      ) : null}
      {summary.error ? <p className="error">{summary.error.message}</p> : null}
      {summary.data ? (
        <>
          <section className="section">
            <h2>
              <Term k="extractGraph">{x.graphs}</Term>
            </h2>
            <AppGraphs summary={summary.data} highlight={params.app ?? null} onExtract={(app) => submit({ kind: "extract", app })} />
          </section>
          <section className="section">
            <h2>{x.study}</h2>
            <StudyRunner summary={summary.data} jobsVersion={jobs.jobs.length + (jobs.busy ? 1 : 0)} onSubmit={submit} />
          </section>
          <section className="section">
            <h2>
              <Term k="dryRun">{x.dryRun}</Term>
            </h2>
            <p className="note">{x.dryRunText}</p>
            <button type="button" className="button" onClick={() => submit({ kind: "dry_run" })} style={{ marginTop: 6 }}>
              {x.dryRunButton}
            </button>
          </section>
        </>
      ) : (
        <p className="note">{t.common.loading}</p>
      )}
      <section className="section">
        <h2>
          <Term k="jobs">{x.jobs}</Term>
        </h2>
        {jobs.error ? <p className="error">{jobs.error.message}</p> : null}
        <JobsList jobs={jobs.jobs} knownStudies={knownStudies} onChange={jobs.refresh} />
      </section>
    </>
  );
}

function AppGraphs({ summary, highlight, onExtract }: { summary: ConfigSummary; highlight: string | null; onExtract: (app: string) => void }) {
  const { t } = useI18n();
  const a = t.config.apps;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th>{a.name}</th>
            <th>
              <Term k="commit">{t.overview.cols.commit}</Term>
            </th>
            <th>
              <Term k="build">{a.build}</Term>
            </th>
            <th>
              <Term k="appStatus">{a.status}</Term>
            </th>
            <th />
          </tr>
        </thead>
        <tbody>
          {summary.apps.map((app) => (
            <tr key={app.id} className={app.id === highlight ? "selected" : undefined}>
              <td>
                {app.name} <span className="pkg">{app.id}</span>
              </td>
              <td className="mono">
                {app.tag ?? ""} {app.commit.slice(0, 7)}
              </td>
              <td>{a.buildTypes[app.build] ?? app.build}</td>
              <td>
                {app.status.fetched ? a.fetched : a.notFetched} ·{" "}
                {app.status.graph ? a.graph(app.status.graph.classes, app.status.graph.edges ?? 0) : a.noGraph}
              </td>
              <td className="actions-cell">
                <button type="button" className="button" onClick={() => onExtract(app.id)}>
                  {app.status.graph ? t.execution.reextract : t.execution.extract}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StudyRunner(props: { summary: ConfigSummary; jobsVersion: number; onSubmit: (body: Record<string, unknown>) => Promise<void> }) {
  const { t, fmt } = useI18n();
  const x = t.execution;
  const experiments = props.summary.experiments.filter((e) => e.valid && e.data);
  const profiles = props.summary.profiles.filter((p) => !p.template && p.valid);
  const [file, setFile] = useState(experiments[0]?.id ?? "");
  const experiment = experiments.find((e) => e.id === file);
  const defaultProfile = experiment?.data?.llm ?? "";
  const [profile, setProfile] = useState(defaultProfile || profiles.find((p) => p.data?.provider !== "fake")?.name || profiles[0]?.name || "");
  const [variants, setVariants] = useState<string[]>(experiment?.data?.variants ?? []);
  const [operation, setOperation] = useState<Operation>("full");
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [estimateError, setEstimateError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const profileEntry = profiles.find((p) => p.name === profile);
  const providerInfo = props.summary.providers.find((p) => p.provider === profileEntry?.data?.provider);
  // Confirmation only when the job can call a paid model: something left to run and a provider that bills
  // (not the fake client nor a local model).
  const paid = operation !== "evaluate" && (providerInfo?.paid ?? true) && (estimate?.missing_runs ?? 1) > 0;

  useEffect(() => {
    setVariants(experiment?.data?.variants ?? []);
    if (defaultProfile) setProfile(defaultProfile);
  }, [file]);

  const request = useMemo(() => ({ config: file, profile, variants }), [file, profile, variants]);
  useEffect(() => {
    setConfirming(false);
    if (!file || !profile || !variants.length) {
      setEstimate(null);
      return;
    }
    let active = true;
    setEstimateError(null);
    send<Estimate>("POST", "jobs/estimate", request).then(
      (answer) => active && setEstimate(answer),
      (error) => {
        if (!active) return;
        setEstimate(null);
        setEstimateError(toFormError(error).message);
      },
    );
    return () => {
      active = false;
    };
  }, [request, file, profile, variants.length, props.jobsVersion]);

  const start = async () => {
    if (paid && !confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    await props.onSubmit({ kind: operation, ...request, confirm: estimate?.token });
  };

  const toggle = (variant: string) =>
    setVariants(variants.includes(variant) ? variants.filter((v) => v !== variant) : [...variants, variant]);

  return (
    <div className="form">
      <div className="form-grid">
        <label className="field">
          <span className="label">
            <Term k="experiment">{x.experiment}</Term>
          </span>
          <select value={file} onChange={(event) => setFile(event.target.value)}>
            {experiments.map((e) => (
              <option key={e.id} value={e.id}>
                {e.id} · {e.data?.name} · {e.data?.app}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="label">
            <Term k="profile">{x.profile}</Term>
          </span>
          <select value={profile} onChange={(event) => setProfile(event.target.value)}>
            {profiles.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name} · {p.data?.provider} · {p.data?.model}
              </option>
            ))}
          </select>
        </label>
        <div className="field">
          <span className="label">
            <Term k="variant">{x.variants}</Term>
          </span>
          <div className="checks">
            {(experiment?.data?.variants ?? []).map((v) => (
              <label key={v} className="check">
                <input type="checkbox" checked={variants.includes(v)} onChange={() => toggle(v)} />
                {t.variants[v] ?? v}
              </label>
            ))}
          </div>
        </div>
        <div className="field">
          <span className="label">
            <Term k="operation">{x.operation}</Term>
          </span>
          <select value={operation} onChange={(event) => setOperation(event.target.value as Operation)}>
            {(["full", "llm", "evaluate"] as Operation[]).map((op) => (
              <option key={op} value={op}>
                {x.operations[op]}
              </option>
            ))}
          </select>
        </div>
      </div>

      {estimateError ? <Notice kind="error">{estimateError}</Notice> : null}
      {estimate && operation !== "evaluate" ? (
        <div>
          <h3 style={{ margin: "6px 0" }}>
            <Term k="estimate">{x.estimateTitle}</Term>
          </h3>
          <p className="note mono">
            {x.model}: {estimate.provider} · {estimate.model}
          </p>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>
                    <Term k="variant">{x.cols.variant}</Term>
                  </th>
                  <th className="num">
                    <Term k="accepted">{x.cols.accepted}</Term>
                  </th>
                  <th className="num">
                    <Term k="missing">{x.cols.missing}</Term>
                  </th>
                  <th className="num">
                    <Term k="tokensPerAttempt">{x.cols.tokensIn}</Term>
                  </th>
                  <th className="num">
                    <Term k="tokensPerAttempt">{x.cols.tokensOut}</Term>
                  </th>
                  <th className="num">
                    <Term k="attemptsExpected">{x.cols.attempts}</Term>
                  </th>
                  {estimate.paid ? (
                    <>
                      <th className="num">
                        <Term k="expectedCost">{x.cols.expected}</Term>
                      </th>
                      <th className="num">
                        <Term k="maxCost">{x.cols.max}</Term>
                      </th>
                    </>
                  ) : (
                    <>
                      <th className="num">
                        <Term k="secondsPerAttempt">{x.cols.secondsPerAttempt}</Term>
                      </th>
                      <th className="num">
                        <Term k="expectedTime">{x.cols.expectedTime}</Term>
                      </th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {estimate.variants.map((row) => (
                  <tr key={row.variant}>
                    <td>{t.variants[row.variant] ?? row.variant}</td>
                    <td className="num">
                      {row.accepted} / {row.target}
                    </td>
                    <td className="num">{row.missing}</td>
                    <td className="num">
                      {fmt.integer(row.input_tokens_per_attempt)} <span className="pkg">{row.observed ? x.observed : x.approximate}</span>
                    </td>
                    <td className="num">
                      {fmt.integer(row.output_tokens_per_attempt)} <span className="pkg">{row.observed ? x.observed : x.approximate}</span>
                    </td>
                    <td className="num">
                      {fmt.number(row.expected_attempts, 1)} / {fmt.integer(row.max_attempts)}
                    </td>
                    {estimate.paid ? (
                      <>
                        <td className="num">{fmt.number(row.expected_cost_usd, 4)}</td>
                        <td className="num">{fmt.number(row.max_cost_usd, 4)}</td>
                      </>
                    ) : (
                      <>
                        <td className="num">{fmt.duration(row.seconds_per_attempt)}</td>
                        <td className="num">{fmt.duration(row.expected_seconds)}</td>
                      </>
                    )}
                  </tr>
                ))}
                <tr>
                  <td>
                    <strong>{x.total}</strong>
                  </td>
                  <td />
                  <td className="num">{estimate.missing_runs}</td>
                  <td />
                  <td />
                  <td />
                  {estimate.paid ? (
                    <>
                      <td className="num">
                        <strong>{fmt.number(estimate.expected_cost_usd, 4)}</strong>
                      </td>
                      <td className="num">
                        <strong>{fmt.number(estimate.max_cost_usd, 4)}</strong>
                      </td>
                    </>
                  ) : (
                    <>
                      <td />
                      <td className="num">
                        <strong>{fmt.duration(estimate.expected_seconds)}</strong>
                      </td>
                    </>
                  )}
                </tr>
              </tbody>
            </table>
          </div>
          <div className="form" style={{ marginTop: 8, gap: 6 }}>
            {estimate.problem ? <Notice kind="error">{x.problem(estimate.problem)}</Notice> : null}
            {!estimate.priced && estimate.paid ? <Notice kind="warn">{x.noPricing}</Notice> : null}
            {!estimate.paid && estimate.provider !== "fake" ? <p className="note">{x.free}</p> : null}
            {estimate.key_present === false ? <Notice kind="error">{x.keyMissing}</Notice> : null}
            {estimate.key_present === true ? <p className="note">{x.keyFound}</p> : null}
            {estimate.paid && estimate.variants.some((r) => !r.observed) ? (
              <p className="note">{x.assumptions(estimate.defaults.output_tokens, estimate.defaults.attempts_per_run)}</p>
            ) : null}
            {!estimate.paid && estimate.variants.some((r) => r.missing > 0 && r.seconds_per_attempt === null) ? (
              <p className="note">{x.timeUnknown}</p>
            ) : null}
            {estimate.missing_runs === 0 ? <p className="note">{x.nothingToRun}</p> : null}
          </div>
        </div>
      ) : null}

      {confirming ? (
        <div className="confirm">
          <strong>{x.confirmTitle}</strong>
          <p style={{ margin: "6px 0" }}>
            {estimate?.priced
              ? x.confirmText(fmt.number(estimate.max_cost_usd, 4), fmt.number(estimate.expected_cost_usd, 4))
              : x.confirmUnpriced}
          </p>
          <div className="actions">
            <button type="button" className="button primary" onClick={start}>
              {x.confirmButton}
            </button>
            <button type="button" className="button" onClick={() => setConfirming(false)}>
              {t.config.cancel}
            </button>
          </div>
        </div>
      ) : (
        <div className="actions">
          <button type="button" className="button primary" onClick={start}
            disabled={!file || !profile || !variants.length || (operation !== "evaluate" && !estimate)}>
            {x.start}
          </button>
        </div>
      )}
    </div>
  );
}
