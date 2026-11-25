import type { ClassInfo, Decomposition, GraphPayload } from "../../api/types";
import { Swatch } from "../../components/Swatch";
import { Term } from "../../components/Term";
import { useI18n } from "../../i18n/I18n";
import { methodLabel } from "../../lib/methods";
import type { Palette } from "../../theme/Theme";

export interface PaneView {
  method: string;
  decomposition: Decomposition | undefined;
  slots: number[];
  serviceLabel: (serviceIndex: number) => string;
}

interface Props {
  classId: string | null;
  graph: GraphPayload;
  panes: PaneView[];
  promptName: string | undefined;
  ahSelected: string | null;
  palette: Palette;
}

export function ClassDetails({ classId, graph, panes, promptName, ahSelected, palette }: Props) {
  const { t, fmt } = useI18n();
  const info: ClassInfo | undefined = graph.classes.find((c) => c.id === classId);
  if (!info) {
    return (
      <div className="panel">
        <h3>{t.decompositions.detailsTitle}</h3>
        <p className="note">{t.decompositions.detailsHint}</p>
      </div>
    );
  }
  const simple = new Map(graph.classes.map((c) => [c.id, c.simple]));
  const outgoing = graph.edges.filter((e) => e.source === info.id).sort((a, b) => b.calls - a.calls);
  const incoming = graph.edges.filter((e) => e.target === info.id).sort((a, b) => b.calls - a.calls);
  const reference = panes[0]?.decomposition;
  const crosses = (other: string) => reference !== undefined && reference.assignment[other] !== reference.assignment[info.id];

  return (
    <div className="panel">
      <h3>
        {t.decompositions.detailsTitle}: {info.simple}
      </h3>
      <dl className="facts">
        <dt>
          <Term k="package">{t.decompositions.package}</Term>
        </dt>
        <dd className="mono">{info.package}</dd>
        <dt>
          <Term k="kind">{t.decompositions.kind}</Term>
        </dt>
        <dd>{t.decompositions.kinds[info.kind] ?? info.kind}</dd>
        {info.source ? (
          <>
            <dt>
              <Term k="sourceFile">{t.decompositions.source}</Term>
            </dt>
            <dd className="mono">{info.source}</dd>
          </>
        ) : null}
        {promptName ? (
          <>
            <dt>
              <Term k="promptName">{t.decompositions.promptName}</Term>
            </dt>
            <dd className="mono">{promptName}</dd>
          </>
        ) : null}
      </dl>

      <h3 style={{ marginTop: 12 }}>
        <Term k="servicePerPane">{t.decompositions.servicePerPane}</Term>
      </h3>
      <table className="data" style={{ marginTop: 4 }}>
        <tbody>
          {panes.map((pane, index) => {
            const d = pane.decomposition;
            const service = d?.assignment[info.id];
            return (
              <tr key={index}>
                <td>{index + 1}</td>
                <td>{methodLabel(t, pane.method, ahSelected)}</td>
                <td>
                  {d && service !== undefined ? (
                    <span className="cell-service">
                      <Swatch palette={palette} slot={pane.slots[service]} />
                      {pane.serviceLabel(service)}
                      {d.interfaces.includes(info.id) ? <span className="tag-iface">{t.decompositions.interfaceTag}</span> : null}
                    </span>
                  ) : (
                    t.common.dash
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="call-lists">
        <div>
          <h3>
            <Term k="callsOut">{t.decompositions.calls}</Term>
          </h3>
          <ul>
            {outgoing.length ? (
              outgoing.map((e) => (
                <li key={e.target}>
                  <span>
                    {simple.get(e.target)}
                    {crosses(e.target) ? " ↔" : ""}
                  </span>
                  <span>{fmt.integer(e.calls)}</span>
                </li>
              ))
            ) : (
              <li className="note">{t.decompositions.noCalls}</li>
            )}
          </ul>
        </div>
        <div>
          <h3>
            <Term k="calledBy">{t.decompositions.calledBy}</Term>
          </h3>
          <ul>
            {incoming.length ? (
              incoming.map((e) => (
                <li key={e.source}>
                  <span>
                    {simple.get(e.source)}
                    {crosses(e.source) ? " ↔" : ""}
                  </span>
                  <span>{fmt.integer(e.calls)}</span>
                </li>
              ))
            ) : (
              <li className="note">{t.decompositions.noCalls}</li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}
