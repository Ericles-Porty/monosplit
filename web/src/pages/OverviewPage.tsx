import type { IndexPayload, StudyEntry } from "../api/types";
import { hrefFor } from "../app/router";
import { Term } from "../components/Term";
import { useI18n } from "../i18n/I18n";

function configuration(study: StudyEntry, t: ReturnType<typeof useI18n>["t"]): string {
  const options = Object.entries(study.request_options).map(([key, value]) =>
    `${key} = ${typeof value === "object" ? JSON.stringify(value) : String(value)}`,
  );
  const temperature = study.temperature === null ? t.overview.apiDefault : String(study.temperature);
  return [...options, `${t.overview.temperature}: ${temperature}`, study.prompt_template ? `prompt ${study.prompt_template}` : ""]
    .filter(Boolean)
    .join(" · ");
}

export function OverviewPage({ index }: { index: IndexPayload }) {
  const { t, fmt } = useI18n();
  const appName = new Map(index.apps.map((a) => [a.id, a.name]));
  const cols = t.overview.cols;
  return (
    <>
      <section className="section">
        <h2>{t.app.title}</h2>
        <p className="lead">{t.overview.intro}</p>
        <p className="note">{t.overview.statusNote}</p>
        <p className="note">{t.overview.termsHint}</p>
      </section>

      <section className="section">
        <h2>{t.overview.studies}</h2>
        {index.studies.length === 0 ? (
          <p className="note">{t.overview.noStudies}</p>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>
                    <Term k="experiment">{cols.experiment}</Term>
                  </th>
                  <th>
                    <Term k="app">{cols.app}</Term>
                  </th>
                  <th>
                    <Term k="model">{cols.model}</Term>
                  </th>
                  <th>
                    <Term k="modelConfig">{cols.configuration}</Term>
                  </th>
                  <th>
                    <Term k="variant">{cols.variant}</Term>
                  </th>
                  <th className="num">
                    <Term k="accepted">{cols.accepted}</Term>
                  </th>
                  <th className="num">
                    <Term k="attempt">{cols.attempts}</Term>
                  </th>
                  <th>
                    <Term k="kPerRun">{cols.ks}</Term>
                  </th>
                  <th className="num">
                    <Term k="cost">{cols.cost}</Term>
                  </th>
                  <th>
                    <Term k="evaluated">{cols.evaluated}</Term>
                  </th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {index.studies.flatMap((study) =>
                  study.variants.map((variant, i) => {
                    const span = study.variants.length;
                    return (
                      <tr key={`${study.id}/${variant.variant}`}>
                        {i === 0 ? (
                          <>
                            <td rowSpan={span}>{study.experiment}</td>
                            <td rowSpan={span}>{appName.get(study.app) ?? study.app}</td>
                            <td rowSpan={span} className="mono">
                              {study.provider} · {study.model}
                            </td>
                            <td rowSpan={span}>{configuration(study, t)}</td>
                          </>
                        ) : null}
                        <td>{t.variants[variant.variant] ?? variant.variant}</td>
                        <td className="num">{fmt.integer(variant.accepted)}</td>
                        <td className="num">{fmt.integer(variant.attempts)}</td>
                        <td className="mono">{variant.runs.map((r) => r.k).join(" ")}</td>
                        <td className="num">{fmt.number(variant.cost_usd, 4)}</td>
                        {i === 0 ? (
                          <>
                            <td rowSpan={span}>{study.evaluated ? t.common.yes : t.common.no}</td>
                            <td rowSpan={span} className="links-cell">
                              {study.has_graph ? <a href={hrefFor("decompositions", { study: study.id })}>{t.overview.open}</a> : null}
                              {study.evaluated ? (
                                <a href={hrefFor("results", { set: `${study.experiment}/${study.profile}` })}>{t.overview.openResults}</a>
                              ) : null}
                            </td>
                          </>
                        ) : null}
                      </tr>
                    );
                  }),
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="section">
        <h2>{t.overview.apps}</h2>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>
                  <Term k="app">{cols.app}</Term>
                </th>
                <th>
                  <Term k="tag">{cols.version}</Term>
                </th>
                <th>
                  <Term k="commit">{cols.commit}</Term>
                </th>
                <th className="num">
                  <Term k="classes">{cols.classes}</Term>
                </th>
                <th className="num">
                  <Term k="edges">{cols.edges}</Term>
                </th>
                <th className="num">
                  <Term k="calls">{cols.calls}</Term>
                </th>
                <th className="num">
                  <Term k="isolated">{cols.isolated}</Term>
                </th>
              </tr>
            </thead>
            <tbody>
              {index.apps.map((app) => (
                <tr key={app.id}>
                  <td>{app.repository ? <a href={app.repository.replace(/\.git$/, "")}>{app.name}</a> : app.name}</td>
                  <td className="mono">{app.tag ?? t.common.dash}</td>
                  <td className="mono">{app.commit ? app.commit.slice(0, 7) : t.common.dash}</td>
                  <td className="num">{fmt.integer(app.graph?.classes)}</td>
                  <td className="num">{fmt.integer(app.graph?.edges)}</td>
                  <td className="num">{fmt.integer(app.graph?.calls_in_graph)}</td>
                  <td className="num">{fmt.integer(app.graph?.isolated_classes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
