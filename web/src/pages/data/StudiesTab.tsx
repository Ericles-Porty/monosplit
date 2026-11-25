import { useState } from "react";

import { invalidate, send, useResource } from "../../api/client";
import type { DataStudy } from "../../api/types";
import { Field, Notice, toFormError } from "../../components/forms";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";
import { useDataRoute, utcText } from "./DataPage";

type Message = { kind: "ok" | "error"; text: string } | null;

export function StudiesTab({ database, params }: { database: string; params: Record<string, string> }) {
  const { t, fmt } = useI18n();
  const d = t.data;
  const s = d.studies;
  const go = useDataRoute(params);
  const studies = useResource<{ database: string; studies: DataStudy[] }>(`data/${database}/studies`);
  const rows = studies.data?.studies ?? [];
  const selected = rows.find((study) => study.id === params.study) ?? null;
  // Kept here: a deletion closes the panel that started it.
  const [message, setMessage] = useState<Message>(null);

  if (studies.error) return <p className="error">{studies.error.message}</p>;
  if (!studies.data) return <p className="note">{t.common.loading}</p>;
  const notice = message ? <Notice kind={message.kind}>{message.text}</Notice> : null;
  if (!rows.length)
    return (
      <>
        {notice}
        <p className="note">{d.noStudies}</p>
      </>
    );

  return (
    <>
    {notice}
    <div className="split">
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>
                <Term k="study">{s.study}</Term>
              </th>
              <th>
                <Term k="variant">{s.variant}</Term>
              </th>
              <th className="num">
                <Term k="accepted">{s.accepted}</Term>
              </th>
              <th className="num">
                <Term k="attempt">{s.attempts}</Term>
              </th>
              <th className="num">
                <Term k="invalid">{s.invalid}</Term>
              </th>
              <th className="num">
                <Term k="apiErrors">{s.apiErrors}</Term>
              </th>
              <th>
                <Term k="evaluated">{s.evaluated}</Term>
              </th>
              <th>
                <Term k="experimentConfig">{s.configs}</Term>
              </th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.flatMap((study) =>
              study.variants.map((v, i) => (
                <tr key={`${study.id}/${v.variant}`} className={selected?.id === study.id ? "selected" : undefined}>
                  {i === 0 ? (
                    <td rowSpan={study.variants.length}>
                      <strong>{study.experiment}</strong>
                      <div className="pkg mono nowrap">
                        {study.app} · {study.profile}
                      </div>
                      {study.note ? <div className="pkg">{study.note.length > 80 ? `${study.note.slice(0, 80)}…` : study.note}</div> : null}
                    </td>
                  ) : null}
                  <td>{t.variantsShort[v.variant] ?? v.variant}</td>
                  <td className="num">{fmt.integer(v.accepted)}</td>
                  <td className="num">{fmt.integer(v.attempts)}</td>
                  <td className="num">{fmt.integer(v.invalid)}</td>
                  <td className="num">{fmt.integer(v.api_errors)}</td>
                  {i === 0 ? (
                    <>
                      <td rowSpan={study.variants.length}>{study.evaluated_utc ? utcText(study.evaluated_utc) : s.notEvaluated}</td>
                      <td rowSpan={study.variants.length} className="mono pkg">
                        {study.configs.length ? study.configs.join(", ") : s.noConfig}
                      </td>
                      <td rowSpan={study.variants.length} className="actions-cell">
                        <button type="button" className="button" onClick={() => go({ study: study.id })}>
                          {s.select}
                        </button>{" "}
                        <button
                          type="button"
                          className="button"
                          onClick={() =>
                            go({ tab: "attempts", experiment: study.experiment, app: study.app, profile: study.profile, variant: null, status: null, skip: null }, false)
                          }
                        >
                          {s.showAttempts}
                        </button>
                      </td>
                    </>
                  ) : null}
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
      <div className="panel">
        {selected ? (
          <StudyPanel
            key={`${database}:${selected.id}`}
            database={database}
            study={selected}
            onDeleted={(text) => {
              setMessage({ kind: "ok", text });
              go({ study: null });
            }}
          />
        ) : (
          <p className="note">{d.study.pick}</p>
        )}
      </div>
    </div>
    </>
  );
}

function StudyPanel(props: { database: string; study: DataStudy; onDeleted: (text: string) => void }) {
  const { t } = useI18n();
  const d = t.data.study;
  const { database, study } = props;
  const [note, setNote] = useState(study.note);
  const [config, setConfig] = useState(study.configs[0] ?? "");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState<Message>(null);
  const [busy, setBusy] = useState(false);

  const run = async (action: () => Promise<string>) => {
    setMessage(null);
    setBusy(true);
    try {
      setMessage({ kind: "ok", text: await action() });
    } catch (failure) {
      setMessage({ kind: "error", text: toFormError(failure).message });
    } finally {
      setBusy(false);
    }
  };

  const saveNote = () =>
    run(async () => {
      await send("PUT", `data/${database}/notes/${study.experiment}/${study.app}/${study.profile}`, { text: note });
      invalidate();
      return d.noteSaved;
    });

  const recompute = () =>
    run(async () => {
      await send("POST", "jobs", { kind: "evaluate", config, profile: study.profile });
      return d.submitted;
    });

  const remove = async () => {
    setMessage(null);
    setBusy(true);
    try {
      const answer = await send<{ backup: string }>("POST", `data/${database}/studies/delete`, {
        experiment: study.experiment,
        app: study.app,
        profile: study.profile,
        confirm,
      });
      invalidate();
      props.onDeleted(d.deleted(study.id, answer.backup));
    } catch (failure) {
      setMessage({ kind: "error", text: toFormError(failure).message });
      setBusy(false);
    }
  };

  return (
    <div className="form">
      <h3>{study.id}</h3>
      {message ? <Notice kind={message.kind}>{message.text}</Notice> : null}

      <Field label={d.noteTitle} help="studyNote" hint={d.noteHint}>
        <textarea className="input" rows={4} value={note} onChange={(event) => setNote(event.target.value)} />
      </Field>
      <div className="actions">
        <button type="button" className="button" onClick={saveNote} disabled={busy || note === study.note}>
          {d.saveNote}
        </button>
      </div>

      <fieldset>
        <legend>
          <Term k="recompute">{d.recomputeTitle}</Term>
        </legend>
        <p className="note">{d.recomputeText}</p>
        {study.configs.length ? (
          <div className="inline">
            <Field label={d.recomputeConfig} help="experimentConfig">
              <select value={config} onChange={(event) => setConfig(event.target.value)}>
                {study.configs.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </Field>
            <button type="button" className="button" onClick={recompute} disabled={busy}>
              {d.recompute}
            </button>
          </div>
        ) : (
          <p className="note">{d.noConfig}</p>
        )}
      </fieldset>

      <fieldset>
        <legend>
          <Term k="deleteStudy">{d.deleteTitle}</Term>
        </legend>
        <p className="note">{d.deleteText(database)}</p>
        <Field label={d.confirmLabel(study.id)}>
          <input className="input mono" value={confirm} onChange={(event) => setConfirm(event.target.value)} autoComplete="off" />
        </Field>
        <div className="actions">
          <button type="button" className="button danger" onClick={remove} disabled={busy || confirm !== study.id}>
            {d.delete}
          </button>
        </div>
      </fieldset>
    </div>
  );
}
