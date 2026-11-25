import { invalidate, useResource } from "../../api/client";
import type { DatabaseInfo } from "../../api/types";
import { navigate } from "../../app/router";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";
import { AttemptsTab } from "./AttemptsTab";
import { AuditTab } from "./AuditTab";
import { EdgesTab } from "./EdgesTab";
import { StudiesTab } from "./StudiesTab";

const TABS = ["studies", "attempts", "edges", "audit"] as const;

/** Changes the route parameters of the Data page, keeping the ones not given. */
export function useDataRoute(params: Record<string, string>) {
  return (patch: Record<string, string | number | null>, replace = true) => {
    const next: Record<string, string | number | null> = { ...params, ...patch };
    navigate("data", next, replace);
  };
}

export function DataPage({ params }: { params: Record<string, string> }) {
  const { t, fmt } = useI18n();
  const d = t.data;
  const databases = useResource<{ databases: DatabaseInfo[]; default: string }>("data/databases");
  const tab = (TABS as readonly string[]).includes(params.tab) ? params.tab : "studies";
  const go = useDataRoute(params);
  const list = databases.data?.databases ?? [];
  const database = list.some((db) => db.name === params.db) ? params.db : (databases.data?.default ?? "");
  const info = list.find((db) => db.name === database);

  return (
    <>
      <h2>{d.title}</h2>
      <p className="note">{d.intro}</p>
      {databases.error ? <p className="error">{databases.error.message}</p> : null}
      <div className="inline" style={{ margin: "10px 0", flexWrap: "wrap" }}>
        <label className="field" style={{ minWidth: 260 }}>
          <span className="label">
            <Term k="database">{d.database}</Term>
          </span>
          <select value={database} onChange={(event) => go({ db: event.target.value, skip: null, experiment: null, app: null, profile: null, variant: null, status: null })}>
            {list.map((db) => (
              <option key={db.name} value={db.name}>
                {db.name}
                {db.main ? ` (${d.mainDatabase})` : ""}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="button" onClick={() => invalidate()}>
          {d.refresh}
        </button>
      </div>
      {info ? (
        <p className="note">
          <Term k="documents">{d.documents}</Term>:{" "}
          {Object.entries(info.counts)
            .map(([name, n]) => `${d.collections[name] ?? name} ${fmt.integer(n)}`)
            .join(" · ")}
        </p>
      ) : null}
      <div className="tabs" role="tablist">
        {TABS.map((name) => (
          <button key={name} type="button" role="tab" aria-selected={tab === name} onClick={() => go({ tab: name, skip: null })}>
            {d.tabs[name]}
          </button>
        ))}
      </div>
      {!database ? (
        <p className="note">{t.common.loading}</p>
      ) : tab === "attempts" ? (
        <AttemptsTab database={database} params={params} />
      ) : tab === "edges" ? (
        <EdgesTab params={params} />
      ) : tab === "audit" ? (
        <AuditTab database={database} params={params} />
      ) : (
        <StudiesTab database={database} params={params} />
      )}
    </>
  );
}

/** "2026-11-05T15:12:57.134512+00:00" -> "2026-11-05 15:12:57". */
export function utcText(value: string | null | undefined): string {
  if (!value) return "";
  return value.replace("T", " ").replace(/(\.\d+)?(\+00:00|Z)$/, "");
}
