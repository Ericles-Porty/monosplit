import { useState } from "react";

import { invalidate, send } from "../../api/client";
import type { ConfigSummary, ExperimentData, ExperimentEntry } from "../../api/types";
import { Field, Notice, integerOrNull, toFormError, type FormError } from "../../components/forms";
import type { HelpKey } from "../../i18n/messages-help";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";
import { methodLabel } from "../../lib/methods";

type Editing = { mode: "create" | "edit"; id: string; data: ExperimentData; studies: string[] };

const LOCKED = ["name", "app", "seed", "max_retries", "prompt_template", "database"];

function emptyExperiment(summary: ConfigSummary): ExperimentData {
  return {
    name: "",
    app: summary.apps[0]?.id ?? "",
    seed: Math.floor(Date.now() / 1000),
    accepted_runs: 10,
    max_retries: 3,
    max_failed_runs: 10,
    variants: ["original", "obfuscated"],
    database: "monosplit",
    llm: null,
    prompt_template: summary.prompts[summary.prompts.length - 1]?.name ?? "",
    ah_variants: [...summary.ah_variants],
    ah_primary: "auto",
    hdbscan_min_cluster_size: 2,
    inferential: false,
    note: "",
  };
}

export function ExperimentsTab({ summary }: { summary: ConfigSummary }) {
  const { t } = useI18n();
  const c = t.config;
  const [editing, setEditing] = useState<Editing | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const remove = async (entry: ExperimentEntry) => {
    if (!window.confirm(c.confirmRemove(entry.id))) return;
    try {
      await send("DELETE", `config/experiments/${entry.id}`);
      invalidate();
      setMessage({ kind: "ok", text: c.removed(entry.id) });
    } catch (error) {
      setMessage({ kind: "error", text: toFormError(error).message });
    }
  };

  return (
    <div className="split">
      <div>
        <p className="note">{c.experiments.intro}</p>
        {message ? <Notice kind={message.kind}>{message.text}</Notice> : null}
        <div className="inline" style={{ margin: "10px 0" }}>
          <button type="button" className="button" onClick={() => setEditing({ mode: "create", id: "", data: emptyExperiment(summary), studies: [] })}>
            {c.new}
          </button>
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>
                  <Term k="experimentId">{c.experiments.id}</Term>
                </th>
                <th>
                  <Term k="app">{c.experiments.app}</Term>
                </th>
                <th className="num">
                  <Term k="acceptedRuns">{c.experiments.runs}</Term>
                </th>
                <th>
                  <Term k="variant">{c.experiments.variants}</Term>
                </th>
                <th>
                  <Term k="usage">{c.usage}</Term>
                </th>
                <th />
              </tr>
            </thead>
            <tbody>
              {summary.experiments.map((e) => (
                <tr key={e.id} className={editing?.id === e.id ? "selected" : undefined}>
                  <td>
                    <strong>{e.id}</strong>
                    {e.protected ? <span className="chip"> <Term k="protectedDefault">{c.protectedChip}</Term></span> : null}
                    {!e.valid ? <span className="chip failed"> {c.invalid}</span> : null}
                    <div className="pkg mono">
                      {e.data?.name} · {e.data?.prompt_template}
                    </div>
                  </td>
                  <td>{e.data?.app}</td>
                  <td className="num">{e.data?.accepted_runs}</td>
                  <td>{e.data?.variants.map((v) => t.variantsShort[v] ?? v).join(", ")}</td>
                  <td className="pkg">{e.studies?.length ? e.studies.join(", ") : c.none}</td>
                  <td className="actions-cell">
                    <button type="button" className="button" disabled={!e.data}
                      onClick={() => e.data && setEditing({ mode: "edit", id: e.id, data: e.data, studies: e.studies ?? [] })}>
                      {c.edit}
                    </button>{" "}
                    <button type="button" className="button" disabled={!e.data}
                      onClick={() => e.data && setEditing({ mode: "create", id: `${e.id}-2`, data: { ...e.data, name: `${e.data.name}-2` }, studies: [] })}>
                      {c.duplicate}
                    </button>{" "}
                    <button type="button" className="button danger" onClick={() => remove(e)} disabled={Boolean(e.studies?.length) || e.protected}>
                      {c.remove}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="panel">
        {editing ? (
          <ExperimentForm
            key={`${editing.mode}:${editing.id}`}
            summary={summary}
            editing={editing}
            onCancel={() => setEditing(null)}
            onSaved={(id) => {
              setMessage({ kind: "ok", text: c.saved(id) });
              setEditing(null);
            }}
          />
        ) : (
          <p className="note">{c.experiments.intro}</p>
        )}
      </div>
    </div>
  );
}

function ExperimentForm(props: { summary: ConfigSummary; editing: Editing; onCancel: () => void; onSaved: (id: string) => void }) {
  const { t } = useI18n();
  const c = t.config;
  const e = c.experiments;
  const { summary, editing } = props;
  const [id, setId] = useState(editing.id);
  const [data, setData] = useState<ExperimentData>(editing.data);
  const [numbers, setNumbers] = useState({
    seed: String(editing.data.seed ?? ""),
    accepted_runs: String(editing.data.accepted_runs ?? ""),
    max_retries: String(editing.data.max_retries ?? ""),
    max_failed_runs: String(editing.data.max_failed_runs ?? ""),
    hdbscan_min_cluster_size: String(editing.data.hdbscan_min_cluster_size ?? ""),
  });
  const [error, setError] = useState<FormError | null>(null);
  const [busy, setBusy] = useState(false);
  const locked = editing.studies.length > 0;
  const lock = (field: string) => (locked && LOCKED.includes(field) ? c.lockedField : null);
  const set = (patch: Partial<ExperimentData>) => setData({ ...data, ...patch });
  const toggle = (list: string[], value: string) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  const profiles = summary.profiles.filter((p) => !p.template);

  const save = async () => {
    setError(null);
    const payload: ExperimentData = {
      ...data,
      seed: integerOrNull(numbers.seed),
      accepted_runs: integerOrNull(numbers.accepted_runs),
      max_retries: integerOrNull(numbers.max_retries) ?? Number.NaN,
      max_failed_runs: integerOrNull(numbers.max_failed_runs),
      hdbscan_min_cluster_size: integerOrNull(numbers.hdbscan_min_cluster_size) ?? Number.NaN,
    };
    setBusy(true);
    try {
      await send("PUT", `config/experiments/${encodeURIComponent(id.trim())}`, { data: payload, create: editing.mode === "create" });
      invalidate();
      props.onSaved(id.trim());
    } catch (failure) {
      setError(toFormError(failure));
    } finally {
      setBusy(false);
    }
  };

  const numberField = (key: keyof typeof numbers, label: string, help: HelpKey) => (
    <Field label={label} help={help} name={key} error={error} lockNote={lock(key)}>
      <input className="input" inputMode="numeric" value={numbers[key]} disabled={Boolean(lock(key))}
        onChange={(event) => setNumbers({ ...numbers, [key]: event.target.value })} />
    </Field>
  );

  return (
    <div className="form">
      <h3>{editing.mode === "create" ? c.newTitle : c.editTitle(editing.id)}</h3>
      {locked ? <Notice kind="warn">{c.locked(editing.studies.join(", "))}</Notice> : null}
      {error && !error.field ? <Notice kind="error">{error.message}</Notice> : null}
      <div className="form-grid">
        <Field label={e.id} help="experimentId" name="id" error={error} hint={e.idHint}>
          <input className="input" value={id} onChange={(event) => setId(event.target.value)} disabled={editing.mode === "edit"} />
        </Field>
        <Field label={e.name} help="experimentName" name="name" error={error} hint={e.nameHint} lockNote={lock("name")}>
          <input className="input" value={data.name} onChange={(event) => set({ name: event.target.value })} disabled={Boolean(lock("name"))} />
        </Field>
        <Field label={e.app} help="app" name="app" error={error} lockNote={lock("app")}>
          <select value={data.app} onChange={(event) => set({ app: event.target.value })} disabled={Boolean(lock("app"))}>
            {summary.apps.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.id})
              </option>
            ))}
          </select>
        </Field>
        <Field label={e.prompt} help="promptVersion" name="prompt_template" error={error} lockNote={lock("prompt_template")}>
          <select value={data.prompt_template} onChange={(event) => set({ prompt_template: event.target.value })} disabled={Boolean(lock("prompt_template"))}>
            {summary.prompts.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
        </Field>
        {numberField("seed", e.seed, "masterSeed")}
        {numberField("accepted_runs", e.acceptedRuns, "acceptedRuns")}
        {numberField("max_retries", e.maxRetries, "maxRetries")}
        {numberField("max_failed_runs", e.maxFailedRuns, "maxFailedRuns")}
        <Field label={e.variants} help="variant" name="variants" error={error}>
          <div className="checks">
            {summary.variants.map((v) => (
              <label key={v} className="check">
                <input type="checkbox" checked={data.variants.includes(v)} onChange={() => set({ variants: toggle(data.variants, v) })} />
                {t.variants[v] ?? v}
              </label>
            ))}
          </div>
        </Field>
        <Field label={e.database} help="database" name="database" error={error} lockNote={lock("database")}>
          <input className="input" value={data.database} onChange={(event) => set({ database: event.target.value })} disabled={Boolean(lock("database"))} />
        </Field>
        <Field label={e.profile} help="defaultProfile" name="llm" error={error} wide>
          <select value={data.llm ?? ""} onChange={(event) => set({ llm: event.target.value || null })}>
            <option value="">{e.noProfile}</option>
            {profiles.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <fieldset>
        <legend>
          <Term k="ahVariants">{e.ahVariants}</Term>
        </legend>
        <div className="checks">
          {summary.ah_variants.map((v) => (
            <label key={v} className="check">
              <input type="checkbox" checked={data.ah_variants.includes(v)} onChange={() => set({ ah_variants: toggle(data.ah_variants, v) })} />
              {methodLabel(t, `ah:${v}`)}
            </label>
          ))}
        </div>
        {error?.field === "ah_variants" ? <span className="field-error">{error.message}</span> : null}
      </fieldset>
      <div className="form-grid">
        <Field label={e.ahPrimary} help="ahPrimary" name="ah_primary" error={error}>
          <select value={data.ah_primary} onChange={(event) => set({ ah_primary: event.target.value })}>
            <option value="auto">{e.ahAuto}</option>
            {data.ah_variants.map((v) => (
              <option key={v} value={v}>
                {methodLabel(t, `ah:${v}`)}
              </option>
            ))}
          </select>
        </Field>
        {numberField("hdbscan_min_cluster_size", e.hdbscan, "hdbscanMin")}
      </div>
      <fieldset>
        <legend>
          <Term k="inferential">{e.analysis}</Term>
        </legend>
        <label className="check">
          <input type="checkbox" checked={data.inferential} onChange={() => set({ inferential: !data.inferential })} />
          {e.inferential}
        </label>
        <span className="hint">{e.inferentialHint}</span>
        {error?.field === "inferential" ? <span className="field-error">{error.message}</span> : null}
      </fieldset>
      <Field label={c.note} help="configNote" name="note" error={error} hint={c.noteHint}>
        <textarea className="input" rows={4} value={data.note ?? ""} onChange={(event) => set({ note: event.target.value })} />
      </Field>
      <div className="actions">
        <button type="button" className="button primary" onClick={save} disabled={busy}>
          {c.save}
        </button>
        <button type="button" className="button" onClick={props.onCancel}>
          {c.cancel}
        </button>
      </div>
    </div>
  );
}
