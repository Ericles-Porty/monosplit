import { queryPath, useResource } from "../../api/client";
import type { AuditPage } from "../../api/types";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";
import { useDataRoute, utcText } from "./DataPage";

const LIMIT = 50;

function json(value: unknown): string {
  return value === null || value === undefined ? "—" : JSON.stringify(value, null, 2);
}

export function AuditTab({ database, params }: { database: string; params: Record<string, string> }) {
  const { t } = useI18n();
  const d = t.data;
  const a = d.audit;
  const go = useDataRoute(params);
  const skip = Math.max(0, Number(params.skip) || 0);
  const page = useResource<AuditPage>(queryPath(`data/${database}/audit`, { skip, limit: LIMIT }));

  if (page.error) return <p className="error">{page.error.message}</p>;
  if (!page.data) return <p className="note">{t.common.loading}</p>;
  const { rows, total } = page.data;
  if (!rows.length) return <p className="note empty">{a.none}</p>;
  return (
    <>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>{a.when}</th>
              <th>
                <Term k="auditAction">{a.action}</Term>
              </th>
              <th>
                <Term k="collection">{a.collection}</Term>
              </th>
              <th>{a.target}</th>
              <th>
                <Term k="auditSource">{a.source}</Term>
              </th>
              <th>{a.changes}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td className="mono pkg">{utcText(row.utc)}</td>
                <td>{a.actions[row.action] ?? row.action}</td>
                <td>{d.collections[row.collection] ?? row.collection}</td>
                <td className="mono pkg">{row.target}</td>
                <td>{a.sources[row.source] ?? row.source}</td>
                <td>
                  {row.detail ? <div className="pkg">{row.detail}</div> : null}
                  {row.before !== null || row.after !== null ? (
                    <details>
                      <summary className="pkg">{a.changes}</summary>
                      <div className="audit-values">
                        <div>
                          <strong>{a.before}</strong>
                          <pre className="output wrap">{json(row.before)}</pre>
                        </div>
                        <div>
                          <strong>{a.after}</strong>
                          <pre className="output wrap">{json(row.after)}</pre>
                        </div>
                      </div>
                    </details>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="inline" style={{ marginTop: 8 }}>
        <span className="note">{d.attempts.range(skip + 1, Math.min(skip + LIMIT, total), total)}</span>
        <button type="button" className="button" disabled={skip === 0} onClick={() => go({ skip: Math.max(0, skip - LIMIT) || null })}>
          {d.attempts.previous}
        </button>
        <button type="button" className="button" disabled={skip + LIMIT >= total} onClick={() => go({ skip: skip + LIMIT })}>
          {d.attempts.next}
        </button>
      </div>
    </>
  );
}
