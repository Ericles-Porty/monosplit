import { useEffect, useState } from "react";

import { invalidate, send, useResource } from "../../api/client";
import type { EdgeCheck, EdgeCheckRow, IndexPayload } from "../../api/types";
import { Field, Notice, toFormError } from "../../components/forms";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";
import { useDataRoute, utcText } from "./DataPage";

type Draft = Record<number, { confirmed: EdgeCheckRow["confirmed"]; notes: string }>;

export function EdgesTab({ params }: { params: Record<string, string> }) {
  const { t } = useI18n();
  const e = t.data.edges;
  const go = useDataRoute(params);
  const index = useResource<IndexPayload>("index");
  const apps = (index.data?.apps ?? []).filter((app) => app.graph);
  const app = apps.some((item) => item.id === params.app) ? params.app : (apps[0]?.id ?? "");

  if (index.data && !apps.length) return <p className="note">{e.noGraph}</p>;
  return (
    <>
      <div className="inline" style={{ marginBottom: 10 }}>
        <Field label={e.app} help="app">
          <select value={app} onChange={(event) => go({ app: event.target.value })}>
            {apps.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} ({item.id})
              </option>
            ))}
          </select>
        </Field>
      </div>
      {app ? <EdgeCheckTable key={app} app={app} /> : null}
    </>
  );
}

function EdgeCheckTable({ app }: { app: string }) {
  const { t, fmt } = useI18n();
  const e = t.data.edges;
  const check = useResource<EdgeCheck>(`data/edge-check/${app}`);
  const [draft, setDraft] = useState<Draft>({});
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  // A saved check reloads the rows; the draft then starts again from them.
  useEffect(() => setDraft({}), [check.data]);

  if (check.error) return <p className="error">{check.error.message}</p>;
  if (!check.data) return <p className="note">{t.common.loading}</p>;
  const data = check.data;
  if (!data.sampled) return <p className="note">{e.notSampled}</p>;

  const value = (row: EdgeCheckRow) => draft[row.row] ?? { confirmed: row.confirmed, notes: row.notes };
  const changed = data.rows.filter((row) => {
    const v = value(row);
    return v.confirmed !== row.confirmed || v.notes.trim() !== row.notes;
  });
  const edit = (row: EdgeCheckRow, patch: Partial<Draft[number]>) => setDraft({ ...draft, [row.row]: { ...value(row), ...patch } });

  const save = async () => {
    setMessage(null);
    setBusy(true);
    try {
      await send("PUT", `data/edge-check/${app}`, {
        edits: changed.map((row) => ({ row: row.row, caller: row.caller, callee: row.callee, ...value(row) })),
      });
      invalidate();
      setMessage({ kind: "ok", text: changed.length ? e.saved(changed.length) : e.unchanged });
    } catch (failure) {
      setMessage({ kind: "error", text: toFormError(failure).message });
    } finally {
      setBusy(false);
    }
  };

  const summary = data.summary;
  return (
    <>
      <p className="note">{e.intro(data.commit ? data.commit.slice(0, 7) : t.common.dash)}</p>
      {data.meta ? (
        <p className="note">{e.sample(data.rows.length, data.meta.seed ?? t.common.dash, utcText(data.meta.created_utc))}</p>
      ) : null}
      <p>
        <Term k="edgeVerdict">{e.confirmed}</Term>: {e.summary(summary.yes, summary.no, summary.unchecked)}
      </p>
      {message ? <Notice kind={message.kind}>{message.text}</Notice> : null}
      <div className="table-wrap">
        <table className="data edge-check">
          <thead>
            <tr>
              <th className="num">{e.row}</th>
              <th>
                <Term k="edges">{e.edge}</Term>
              </th>
              <th className="num">
                <Term k="calls">{e.calls}</Term>
              </th>
              <th>
                <Term k="callSites">{e.sites}</Term>
              </th>
              <th>
                <Term k="edgeVerdict">{e.confirmed}</Term>
              </th>
              <th>
                <Term k="edgeNote">{e.notes}</Term>
              </th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => {
              const v = value(row);
              return (
                <tr key={row.row}>
                  <td className="num">{row.row}</td>
                  <td className="mono pkg">
                    {row.caller}
                    <br />→ {row.callee}
                  </td>
                  <td className="num">{fmt.integer(row.calls)}</td>
                  <td className="mono pkg">
                    {row.call_sites.split("; ").map((site) => (
                      <div key={site}>{site}</div>
                    ))}
                  </td>
                  <td>
                    <select value={v.confirmed} onChange={(event) => edit(row, { confirmed: event.target.value as EdgeCheckRow["confirmed"] })}
                      aria-label={`${e.confirmed} ${row.row}`}>
                      {(["", "yes", "no"] as const).map((verdict) => (
                        <option key={verdict} value={verdict}>
                          {e.verdicts[verdict]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input className="input" value={v.notes} onChange={(event) => edit(row, { notes: event.target.value })}
                      aria-label={`${e.notes} ${row.row}`} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="inline" style={{ marginTop: 10 }}>
        <button type="button" className="button primary" onClick={save} disabled={busy || !changed.length}>
          {e.save}
        </button>
        {changed.length ? <span className="note">{e.pending(changed.length)}</span> : null}
      </div>
    </>
  );
}
