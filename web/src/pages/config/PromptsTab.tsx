import { useState } from "react";

import { invalidate, send } from "../../api/client";
import type { ConfigSummary, PromptEntry } from "../../api/types";
import { Field, Notice, toFormError, type FormError } from "../../components/forms";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";

interface Preview {
  system: string;
  user: string;
  characters: number;
}

export function PromptsTab({ summary }: { summary: ConfigSummary }) {
  const { t, fmt } = useI18n();
  const c = t.config;
  const [selected, setSelected] = useState<string>(summary.prompts[0]?.name ?? "");
  const [draft, setDraft] = useState<{ name: string; text: string } | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const current = summary.prompts.find((p) => p.name === selected);

  const startVersion = async (prompt: PromptEntry) => {
    setMessage(null);
    try {
      const answer = await send<{ name: string }>("POST", "config/prompts/next-name", { base: prompt.name });
      setDraft({ name: answer.name, text: prompt.text });
    } catch (error) {
      setMessage({ kind: "error", text: toFormError(error).message });
    }
  };

  const remove = async (prompt: PromptEntry) => {
    if (!window.confirm(c.confirmRemove(prompt.name))) return;
    try {
      await send("DELETE", `config/prompts/${prompt.name}`);
      invalidate();
      setMessage({ kind: "ok", text: c.removed(prompt.name) });
      setSelected(summary.prompts.find((p) => p.name !== prompt.name)?.name ?? "");
    } catch (error) {
      setMessage({ kind: "error", text: toFormError(error).message });
    }
  };

  return (
    <div className="split">
      <div>
        <p className="note">{c.prompts.intro}</p>
        {message ? <Notice kind={message.kind}>{message.text}</Notice> : null}
        <h3 style={{ margin: "10px 0 6px" }}>{c.prompts.versions}</h3>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>
                  <Term k="promptVersion">{c.prompts.version}</Term>
                </th>
                <th>
                  <Term k="sha">{c.prompts.sha}</Term>
                </th>
                <th>
                  <Term k="usage">{c.usage}</Term>
                </th>
                <th />
              </tr>
            </thead>
            <tbody>
              {summary.prompts.map((p) => (
                <tr key={p.name} className={p.name === selected ? "selected" : undefined} onClick={() => setSelected(p.name)} style={{ cursor: "pointer" }}>
                  <td>
                    {p.name}
                    {p.protected ? <span className="chip"> <Term k="protectedDefault">{c.protectedChip}</Term></span> : null}
                    {!p.valid ? <span className="chip failed"> {c.invalid}</span> : null}
                  </td>
                  <td className="mono">{p.sha256.slice(0, 12)}</td>
                  <td>{p.used_by.length ? p.used_by.join(", ") : c.none}</td>
                  <td className="actions-cell">
                    <button type="button" className="button" onClick={(event) => { event.stopPropagation(); startVersion(p); }}>
                      {c.prompts.newVersion}
                    </button>{" "}
                    <button type="button" className="button danger" disabled={p.used_by.length > 0 || p.protected}
                      onClick={(event) => { event.stopPropagation(); remove(p); }}>
                      {c.remove}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note" style={{ marginTop: 10 }}>
          {c.prompts.structure}
        </p>
        <p className="note">
          <Term k="placeholders">{c.prompts.placeholders}</Term>: {summary.placeholders.map((p) => `$${p}`).join(", ")}
        </p>
      </div>
      <div className="panel">
        {draft ? (
          <PromptEditor
            key={draft.name}
            summary={summary}
            draft={draft}
            onCancel={() => setDraft(null)}
            onSaved={(name) => {
              setDraft(null);
              setSelected(name);
              setMessage({ kind: "ok", text: c.saved(name) });
            }}
          />
        ) : current ? (
          <>
            <h3>{current.name}</h3>
            {current.error ? <Notice kind="error">{current.error}</Notice> : null}
            <pre className="output wrap">{current.text}</pre>
            <p className="note">{c.prompts.characters(current.text.length, Math.ceil(current.text.length / 4))}</p>
            <span className="note">{fmt.integer(current.used_by.length)} · {c.usage}</span>
          </>
        ) : null}
      </div>
    </div>
  );
}

function PromptEditor(props: { summary: ConfigSummary; draft: { name: string; text: string }; onCancel: () => void; onSaved: (name: string) => void }) {
  const { t } = useI18n();
  const c = t.config;
  const appsWithGraph = props.summary.apps.filter((a) => a.status.graph);
  const [name, setName] = useState(props.draft.name);
  const [text, setText] = useState(props.draft.text);
  const [app, setApp] = useState(appsWithGraph[0]?.id ?? "");
  const [variant, setVariant] = useState("original");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<FormError | null>(null);
  const [busy, setBusy] = useState(false);

  const showPreview = async () => {
    setError(null);
    try {
      setPreview(await send<Preview>("POST", "config/prompts/preview", { text, app, variant, seed: 20261104 }));
    } catch (failure) {
      setError(toFormError(failure));
      setPreview(null);
    }
  };

  const save = async () => {
    setError(null);
    setBusy(true);
    try {
      await send("POST", "config/prompts", { name: name.trim(), text });
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
      <h3>{c.prompts.newVersion}</h3>
      {error && error.field !== "name" ? <Notice kind="error">{error.message}</Notice> : null}
      <Field label={c.prompts.name} help="promptVersion" name="name" error={error}>
        <input className="input" value={name} onChange={(event) => setName(event.target.value)} />
      </Field>
      <Field label={c.prompts.text} help="placeholders" name="text" error={null}>
        <textarea className="input" rows={18} value={text} onChange={(event) => setText(event.target.value)} />
      </Field>
      <div className="inline">
        <label className="field">
          <span className="label">
            <Term k="app">{c.prompts.previewApp}</Term>
          </span>
          <select value={app} onChange={(event) => setApp(event.target.value)}>
            {appsWithGraph.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="label">
            <Term k="variant">{c.prompts.previewVariant}</Term>
          </span>
          <select value={variant} onChange={(event) => setVariant(event.target.value)}>
            {props.summary.variants.map((v) => (
              <option key={v} value={v}>
                {t.variants[v] ?? v}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="button" onClick={showPreview} disabled={!app} style={{ alignSelf: "flex-end" }}>
          {c.prompts.preview}
        </button>
      </div>
      {preview ? (
        <>
          <p className="note">{c.prompts.characters(preview.characters, Math.ceil(preview.characters / 4))}</p>
          <pre className="output wrap">{`### system\n${preview.system}\n\n### user\n${preview.user}`}</pre>
        </>
      ) : null}
      <div className="actions">
        <button type="button" className="button primary" onClick={save} disabled={busy}>
          {c.prompts.saveVersion}
        </button>
        <button type="button" className="button" onClick={props.onCancel}>
          {c.cancel}
        </button>
      </div>
    </div>
  );
}
