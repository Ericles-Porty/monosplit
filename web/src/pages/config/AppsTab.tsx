import { useState } from "react";

import { invalidate, send } from "../../api/client";
import type { AppConfigEntry, ConfigSummary } from "../../api/types";
import { hrefFor } from "../../app/router";
import { Field, Notice, linesOf, toFormError, type FormError } from "../../components/forms";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";

type Editing = { mode: "create" | "edit"; entry: AppConfigEntry };

const LOCKED = ["repository", "commit", "source_roots", "class_dirs"];

function emptyApp(): AppConfigEntry {
  return {
    id: "",
    name: "",
    note: "",
    repository: "",
    tag: "",
    commit: "",
    build: "maven",
    build_args: ["-B", "-DskipTests", "clean", "compile"],
    source_roots: ["src/main/java"],
    class_dirs: ["target/classes"],
    status: { fetched: false, build_log: false, graph: null, edge_check: false },
    studies: [],
  };
}

export function AppsTab({ summary }: { summary: ConfigSummary }) {
  const { t } = useI18n();
  const c = t.config;
  const a = c.apps;
  const [editing, setEditing] = useState<Editing | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const remove = async (entry: AppConfigEntry) => {
    if (!window.confirm(c.confirmRemove(entry.id))) return;
    try {
      await send("DELETE", `config/apps/${entry.id}`);
      invalidate();
      setMessage({ kind: "ok", text: c.removed(entry.id) });
    } catch (error) {
      setMessage({ kind: "error", text: toFormError(error).message });
    }
  };

  const status = (entry: AppConfigEntry) => {
    const graph = entry.status.graph;
    return [
      entry.status.fetched ? a.fetched : a.notFetched,
      graph ? a.graph(graph.classes, graph.edges ?? 0) : a.noGraph,
    ].join(" · ");
  };

  return (
    <div className="split">
      <div>
        <p className="note">{a.intro}</p>
        {message ? <Notice kind={message.kind}>{message.text}</Notice> : null}
        <div className="inline" style={{ margin: "10px 0" }}>
          <button type="button" className="button" onClick={() => setEditing({ mode: "create", entry: emptyApp() })}>
            {c.new}
          </button>
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>
                  <Term k="appId">{a.id}</Term>
                </th>
                <th>{a.name}</th>
                <th>
                  <Term k="tag">{a.tag}</Term>
                </th>
                <th>
                  <Term k="commit">{a.commit}</Term>
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
              {summary.apps.map((entry) => (
                <tr key={entry.id} className={editing?.entry.id === entry.id ? "selected" : undefined}>
                  <td className="mono">
                    {entry.id}
                    {entry.protected ? <span className="chip"> <Term k="protectedDefault">{c.protectedChip}</Term></span> : null}
                  </td>
                  <td>{entry.name}</td>
                  <td className="mono">{entry.tag ?? t.common.dash}</td>
                  <td className="mono">{entry.commit.slice(0, 7)}</td>
                  <td>{entry.build}</td>
                  <td>
                    {status(entry)}
                    {!entry.status.graph ? (
                      <>
                        {" · "}
                        <a href={hrefFor("execution", { app: entry.id })}>{t.execution.extract}</a>
                      </>
                    ) : null}
                  </td>
                  <td className="actions-cell">
                    <button type="button" className="button" onClick={() => setEditing({ mode: "edit", entry })}>
                      {c.edit}
                    </button>{" "}
                    <button type="button" className="button danger" onClick={() => remove(entry)}
                      disabled={Boolean(entry.status.graph) || entry.studies.length > 0 || entry.protected}>
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
          <AppForm
            key={`${editing.mode}:${editing.entry.id}`}
            summary={summary}
            editing={editing}
            onCancel={() => setEditing(null)}
            onSaved={(id) => {
              setEditing(null);
              setMessage({ kind: "ok", text: c.saved(id) });
            }}
          />
        ) : (
          <p className="note">{a.intro}</p>
        )}
      </div>
    </div>
  );
}

function AppForm(props: { summary: ConfigSummary; editing: Editing; onCancel: () => void; onSaved: (id: string) => void }) {
  const { t } = useI18n();
  const c = t.config;
  const a = c.apps;
  const entry = props.editing.entry;
  const lockedBy = entry.status.graph || entry.studies.length ? (entry.studies.length ? entry.studies : ["graph"]) : [];
  const lock = (field: string) => (lockedBy.length && LOCKED.includes(field) ? c.lockedField : null);
  const [id, setId] = useState(entry.id);
  const [form, setForm] = useState({
    name: entry.name,
    note: entry.note,
    repository: entry.repository,
    tag: entry.tag ?? "",
    commit: entry.commit,
    build: entry.build,
    build_args: entry.build_args.join("\n"),
    source_roots: entry.source_roots.join("\n"),
    class_dirs: entry.class_dirs.join("\n"),
  });
  const [error, setError] = useState<FormError | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const resolve = async () => {
    setError(null);
    setBusy(true);
    try {
      const answer = await send<{ commit: string }>("POST", "config/apps/resolve", { repository: form.repository, tag: form.tag });
      set({ commit: answer.commit });
    } catch (failure) {
      setError(toFormError(failure));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setError(null);
    setBusy(true);
    const data = {
      ...form,
      build_args: linesOf(form.build_args),
      source_roots: linesOf(form.source_roots),
      class_dirs: linesOf(form.class_dirs),
    };
    try {
      await send("PUT", `config/apps/${encodeURIComponent(id.trim())}`, { data, create: props.editing.mode === "create" });
      invalidate();
      props.onSaved(id.trim());
    } catch (failure) {
      setError(toFormError(failure));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="form">
      <h3>{props.editing.mode === "create" ? c.newTitle : c.editTitle(entry.id)}</h3>
      {lockedBy.length ? <Notice kind="warn">{c.locked(lockedBy.join(", "))}</Notice> : null}
      {error && !error.field ? <Notice kind="error">{error.message}</Notice> : null}
      <div className="form-grid">
        <Field label={a.id} help="appId" name="id" error={error} hint={a.idHint}>
          <input className="input" value={id} onChange={(event) => setId(event.target.value)} disabled={props.editing.mode === "edit"} />
        </Field>
        <Field label={a.name} name="name" error={error}>
          <input className="input" value={form.name} onChange={(event) => set({ name: event.target.value })} />
        </Field>
        <Field label={a.repository} help="repository" name="repository" error={error} lockNote={lock("repository")} wide>
          <input className="input" value={form.repository} onChange={(event) => set({ repository: event.target.value })} disabled={Boolean(lock("repository"))} />
        </Field>
        <Field label={a.tag} help="tag" name="tag" error={error}>
          <div className="inline">
            <input className="input" style={{ flex: 1 }} value={form.tag} onChange={(event) => set({ tag: event.target.value })} disabled={Boolean(lock("commit"))} />
            <button type="button" className="button" onClick={resolve} disabled={busy || Boolean(lock("commit")) || !form.tag}>
              {a.resolve}
            </button>
          </div>
        </Field>
        <Field label={a.commit} help="commit" name="commit" error={error} lockNote={lock("commit")}>
          <input className="input mono" value={form.commit} onChange={(event) => set({ commit: event.target.value })} disabled={Boolean(lock("commit"))} />
        </Field>
        <Field label={a.build} help="build" name="build" error={error} wide>
          <select value={form.build} onChange={(event) => set({ build: event.target.value })}>
            {props.summary.build_types.map((type) => (
              <option key={type} value={type}>
                {a.buildTypes[type] ?? type}
              </option>
            ))}
          </select>
        </Field>
        <Field label={a.buildArgs} help="buildArgs" name="build_args" error={error} wide>
          <textarea className="input" rows={4} value={form.build_args} onChange={(event) => set({ build_args: event.target.value })} />
        </Field>
        <Field label={a.sourceRoots} help="sourceRoots" name="source_roots" error={error} lockNote={lock("source_roots")}>
          <textarea className="input" rows={2} value={form.source_roots} onChange={(event) => set({ source_roots: event.target.value })} disabled={Boolean(lock("source_roots"))} />
        </Field>
        <Field label={a.classDirs} help="classDirs" name="class_dirs" error={error} lockNote={lock("class_dirs")}>
          <textarea className="input" rows={2} value={form.class_dirs} onChange={(event) => set({ class_dirs: event.target.value })} disabled={Boolean(lock("class_dirs"))} />
        </Field>
        <Field label={a.note} help="note" name="note" error={error} wide>
          <textarea className="input" rows={3} value={form.note} onChange={(event) => set({ note: event.target.value })} style={{ fontFamily: "var(--font-sans)" }} />
        </Field>
      </div>
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
