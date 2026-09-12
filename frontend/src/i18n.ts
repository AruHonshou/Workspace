import type { Locale } from "./types";

const es: Record<string, string> = {
  "common.cancel": "Cancelar",
  "common.edit": "Editar",
  "common.save": "Guardar",
  "profile.confirm": "Confirmar mi CV",
  "profile.confirmed": "CV confirmado",
  "profile.confirming": "Confirmando…",
  "profile.extractedFacts": "Datos extraídos",
  "profile.name": "Perfil",
  "profile.pending": "Pendiente de revisión",
  "profile.ready": "Listo para buscar",
  "profile.review": "Revisar resumen",
  "profile.status": "Estado",
  "profile.title": "Mi CV",
  "settings.applications": "La aplicación abre la publicación original, pero nunca rellena ni envía una candidatura.",
  "settings.applicationsTitle": "Postulaciones",
  "settings.cvTitle": "Tu CV",
  "settings.title": "Configuración y privacidad",
  "notice.profileImported": "CV importado. Revisa la información extraída antes de confirmarlo.",
};

const en: Record<string, string> = {
  "common.cancel": "Cancel",
  "common.edit": "Edit",
  "common.save": "Save",
  "profile.confirm": "Confirm my résumé",
  "profile.confirmed": "Résumé confirmed",
  "profile.confirming": "Confirming…",
  "profile.extractedFacts": "Extracted facts",
  "profile.name": "Profile",
  "profile.pending": "Review required",
  "profile.ready": "Ready to use",
  "profile.review": "Review summary",
  "profile.status": "Status",
  "profile.title": "My résumé",
  "settings.applications": "The app opens the original listing but never completes or submits an application.",
  "settings.applicationsTitle": "Applications",
  "settings.cvTitle": "Your résumé",
  "settings.title": "Settings and privacy",
  "notice.profileImported": "Résumé imported. Review the extracted information before confirming it.",
};

const copy: Record<Locale, Record<string, string>> = { es, en };

export type Translate = (
  key: string,
  variables?: Record<string, string | number | boolean>,
) => string;

export function createTranslator(locale: Locale): Translate {
  return (key, variables = {}) => (copy[locale][key] ?? es[key] ?? key).replace(
    /\{(\w+)\}/g,
    (_, name: string) => String(variables[name] ?? `{${name}}`),
  );
}
