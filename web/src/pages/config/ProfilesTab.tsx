import { useState } from "react";

import { invalidate, send } from "../../api/client";
import type { ConfigSummary, ProfileData, ProfileEntry } from "../../api/types";
import { Field, Notice, integerOrNull, numberOrNull, today, toFormError, type FormError } from "../../components/forms";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";

type Editing = { mode: "create" | "edit"; name: string; data: ProfileData; locked: string[] };

const EMPTY: ProfileData = {
  provider: "openai",
  model: "",
  temperature: null,
  max_output_tokens: 32000,
  seed: null,
  client: {},
  request: {},
  pricing: {},
  note: "",
};

function defaultsFor(summary: ConfigSummary, provider: string): Partial<ProfileData> {
  const info = summary.providers.find((p) => p.provider === provider);
  const client: Record<string, string | number> = {};
  for (const field of info?.client_fields ?? []) if (field.default !== null) client[field.key] = field.default;
  return { client, request: info?.request_example ?? {}, pricing: { source: info?.pricing_url ?? "", accessed: today() } };
}

export function ProfilesTab({ summary }: { summary: ConfigSummary }) {
  const { t, fmt } = useI18n();
  const c = t.config;
  const [editing, setEditing] = useState<Editing | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const profiles = summary.profiles.filter((p) => !p.template);
  const templates = summary.profiles.filter((p) => p.template);

  const startCreate = (data: ProfileData | null, name = "") =>
    setEditing({ mode: "create", name, data: data ? { ...data, model: data.model === "CHANGE-ME" ? "" : data.model } : { ...EMPTY, ...defaultsFor(summary, EMPTY.provider) }, locked: [] });

  const remove = async (profile: ProfileEntry) => {
    if (!window.confirm(c.confirmRemove(profile.name))) return;
    try {
      await send("DELETE", `config/profiles/${profile.name}`);
      invalidate();
      setMessage({ kind: "ok", text: c.removed(profile.name) });
      if (editing?.name === profile.name) setEditing(null);
    } catch (error) {
      setMessage({ kind: "error", text: toFormError(error).message });
    }
  };

  const keyLabel = (p: ProfileEntry) =>
    p.key_present === true ? c.profiles.keyFound : p.key_present === false ? c.profiles.keyMissing : c.profiles.keyNone;

  return (
    <div className="split">
      <div>
        <p className="note">{c.profiles.intro}</p>
        {message ? <Notice kind={message.kind}>{message.text}</Notice> : null}
        <div className="inline" style={{ margin: "10px 0" }}>
          <h3>{c.profiles.list}</h3>
          <button type="button" className="button" onClick={() => startCreate(null)}>
            {c.new}
          </button>
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>
                  <Term k="profileName">{c.profiles.name}</Term>
                </th>
                <th>
                  <Term k="requestOptions">{c.profiles.request}</Term>
                </th>
                <th className="num">
                  <Term k="price">{c.profiles.pricing}</Term>
                </th>
                <th>
                  <Term k="apiKey">{c.profiles.key}</Term>
                </th>
                <th>
                  <Term k="usage">{c.usage}</Term>
                </th>
                <th />
              </tr>
            </thead>
            <tbody>
              {profiles.map((p) => (
                <tr key={p.name} className={editing?.name === p.name ? "selected" : undefined}>
                  <td>
                    <strong>{p.name}</strong>
                    {p.protected ? <span className="chip"> <Term k="protectedDefault">{c.protectedChip}</Term></span> : null}
                    {!p.valid ? <span className="chip failed"> {c.invalid}</span> : null}
                    <div className="pkg mono">
                      {p.data?.provider} · {p.data?.model}
                    </div>
                  </td>
                  <td className="mono pkg">{p.data && Object.keys(p.data.request).length ? JSON.stringify(p.data.request) : t.common.dash}</td>
                  <td className="num">
                    {fmt.number(p.data?.pricing.input_per_mtok ?? null, 2)} / {fmt.number(p.data?.pricing.output_per_mtok ?? null, 2)}
                  </td>
                  <td>{keyLabel(p)}</td>
                  <td className="pkg">{p.used_by?.length ? p.used_by.join(", ") : c.none}</td>
                  <td className="actions-cell">
                    <button
                      type="button"
                      className="button"
                      onClick={() => p.data && setEditing({ mode: "edit", name: p.name, data: p.data, locked: p.used_by ?? [] })}
                      disabled={!p.data}
                    >
                      {c.edit}
                    </button>{" "}
                    <button type="button" className="button" onClick={() => startCreate(p.data, `${p.name}-2`)} disabled={!p.data}>
                      {c.duplicate}
                    </button>{" "}
                    <button type="button" className="button danger" onClick={() => remove(p)} disabled={Boolean(p.used_by?.length) || p.protected}>
                      {c.remove}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h3 style={{ margin: "18px 0 6px" }}>{c.profiles.templates}</h3>
        <p className="note">{c.profiles.templatesNote}</p>
        <div className="table-wrap">
          <table className="data">
            <tbody>
              {templates.map((p) => (
                <tr key={p.name}>
                  <td className="mono">{p.name}</td>
                  <td>{p.data?.provider}</td>
                  <td className="actions-cell">
                    <button type="button" className="button" onClick={() => p.data && startCreate({ ...p.data, note: "" })} disabled={!p.data}>
                      {c.profiles.useTemplate}
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
          <ProfileForm
            key={`${editing.mode}:${editing.name}:${editing.data.provider}`}
            summary={summary}
            editing={editing}
            onCancel={() => setEditing(null)}
            onSaved={(name) => {
              setMessage({ kind: "ok", text: c.saved(name) });
              setEditing(null);
            }}
          />
        ) : (
          <p className="note">{c.profiles.intro}</p>
        )}
      </div>
    </div>
  );
}

function ProfileForm(props: { summary: ConfigSummary; editing: Editing; onCancel: () => void; onSaved: (name: string) => void }) {
  const { t } = useI18n();
  const c = t.config;
  const { summary, editing } = props;
  const initial = editing.data;
  const locked = editing.locked.length > 0;
  const [name, setName] = useState(editing.name);
  const [provider, setProvider] = useState(initial.provider || "openai");
  const [model, setModel] = useState(initial.model);
  const [temperature, setTemperature] = useState(initial.temperature === null ? "" : String(initial.temperature));
  const [maxTokens, setMaxTokens] = useState(initial.max_output_tokens === null ? "" : String(initial.max_output_tokens));
  const [seed, setSeed] = useState(initial.seed === null ? "" : String(initial.seed));
  const [client, setClient] = useState<Record<string, string>>(
    Object.fromEntries(Object.entries(initial.client).map(([k, v]) => [k, String(v)])),
  );
  const [request, setRequest] = useState(JSON.stringify(initial.request ?? {}, null, 2));
  const [priceIn, setPriceIn] = useState(initial.pricing.input_per_mtok == null ? "" : String(initial.pricing.input_per_mtok));
  const [priceOut, setPriceOut] = useState(initial.pricing.output_per_mtok == null ? "" : String(initial.pricing.output_per_mtok));
  const [source, setSource] = useState(initial.pricing.source ?? "");
  const [accessed, setAccessed] = useState(initial.pricing.accessed ?? "");
  const [note, setNote] = useState(initial.note ?? "");
  const [models, setModels] = useState<string[] | null>(null);
  const [error, setError] = useState<FormError | null>(null);
  const [busy, setBusy] = useState(false);
  const info = summary.providers.find((p) => p.provider === provider);
  const lockNote = locked ? c.lockedField : null;

  const changeProvider = (next: string) => {
    setProvider(next);
    if (summary.providers.find((p) => p.provider === next)?.per_attempt_seed) setSeed("");
    if (editing.mode === "create") {
      const defaults = defaultsFor(summary, next);
      setClient(Object.fromEntries(Object.entries(defaults.client ?? {}).map(([k, v]) => [k, String(v)])));
      setRequest(JSON.stringify(defaults.request ?? {}, null, 2));
      setSource(defaults.pricing?.source ?? "");
      setModels(null);
    }
  };

  const clientValues = () => {
    const values: Record<string, string | number> = {};
    for (const field of info?.client_fields ?? []) {
      const raw = (client[field.key] ?? "").trim();
      if (raw === "") continue;
      values[field.key] = field.kind === "number" ? Number(raw.replace(",", ".")) : raw;
    }
    return values;
  };

  const listModels = async () => {
    setError(null);
    setBusy(true);
    try {
      const answer = await send<{ models: string[] }>("POST", "config/models", { provider, client: clientValues() });
      setModels(answer.models);
    } catch (failure) {
      setError(toFormError(failure));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setError(null);
    let requestOptions: Record<string, unknown>;
    try {
      requestOptions = request.trim() ? JSON.parse(request) : {};
    } catch {
      setError({ message: c.profiles.jsonError, field: "request" });
      return;
    }
    const data: ProfileData = {
      provider,
      model: model.trim(),
      temperature: numberOrNull(temperature),
      max_output_tokens: integerOrNull(maxTokens),
      seed: integerOrNull(seed),
      client: clientValues(),
      request: requestOptions,
      pricing: { input_per_mtok: numberOrNull(priceIn), output_per_mtok: numberOrNull(priceOut), source: source.trim(), accessed: accessed.trim() },
      note,
    };
    setBusy(true);
    try {
      await send("PUT", `config/profiles/${encodeURIComponent(name.trim())}`, { data, create: editing.mode === "create" });
      invalidate();
      props.onSaved(name.trim());
    } catch (failure) {
      setError(toFormError(failure));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="form">
      <h3>{editing.mode === "create" ? c.newTitle : c.editTitle(editing.name)}</h3>
      {locked ? <Notice kind="warn">{c.locked(editing.locked.join(", "))}</Notice> : null}
      {error && !error.field ? <Notice kind="error">{error.message}</Notice> : null}
      <div className="form-grid">
        <Field label={c.profiles.name} help="profileName" name="name" error={error} hint={c.profiles.nameHint}>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} disabled={editing.mode === "edit"} />
        </Field>
        <Field label={c.profiles.provider} help="provider" name="provider" error={error} lockNote={lockNote}>
          <select value={provider} onChange={(e) => changeProvider(e.target.value)} disabled={locked}>
            {summary.providers.map((p) => (
              <option key={p.provider} value={p.provider}>
                {p.provider}
              </option>
            ))}
          </select>
        </Field>
        <Field label={c.profiles.model} help="modelId" name="model" error={error} lockNote={lockNote} wide
          hint={models ? c.profiles.modelsFound(models.length) : undefined}>
          <div className="inline">
            <input className="input" style={{ flex: 1 }} list="model-options" value={model} onChange={(e) => setModel(e.target.value)} disabled={locked} />
            <button type="button" className="button" onClick={listModels} disabled={busy || locked}>
              {c.profiles.listModels}
            </button>
          </div>
          <datalist id="model-options">
            {(models ?? []).map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </Field>
        <Field
          label={c.profiles.temperature}
          help="temperature"
          name="temperature"
          error={error}
          lockNote={lockNote}
          hint={info?.accepts_temperature === false ? c.profiles.temperatureRejected : info?.accepts_temperature === null ? c.profiles.temperatureDepends : c.profiles.temperatureHint}
        >
          <input className="input" inputMode="decimal" value={temperature} onChange={(e) => setTemperature(e.target.value)} disabled={locked || info?.accepts_temperature === false} />
        </Field>
        <Field label={c.profiles.maxTokens} help="maxTokens" name="max_output_tokens" error={error} lockNote={lockNote}>
          <input className="input" inputMode="numeric" value={maxTokens} onChange={(e) => setMaxTokens(e.target.value)} disabled={locked} />
        </Field>
        <Field label={c.profiles.seed} help="apiSeed" name="seed" error={error} lockNote={lockNote}
          hint={info?.per_attempt_seed ? c.profiles.seedPerAttempt : undefined}>
          <input className="input" inputMode="numeric" value={seed} onChange={(e) => setSeed(e.target.value)}
            disabled={locked || provider === "anthropic" || Boolean(info?.per_attempt_seed)} />
        </Field>
      </div>

      <fieldset>
        <legend>
          <Term k="clientOptions">{c.profiles.client}</Term>
        </legend>
        <div className="form-grid">
          {(info?.client_fields ?? []).map((field) => (
            <Field key={field.key} label={field.key === "api_key_env" ? c.profiles.keyVariable : field.key} name="client" error={error}
              help={field.key === "api_key_env" ? "keyVariable" : field.key === "timeout_s" ? "timeout" : field.key === "base_url" ? "baseUrl" : undefined}
              hint={field.key === "api_key_env" && info?.default_key_env ? `${info.default_key_env}` : undefined}>
              <input
                className="input"
                inputMode={field.kind === "number" ? "decimal" : undefined}
                value={client[field.key] ?? ""}
                placeholder={field.default === null ? "" : String(field.default)}
                onChange={(e) => setClient({ ...client, [field.key]: e.target.value })}
              />
            </Field>
          ))}
        </div>
      </fieldset>

      <Field label={c.profiles.requestJson} help="requestOptions" name="request" error={error} lockNote={lockNote}
        hint={info && Object.keys(info.request_example).length ? c.profiles.requestExample(JSON.stringify(info.request_example)) : undefined}>
        <textarea className="input" rows={4} value={request} onChange={(e) => setRequest(e.target.value)} disabled={locked} />
      </Field>

      <fieldset>
        <legend>
          <Term k="price">{c.profiles.pricing}</Term>
        </legend>
        <div className="form-grid">
          <Field label={c.profiles.priceIn} help="price" name="pricing" error={error}>
            <input className="input" inputMode="decimal" value={priceIn} onChange={(e) => setPriceIn(e.target.value)} />
          </Field>
          <Field label={c.profiles.priceOut} help="price" name="pricing" error={null}>
            <input className="input" inputMode="decimal" value={priceOut} onChange={(e) => setPriceOut(e.target.value)} />
          </Field>
          <Field label={c.profiles.priceSource} help="priceSource" wide
            hint={info?.pricing_url ? <a href={info.pricing_url} target="_blank" rel="noreferrer">{c.profiles.pricingPage}</a> : undefined}>
            <input className="input" value={source} onChange={(e) => setSource(e.target.value)} />
          </Field>
          <Field label={c.profiles.priceDate} help="priceSource">
            <input className="input" type="date" value={accessed} onChange={(e) => setAccessed(e.target.value)} />
          </Field>
        </div>
      </fieldset>

      <Field label={c.note} help="configNote" name="note" error={error} hint={c.noteHint}>
        <textarea className="input" rows={4} value={note} onChange={(e) => setNote(e.target.value)} />
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
