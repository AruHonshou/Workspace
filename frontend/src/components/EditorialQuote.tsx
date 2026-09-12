import type { Locale } from "../types";

const quotes: Record<string, Record<Locale, string>> = {
  buscar: { es: "Cada búsqueda puede\nabrir una puerta.", en: "Every search can\nopen a door." },
  favoritos: { es: "Buenas oportunidades\nllevan a grandes historias.", en: "Great opportunities\nlead to great stories." },
  "mi-cv": { es: "Tu historia merece\nestar bien contada.", en: "Your story deserves\nto be told well." },
  "sobre-mi": { es: "Lo que sabes hacer\ntambién cuenta tu historia.", en: "What you can do\ntells your story, too." },
  candidaturas: { es: "Cada paso te acerca\na la oportunidad correcta.", en: "Every step brings you closer\nto the right opportunity." },
  linkedin: { es: "La forma en que te presentas\nabre conversaciones.", en: "How you introduce yourself\nstarts conversations." },
  configuracion: { es: "Tu espacio.\nTus datos. Tus reglas.", en: "Your space.\nYour data. Your rules." },
};

export function EditorialQuote({ path, locale }: { path: string; locale: Locale }) {
  const quote = quotes[path.split("/")[1]]?.[locale];
  return quote ? <p className="editorial-quote">{quote}</p> : null;
}
