import { useEffect, useMemo, useRef, useState } from "react";

import { hrefFor } from "../../app/router";
import { useI18n } from "../../i18n/I18n";
import { WIKI_PAGES, isWikiPage, wikiSource, wikiTitle } from "../../wiki/content";
import { renderMarkdown } from "../../wiki/markdown";

interface Heading {
  id: string;
  text: string;
}

// Loaded on demand (React.lazy): Markdown and KaTeX stay out of the main bundle.
export default function WikiPage({ params }: { params: Record<string, string> }) {
  const { t, lang } = useI18n();
  const page = isWikiPage(params.page) ? params.page : "overview";
  const source = wikiSource(lang, page);
  const html = useMemo(() => renderMarkdown(source), [source]);
  const article = useRef<HTMLElement>(null);
  const [headings, setHeadings] = useState<Heading[]>([]);

  useEffect(() => {
    const element = article.current;
    if (!element) return;
    setHeadings([...element.querySelectorAll("h2")].map((h) => ({ id: h.id, text: h.textContent ?? "" })));
  }, [html]);

  // A link such as #/wiki?page=metrics&section=<heading id> opens at that section.
  const section = params.section;
  useEffect(() => {
    const target = section ? document.getElementById(section) : null;
    if (target) target.scrollIntoView({ block: "start" });
    else window.scrollTo({ top: 0 });
  }, [html, section]);

  const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div className="wiki">
      <nav className="wiki-nav" aria-label={t.wiki.pages}>
        <h2>{t.wiki.pages}</h2>
        <ol>
          {WIKI_PAGES.map((id) => (
            <li key={id}>
              <a href={hrefFor("wiki", { page: id })} aria-current={id === page ? "page" : undefined}>
                {wikiTitle(wikiSource(lang, id))}
              </a>
            </li>
          ))}
        </ol>
        {headings.length > 1 ? (
          <>
            <h2>{t.wiki.onThisPage}</h2>
            <ul>
              {headings.map((h) => (
                <li key={h.id}>
                  <button type="button" className="link-button" onClick={() => jump(h.id)}>
                    {h.text}
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </nav>
      <article ref={article} className="wiki-content" lang={t.meta.locale} dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}
