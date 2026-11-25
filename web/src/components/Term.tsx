import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { hrefFor } from "../app/router";
import { useI18n } from "../i18n/I18n";
import type { HelpKey } from "../i18n/messages-help";

/** "metrics#structural-modularity-sm" -> link to that section of the wiki. */
export function wikiHref(target: string): string {
  const [page, section] = target.split("#");
  return hrefFor("wiki", { page, section });
}

/**
 * A term of the interface with its explanation. The text gets a dotted underline; the
 * explanation opens on hover and on keyboard focus, stays open while the pointer is over
 * it (so its wiki link can be clicked) and closes with Escape. It is drawn in a portal,
 * so tables with horizontal scroll do not clip it.
 */
export function Term({ k, children }: { k: HelpKey; children?: ReactNode }) {
  const { t } = useI18n();
  const entry = t.help[k];
  const id = useId();
  const anchor = useRef<HTMLSpanElement>(null);
  const tip = useRef<HTMLDivElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);

  const show = () => {
    window.clearTimeout(timer.current);
    setOpen(true);
  };
  const hide = (delay = 150) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setOpen(false), delay);
  };

  // Below the term, or above it when there is no room; inside the window horizontally.
  // On scroll (including the scroll that keyboard focus causes) the tip follows the term
  // and closes only when the term leaves the window.
  const place = useCallback(() => {
    if (!anchor.current || !tip.current) return;
    const a = anchor.current.getBoundingClientRect();
    if (a.bottom < 0 || a.top > window.innerHeight) {
      setOpen(false);
      return;
    }
    const b = tip.current.getBoundingClientRect();
    const margin = 8;
    let top = a.bottom + 6;
    if (top + b.height > window.innerHeight - margin && a.top - 6 - b.height >= margin) top = a.top - 6 - b.height;
    const left = Math.max(margin, Math.min(a.left, window.innerWidth - b.width - margin));
    setPosition({ top, left });
  }, []);

  useLayoutEffect(() => {
    if (open) place();
  }, [open, place]);

  useEffect(() => {
    if (!open) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    window.addEventListener("keydown", escape);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
      window.removeEventListener("keydown", escape);
    };
  }, [open, place]);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  return (
    <>
      <span
        ref={anchor}
        className="term"
        tabIndex={0}
        aria-describedby={open ? id : undefined}
        onMouseEnter={show}
        onMouseLeave={() => hide()}
        onFocus={show}
        onBlur={() => hide(0)}
      >
        {children ?? entry.title}
      </span>
      {open
        ? createPortal(
            <div
              ref={tip}
              id={id}
              role="tooltip"
              className="help-tip"
              style={position ? { top: position.top, left: position.left } : { top: 0, left: 0, visibility: "hidden" }}
              onMouseEnter={show}
              onMouseLeave={() => hide()}
            >
              <span className="help-title">{entry.title}</span>
              <span className="help-text">{entry.text}</span>
              {entry.wiki ? (
                <a className="help-link" href={wikiHref(entry.wiki)} onClick={() => setOpen(false)}>
                  {t.common.moreInWiki}
                </a>
              ) : null}
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
