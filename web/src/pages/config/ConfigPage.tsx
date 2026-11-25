import { useResource } from "../../api/client";
import type { ConfigSummary } from "../../api/types";
import { navigate } from "../../app/router";
import { useI18n } from "../../i18n/I18n";
import { AppsTab } from "./AppsTab";
import { ExperimentsTab } from "./ExperimentsTab";
import { ProfilesTab } from "./ProfilesTab";
import { PromptsTab } from "./PromptsTab";

// Experiments last: an experiment names a profile, a prompt and an application.
const TABS = ["profiles", "prompts", "apps", "experiments"] as const;

export function ConfigPage({ params }: { params: Record<string, string> }) {
  const { t } = useI18n();
  const summary = useResource<ConfigSummary>("config");
  const tab = (TABS as readonly string[]).includes(params.tab) ? params.tab : "profiles";
  return (
    <>
      <h2>{t.config.title}</h2>
      <div className="tabs" role="tablist">
        {TABS.map((name) => (
          <button key={name} type="button" role="tab" aria-selected={tab === name} onClick={() => navigate("config", { tab: name }, true)}>
            {t.config.tabs[name]}
          </button>
        ))}
      </div>
      {summary.error ? (
        <p className="error">{summary.error.message}</p>
      ) : !summary.data ? (
        <p className="note">{t.common.loading}</p>
      ) : tab === "experiments" ? (
        <ExperimentsTab summary={summary.data} />
      ) : tab === "prompts" ? (
        <PromptsTab summary={summary.data} />
      ) : tab === "apps" ? (
        <AppsTab summary={summary.data} />
      ) : (
        <ProfilesTab summary={summary.data} />
      )}
    </>
  );
}
