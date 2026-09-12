import type { ReactNode } from "react";
import type { Locale } from "../types";

/** Presentation only: every fact stays mounted, including the overflow rows. */
export function FactDisclosure({ title, verified, locale, children }: {
  title: string;
  verified: number;
  locale: Locale;
  children: ReactNode[];
}) {
  const previewSize = 6;
  const remaining = children.length - previewSize;
  return <section className="fact-disclosure">
    <details className="fact-category">
      <summary>
        <span className="fact-category-symbol" aria-hidden="true">≡</span>
        <span className="fact-category-title">{title}<span className="fact-count">{children.length}</span></span>
        <span className="fact-verified-count">✓ {verified} {locale === "es" ? "revisados" : "reviewed"}</span>
        <span className="disclosure-chevron" aria-hidden="true">⌄</span>
      </summary>
      <div className="fact-review-list">{children.slice(0, previewSize)}</div>
      {remaining > 0 && <details className="fact-overflow">
        <summary><span className="disclosure-more">{locale === "es" ? `Ver ${remaining} más` : `Show ${remaining} more`}</span><span className="disclosure-less">{locale === "es" ? "Mostrar menos" : "Show less"}</span><span className="disclosure-chevron" aria-hidden="true">⌄</span></summary>
        <div className="fact-review-list">{children.slice(previewSize)}</div>
      </details>}
    </details>
  </section>;
}
