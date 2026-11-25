import { lazy, Suspense } from "react";

import { isStatic, useResource } from "../api/client";
import type { IndexPayload } from "../api/types";
import { useI18n } from "../i18n/I18n";
import type { Lang } from "../i18n/messages";
import { messages } from "../i18n/messages";
import { ConfigPage } from "../pages/config/ConfigPage";
import { DataPage } from "../pages/data/DataPage";
import { DecompositionsPage } from "../pages/decompositions/DecompositionsPage";
import { ExecutionPage } from "../pages/execution/ExecutionPage";
import { useJobWatcher } from "../pages/execution/useJobs";
import { OverviewPage } from "../pages/OverviewPage";
import { ResultsPage } from "../pages/results/ResultsPage";
import { useTheme } from "../theme/Theme";
import { hrefFor, useRoute } from "./router";

// Configuration, execution and data change the database and can call paid APIs: only in the local version.
type Page = "overview" | "decompositions" | "results" | "wiki" | "config" | "execution" | "data";
const PAGES: readonly Page[] = isStatic
  ? ["wiki", "overview", "decompositions", "results"]
  : ["wiki", "overview", "config", "execution", "decompositions", "results", "data"];

// Markdown and KaTeX load only when the wiki opens.
const WikiPage = lazy(() => import("../pages/wiki/WikiPage"));

function Header({ page }: { page: string }) {
  const { t, lang, setLang } = useI18n();
  const { theme, toggle } = useTheme();
  return (
    <header className="header">
      <div className="brand">
        <span className="brand-name">{t.app.name}</span>
        <span className="brand-title">{t.app.title}</span>
      </div>
      <nav className="nav" aria-label="Main">
        {PAGES.map((p) => (
          <a key={p} href={hrefFor(p)} aria-current={page === p ? "page" : undefined}>
            {t.app.nav[p]}
          </a>
        ))}
      </nav>
      <div className="header-tools">
        {isStatic ? <span className="badge">{t.app.staticBadge}</span> : null}
        <div className="segmented" role="group" aria-label={t.app.language}>
          {(Object.keys(messages) as Lang[]).map((code) => (
            <button key={code} type="button" aria-pressed={lang === code} title={messages[code].meta.name} onClick={() => setLang(code)}>
              {messages[code].meta.label}
            </button>
          ))}
        </div>
        <button type="button" className="icon-button" onClick={toggle} aria-label={theme === "light" ? t.app.themeToDark : t.app.themeToLight} title={theme === "light" ? t.app.themeToDark : t.app.themeToLight}>
          {theme === "light" ? "☾" : "☀"}
        </button>
      </div>
    </header>
  );
}

export function App() {
  const route = useRoute();
  const { t } = useI18n();
  const index = useResource<IndexPayload>("index");
  // Jobs run on the server while any page is open; the watcher refreshes the data when one ends.
  useJobWatcher(!isStatic);
  const page = (PAGES as readonly string[]).includes(route.page) ? route.page : "overview";
  return (
    <div className="app">
      <Header page={page} />
      <main className="main">
        {index.error ? (
          <p className="error">{t.common.loadError}</p>
        ) : !index.data ? (
          <p className="note">{t.common.loading}</p>
        ) : page === "decompositions" ? (
          <DecompositionsPage index={index.data} params={route.params} />
        ) : page === "results" ? (
          <ResultsPage index={index.data} params={route.params} />
        ) : page === "wiki" ? (
          <Suspense fallback={<p className="note">{t.common.loading}</p>}>
            <WikiPage params={route.params} />
          </Suspense>
        ) : page === "config" ? (
          <ConfigPage params={route.params} />
        ) : page === "execution" ? (
          <ExecutionPage params={route.params} />
        ) : page === "data" ? (
          <DataPage params={route.params} />
        ) : (
          <OverviewPage index={index.data} />
        )}
      </main>
      <footer className="footer">
        {t.app.footer} · MonoSplit {index.data?.version ?? ""}
      </footer>
    </div>
  );
}
