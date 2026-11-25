import type { GraphPayload } from "../../api/types";
import { Swatch } from "../../components/Swatch";
import { useI18n } from "../../i18n/I18n";
import { methodLabel } from "../../lib/methods";
import type { Palette } from "../../theme/Theme";
import type { PaneView } from "./ClassDetails";

/** Table twin of the graphs: every class and its service in each panel. */
export function ClassTable(props: {
  graph: GraphPayload;
  panes: PaneView[];
  ahSelected: string | null;
  palette: Palette;
  selected: string | null;
  onSelect: (classId: string) => void;
}) {
  const { t } = useI18n();
  const classes = [...props.graph.classes].sort((a, b) => a.package.localeCompare(b.package) || a.simple.localeCompare(b.simple));
  return (
    <details className="block">
      <summary>{t.decompositions.classTable}</summary>
      <div className="block-body">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t.decompositions.classColumn}</th>
                {props.panes.map((pane, index) => (
                  <th key={index}>
                    {index + 1}. {methodLabel(t, pane.method, props.ahSelected)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {classes.map((info) => (
                <tr key={info.id} className={props.selected === info.id ? "hl" : undefined} onClick={() => props.onSelect(info.id)}>
                  <td>
                    {info.simple} <span className="pkg">{info.package}</span>
                  </td>
                  {props.panes.map((pane, index) => {
                    const d = pane.decomposition;
                    const service = d?.assignment[info.id];
                    return (
                      <td key={index}>
                        {d && service !== undefined ? (
                          <span className="cell-service">
                            <Swatch palette={props.palette} slot={pane.slots[service]} />
                            {pane.serviceLabel(service)}
                            {d.interfaces.includes(info.id) ? <span className="tag-iface">{t.decompositions.interfaceTag}</span> : null}
                          </span>
                        ) : (
                          t.common.dash
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </details>
  );
}
