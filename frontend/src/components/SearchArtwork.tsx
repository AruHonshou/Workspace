import { WorkspaceIcon } from "../app/WorkspaceIcon";
import type { Locale } from "../types";

/** Original, code-native illustration; no image requests or interactive layers. */
export function SearchArtwork() {
  return <div className="search-artwork" aria-hidden="true">
    <span className="search-art-orbit" />
    <span className="search-art-sheet search-art-sheet--back" />
    <span className="search-art-sheet"><WorkspaceIcon name="profile" /><i /><i /><i /></span>
    <span className="search-art-lens"><WorkspaceIcon name="search" /></span>
    <span className="search-art-spark">✦</span>
  </div>;
}

export function SearchBenefits({ locale }: { locale: Locale }) {
  const es = locale === "es";
  return <div className="search-benefits">
    <div><span><WorkspaceIcon name="search" /></span><p><strong>{es ? "Más alcance" : "Broader reach"}</strong><small>{es ? "Tus fuentes, en un solo lugar." : "Your sources, all in one place."}</small></p></div>
    <div><span><WorkspaceIcon name="motion" /></span><p><strong>{es ? "Ahorra tiempo" : "Save time"}</strong><small>{es ? "Filtros claros para tu búsqueda." : "Clear filters for your search."}</small></p></div>
    <div><span><WorkspaceIcon name="favorites" /></span><p><strong>{es ? "Mejores oportunidades" : "Better opportunities"}</strong><small>{es ? "Guarda las que van contigo." : "Save the ones that suit you."}</small></p></div>
  </div>;
}
