from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf" / "manual-career-orchestrator.pdf"

INK = colors.HexColor("#302B36")
MUTED = colors.HexColor("#74666F")
PEACH = colors.HexColor("#70C8BE")
CREAM = colors.HexColor("#FFF9E9")
PANEL = colors.HexColor("#FFFDF9")
LINE = colors.HexColor("#E7D4CA")
CORAL = colors.HexColor("#2D8B83")
BLUE = colors.HexColor("#3AAEC0")
PURPLE = colors.HexColor("#8B70C6")
GOLD = colors.HexColor("#E7B43E")
GREEN = colors.HexColor("#4D8B57")
PINK = colors.HexColor("#D86889")
NAVY = colors.HexColor("#302C43")


def register_fonts() -> None:
    font_dir = Path(r"C:\Windows\Fonts")
    pdfmetrics.registerFont(TTFont("UI", str(font_dir / "segoeui.ttf")))
    pdfmetrics.registerFont(TTFont("UI-Bold", str(font_dir / "segoeuib.ttf")))


register_fonts()
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="CoverKicker", fontName="UI-Bold", fontSize=9, leading=11, textColor=colors.white, spaceAfter=10))
styles.add(ParagraphStyle(name="CoverTitle", fontName="UI-Bold", fontSize=34, leading=38, textColor=INK, spaceAfter=14))
styles.add(ParagraphStyle(name="CoverSub", fontName="UI", fontSize=12.5, leading=18, textColor=colors.HexColor("#65484C"), spaceAfter=16))
styles.add(ParagraphStyle(name="H1x", fontName="UI-Bold", fontSize=24, leading=29, textColor=INK, spaceAfter=8))
styles.add(ParagraphStyle(name="Bodyx", fontName="UI", fontSize=9.2, leading=13.6, textColor=INK, spaceAfter=6))
styles.add(ParagraphStyle(name="Smallx", fontName="UI", fontSize=7.6, leading=10.5, textColor=MUTED))
styles.add(ParagraphStyle(name="Labelx", fontName="UI-Bold", fontSize=7.2, leading=9, textColor=CORAL, spaceAfter=4))
styles.add(ParagraphStyle(name="CardTitle", fontName="UI-Bold", fontSize=8.8, leading=11, textColor=INK, spaceAfter=3))
styles.add(ParagraphStyle(name="CardBody", fontName="UI", fontSize=7.45, leading=10.1, textColor=MUTED))
styles.add(ParagraphStyle(name="CodexBlock", fontName="Courier", fontSize=7.1, leading=9.8, textColor=colors.HexColor("#F5ECF1")))
styles.add(ParagraphStyle(name="Center", fontName="UI-Bold", fontSize=7, leading=9, textColor=INK, alignment=TA_CENTER))


def p(text: str, style: str = "Bodyx") -> Paragraph:
    return Paragraph(text, styles[style])


def section(number: str, title: str, subtitle: str) -> list[Flowable]:
    return [p(number.upper(), "Labelx"), p(title, "H1x"), p(subtitle, "Smallx"), Spacer(1, 7 * mm)]


def callout(title: str, body: str, color=CORAL) -> Table:
    table = Table([[p(title, "CardTitle"), p(body, "CardBody")]], colWidths=[38 * mm, 116 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF3EC")),
        ("BOX", (0, 0), (-1, -1), .7, colors.HexColor("#E8C7B8")),
        ("LINEBEFORE", (0, 0), (0, -1), 3, color), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def cards(items: list[tuple[str, str]]) -> Table:
    cells = [p(f"<font size='9'><b>{title}</b></font><br/><br/>{body}", "CardBody") for title, body in items]
    rows = [[cells[i], cells[i + 1] if i + 1 < len(cells) else p("", "CardBody")] for i in range(0, len(cells), 2)]
    table = Table(rows, colWidths=[77 * mm, 77 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL), ("BOX", (0, 0), (-1, -1), .6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), .6, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return table


def steps(items: list[tuple[str, str]]) -> Table:
    rows = []
    for index, (title, body) in enumerate(items, start=1):
        badge = Table([[p(f"{index:02d}", "Center")]], colWidths=[10 * mm], rowHeights=[10 * mm])
        badge.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PEACH), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        rows.append([badge, p(f"<b>{title}</b><br/>{body}", "CardBody")])
    table = Table(rows, colWidths=[14 * mm, 140 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LINEBELOW", (1, 0), (1, -2), .45, LINE),
    ]))
    return table


def code_block(text: str) -> Table:
    table = Table([[p(text.replace("\n", "<br/>"), "CodexBlock")]], colWidths=[154 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY), ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11), ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return table


class Architecture(Flowable):
    def __init__(self) -> None:
        super().__init__()
        self.width, self.height = 154 * mm, 76 * mm

    def draw(self) -> None:
        c = self.canv
        nodes = [
            (0, 45, 42, 22, "React + Three.js", "Ame scene | panels | WebGL", colors.HexColor("#E7F6EF")),
            (56, 45, 42, 22, "FastAPI", "REST | SSE | validation", colors.HexColor("#ECF7F4")),
            (112, 45, 42, 22, "LangGraph", "5 roles | checkpoints", colors.HexColor("#F3EEFD")),
            (0, 6, 42, 22, "SQLite", "profiles | jobs | interests", colors.HexColor("#FFF7DB")),
            (56, 6, 42, 22, "TheirStack", "CR jobs | 25 per page", colors.HexColor("#E2F4F1")),
            (112, 6, 42, 22, "DeepSeek API", "typed agent proposals", colors.HexColor("#FCECF2")),
        ]
        for x, y, w, h, title, detail, fill in nodes:
            c.setFillColor(fill); c.setStrokeColor(LINE)
            c.roundRect(x * mm, y * mm, w * mm, h * mm, 6, fill=1, stroke=1)
            c.setFillColor(INK); c.setFont("UI-Bold", 7.5); c.drawString((x + 4) * mm, (y + 13) * mm, title)
            c.setFillColor(MUTED); c.setFont("UI", 6.1); c.drawString((x + 4) * mm, (y + 7) * mm, detail)
        c.setStrokeColor(colors.HexColor("#AF8E83")); c.setLineWidth(1.2)
        for x1, y1, x2, y2 in [(42, 56, 56, 56), (98, 56, 112, 56), (77, 45, 21, 28), (77, 45, 77, 28), (133, 45, 133, 28)]:
            c.line(x1 * mm, y1 * mm, x2 * mm, y2 * mm)


def on_cover(canvas, _doc) -> None:
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#65B9C5")); canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#3D8791")); canvas.circle(width * .82, height * .14, 105 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#D9F0D4")); canvas.circle(width * .12, height * .86, 42 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white); canvas.setFont("UI-Bold", 8)
    canvas.drawString(22 * mm, height - 18 * mm, "AMEWORK  /  MANUAL V3")
    canvas.setFillColor(colors.HexColor("#FFF9E9")); canvas.roundRect(22 * mm, 30 * mm, 66 * mm, 26 * mm, 6, fill=1, stroke=0)
    canvas.setFillColor(GREEN); canvas.circle(34 * mm, 43 * mm, 7 * mm, fill=1, stroke=0)
    canvas.setFillColor(INK); canvas.setFont("UI-Bold", 8); canvas.drawString(46 * mm, 45 * mm, "AME ORQUESTADORA")
    canvas.setFillColor(MUTED); canvas.setFont("UI", 6.5); canvas.drawString(46 * mm, 39 * mm, "Terrario 3D | animacion original")
    canvas.setFillColor(colors.HexColor("#E8FFFB")); canvas.setFont("UI", 7)
    canvas.drawString(22 * mm, 18 * mm, "TheirStack | DeepSeek | LangGraph | 24 agosto 2026")
    canvas.restoreState()


def on_page(canvas, _doc) -> None:
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(CREAM); canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setFillColor(PEACH); canvas.rect(0, height - 4 * mm, width, 4 * mm, fill=1, stroke=0)
    canvas.setFillColor(MUTED); canvas.setFont("UI-Bold", 6.3)
    canvas.drawString(22 * mm, height - 13 * mm, "AMEWORK")
    canvas.setFont("UI", 6.3); canvas.drawRightString(width - 22 * mm, height - 13 * mm, "Manual de uso y arquitectura")
    canvas.setStrokeColor(LINE); canvas.line(22 * mm, 15 * mm, width - 22 * mm, 15 * mm)
    canvas.setFillColor(MUTED); canvas.setFont("UI", 6.3)
    canvas.drawString(22 * mm, 9 * mm, "CV local | IA en la nube con consentimiento | Sin postulacion automatica")
    canvas.drawRightString(width - 22 * mm, 9 * mm, f"{canvas.getPageNumber():02d}")
    canvas.restoreState()


def build_story() -> list[Flowable]:
    story: list[Flowable] = [
        Spacer(1, 52 * mm), p("MANUAL BILINGUE / BILINGUAL MANUAL", "CoverKicker"),
        p("Tu equipo para<br/>buscar trabajo", "CoverTitle"),
        p("Uso, arquitectura, seguridad y experiencia visual del orquestador personal para Costa Rica.", "CoverSub"),
        callout("Flujo principal", "Confirma tus CV en espanol e ingles, busca con TheirStack en tandas de 25, filtra hasta 30 dias y crea una guia de entrevista desde Me interesa.", NAVY), PageBreak(),
    ]

    story += section("ES 01 / Uso", "De tu CV a la entrevista", "La interfaz mantiene las decisiones importantes en tus manos.")
    story += [steps([
        ("Configura las conexiones", "Abre Configuracion y valida por separado TheirStack para buscar y DeepSeek para analizar. Ambas claves quedan en el Administrador de credenciales de Windows."),
        ("Confirma tus dos CV", "Importa una version en espanol y otra en ingles. Corrige los hechos extraidos y confirma el perfil; cada vacante usa automaticamente el CV de su idioma."),
        ("Busca un rol", "Escribe QA, Desarrollador, Analista de datos u otro objetivo. La primera tanda recupera hasta 25 vacantes de Costa Rica."),
        ("Filtra o carga mas", "Cambia entre 24 horas, 7 dias o 30 dias sin repetir la busqueda. Cargar 25 mas pide y cachea la pagina siguiente."),
        ("Actua", "Abre el analisis, visita la publicacion oficial o pulsa Me interesa para guardar la vacante y generar su guia PDF."),
    ]), Spacer(1, 6 * mm), callout("Regla de alcance", "Todos significa todos los resultados recuperables desde las fuentes habilitadas en esa ejecucion, no todo Internet.", GREEN), PageBreak()]

    story += section("ES 02 / Fuentes", "TheirStack primero, respaldo seguro", "La busqueda automatica respeta API, creditos, cache, procedencia y atribucion.")
    story += [cards([
        ("Fuente principal", "TheirStack busca vacantes abiertas en Costa Rica, con antiguedad maxima de 30 dias y 25 resultados por tanda."),
        ("Creditos", "Cada vacante devuelta puede consumir un credito. No hay retries automaticos de paginas cobrables y el doble clic queda bloqueado."),
        ("Ventana", "La fecha UTC debe ser exacta, no futura y posterior al inicio de la busqueda menos 30 dias. Una fecha de actualizacion no cuenta."),
        ("Procedencia", "Proveedor, portal de origen, URL de origen, URL final y tipo de enlace se guardan por separado. Un enlace de portal nunca se llama oficial."),
        ("Respaldo", "Jobicy, Remotive, Remote OK, Himalayas, We Work Remotely y ATS configurados siguen disponibles si TheirStack falla."),
        ("Deduplicacion", "Las copias equivalentes se fusionan; se prioriza final_url, luego url y finalmente source_url."),
    ]), Spacer(1, 6 * mm), callout("Enlaces", "La aplicacion nunca completa formularios, envia correos ni presenta candidaturas.", GOLD), PageBreak()]

    story += section("ES 03 / Agentes", "Cinco roles internos, una Ame visible", "LangGraph conserva cinco responsabilidades separadas; la interfaz no representa conversaciones ni razonamiento privado.")
    rows = [
        [p("Rol", "CardTitle"), p("Responsabilidad", "CardTitle"), p("Limite", "CardTitle")],
        [p("Coordinacion", "CardTitle"), p("Comprueba el perfil, delega y comunica.", "CardBody"), p("No busca ni puntua.", "CardBody")],
        [p("Busqueda", "CardTitle"), p("Amplia el rol y consulta fuentes autorizadas.", "CardBody"), p("No recibe datos personales.", "CardBody")],
        [p("Analisis", "CardTitle"), p("Relaciona requisitos con hechos confirmados.", "CardBody"), p("No inventa experiencia.", "CardBody")],
        [p("Preparacion", "CardTitle"), p("Ordena evidencia para la entrevista.", "CardBody"), p("No postula por el usuario.", "CardBody")],
        [p("Revision", "CardTitle"), p("Comprueba fechas, enlaces, evidencia y PDF.", "CardBody"), p("No relaja validadores.", "CardBody")],
    ]
    table = Table(rows, colWidths=[31 * mm, 76 * mm, 47 * mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3D4C2")), ("GRID", (0, 0), (-1, -1), .55, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [table, Spacer(1, 7 * mm), callout("Autoridad", "LangChain create_agent propone JSON tipado. Fechas, filtros, deduplicacion, puntuacion y PDF se validan de forma determinista.", PURPLE), PageBreak()]

    story += section("ES 04 / Claves", "Dos proveedores, dos limites", "Las credenciales se validan por separado y nunca regresan al navegador.")
    story += [cards([
        ("DeepSeek", "deepseek-v4-pro apoya la expansion del rol y valida relaciones de encaje con JSON tipado. Fechas, puntuacion y guias PDF son deterministas."),
        ("TheirStack", "La validacion consulta un endpoint autenticado sin recuperar vacantes ni consumir creditos de resultados."),
        ("CV original", "El PDF no sale del equipo. Se envian solo hechos confirmados sin correo, telefono ni direccion."),
        ("Errores", "Autenticacion, saldo, cuota o timeout se muestran claramente y pueden reintentarse desde el checkpoint."),
        ("Sin secretos", "La clave no aparece en SQLite, logs, SSE, checkpoints, errores ni documentos exportados."),
        ("Borrar", "Configuracion permite eliminar cada credencial sin borrar CV, vacantes, intereses ni guias."),
    ]), Spacer(1, 6 * mm), callout("Aviso", "Al ejecutar analisis, los hechos profesionales confirmados y la descripcion necesaria se procesan en la nube de DeepSeek.", CORAL), PageBreak()]

    story += section("ES 05 / Escena", "Ame dentro del terrario", "Un solo GLB ocupa el fondo completo y reproduce su animacion original de nueve segundos.")
    story += [cards([
        ("Animacion", "El clip Animation se reproduce completo en bucle. El GLB permanece identico byte por byte y no se crean subclips."),
        ("Rotacion", "Arrastra para observar la escena. Los limites de orbita evitan angulos inutiles."),
        ("Zoom", "Usa la rueda o el gesto de pinza. La distancia minima y maxima impiden perder el modelo."),
        ("Desplazamiento", "Boton derecho o dos dedos mueven el encuadre dentro de limites seguros."),
        ("Restablecer", "El boton de camara recupera el centro, zoom y objetivo calculados desde el volumen real del GLB."),
        ("Accesibilidad", "Movimiento reducido mantiene una pose estable. WebGL ausente activa una ilustracion estatica con los mismos paneles DOM."),
    ]), Spacer(1, 6 * mm), callout("Interfaz", "No hay globos, nombres de avatares ni consola de agentes: solo resultados, acciones y errores claros.", BLUE), PageBreak()]

    story += section("ES 06 / Arquitectura", "Componentes y diagnostico", "REST ejecuta comandos, SSE transmite progreso y los checkpoints permiten reanudar.")
    story += [Architecture(), Spacer(1, 3 * mm), cards([
        ("Persistencia", "app.db conserva perfiles, vacantes e intereses. checkpoints.db conserva el estado del grafo. artifacts/ contiene entradas y PDF."),
        ("Inicio", "Ejecuta bootstrap una vez y dev para iniciar API y frontend en loopback."),
    ]), Spacer(1, 5 * mm), code_block("git clone https://github.com/AruHonshou/AmeWork.git\ncd AmeWork\n.\\scripts\\bootstrap.ps1\n.\\scripts\\dev.ps1\n# UI  http://127.0.0.1:5173\n# API http://127.0.0.1:8765"), Spacer(1, 5 * mm), callout("Problemas", "Sin resultados: amplia el rol y revisa cobertura. Error 401: vuelve a validar la clave. Error de fuente: reintenta despues del limite indicado.", GREEN), PageBreak()]

    story += section("EN 01 / Workflow", "From resume to interview", "The interface keeps every important decision under your control.")
    story += [steps([
        ("Configure connections", "Validate TheirStack for search and DeepSeek for analysis in separate Settings cards. Both keys stay in Windows Credential Manager."),
        ("Confirm both resumes", "Import one Spanish and one English version. Review the extracted facts and confirm the profile; each job automatically uses the matching language."),
        ("Search a role", "Enter QA, Developer, Data analyst, or another target. The first batch retrieves up to 25 Costa Rica jobs."),
        ("Filter or load more", "Switch between 24 hours, 7 days, and 30 days locally. Load 25 more requests and caches the next page."),
        ("Continue", "Open the analysis, visit the official posting, or select I'm interested to save the job and create its interview PDF."),
    ]), Spacer(1, 6 * mm), callout("Coverage", "All means all retrievable results from the enabled sources during that run, not every job on the Internet.", GREEN), PageBreak()]

    story += section("EN 02 / Sources", "TheirStack first, safe fallbacks", "Automated search respects API credits, caching, provenance, attribution, and rate limits.")
    story += [cards([
        ("Primary source", "TheirStack searches open Costa Rica jobs no older than 30 days and returns at most 25 records per batch."),
        ("Credits", "Each returned job may consume one credit. Billable pages are never retried automatically and duplicate requests are blocked."),
        ("Date rule", "UTC publication time must be exact, not future, and no earlier than search start minus 30 days. Updated time is not accepted."),
        ("Provenance", "Provider, source portal, source URL, final URL, and link type stay separate. A portal link is never labeled official."),
        ("Fallbacks", "Jobicy, Remotive, Remote OK, Himalayas, We Work Remotely, and configured ATSs remain available if TheirStack fails."),
        ("Deduplication", "Equivalent copies are merged with final_url first, then url, then source_url."),
    ]), Spacer(1, 6 * mm), callout("Applications", "The application never fills a form, sends email, or submits an application.", GOLD), PageBreak()]

    story += section("EN 03 / Provider safety", "Two keys, two boundaries", "Credentials are validated separately and never returned to the browser.")
    story += [cards([
        ("DeepSeek", "deepseek-v4-pro supports role expansion and validates fit mappings with typed JSON. Dates, scoring, and interview PDFs remain deterministic."),
        ("TheirStack", "Validation uses an authenticated endpoint that reveals no jobs and consumes no result credits."),
        ("Original resume", "The file stays on the computer. Only confirmed professional facts without contact details are sent."),
        ("Failures", "Authentication, balance, quota, and timeout errors are explicit and retryable from the checkpoint."),
        ("Secret boundary", "The key never enters SQLite, logs, SSE events, checkpoints, errors, or exported documents."),
        ("Human control", "The user confirms facts, chooses jobs, opens external links, and owns every application decision."),
    ]), Spacer(1, 6 * mm), callout("Cloud notice", "Confirmed professional facts and the necessary job description are processed by DeepSeek when analysis runs.", CORAL), PageBreak()]

    story += section("EN 04 / Scene", "Ame inside the terrarium", "One GLB fills the background and loops its original nine-second animation.")
    story += [cards([
        ("Animation", "The complete Animation clip loops. The GLB stays byte-for-byte identical and no subclips are created."),
        ("Rotate", "Drag to inspect the scene. Orbit limits avoid unusable angles."),
        ("Zoom", "Use the wheel or pinch gesture. Minimum and maximum distances keep the model in reach."),
        ("Pan", "Right drag or two fingers move the composition within safe limits."),
        ("Reset", "The camera button restores center, zoom, and target computed from the real GLB bounds."),
        ("Accessibility", "Reduced motion keeps a stable pose. Missing WebGL activates a static illustration with the same DOM controls."),
    ]), Spacer(1, 6 * mm), callout("Interface", "No speech bubbles, avatar labels, or agent console: only results, actions, and clear errors.", BLUE), PageBreak()]

    story += section("EN 05 / Verification", "How to test the project", "CI uses simulated sources and a fake DeepSeek server; the optional smoke test uses the saved key.")
    story += [code_block(".\\scripts\\validate-assets.ps1\n.\\scripts\\test.ps1\npnpm --dir frontend typecheck\npnpm --dir frontend test -- --run\npnpm --dir frontend build"), Spacer(1, 7 * mm), cards([
        ("Search", "Boundary times, pagination, deduplication, source failures, rate limits, large result sets, and portal no-automation policy."),
        ("Privacy", "Key and contact data are absent from databases, logs, events, checkpoints, errors, and PDF output."),
        ("Evidence", "Structured outputs reject unknown IDs; recommendations and interview answers cannot fabricate experience."),
        ("Visuals", "Single-GLB download, nine-second loop, orbit limits, reset, reduced motion, and static fallback."),
    ]), Spacer(1, 6 * mm), callout("Project folder", "Run all commands from the cloned AmeWork repository root.", GREEN), PageBreak()]

    story += section("EN 06 / Reference", "Endpoints and data ownership", "The browser receives status, never the DeepSeek key.")
    story += [cards([
        ("Settings", "Separate DeepSeek and TheirStack GET, PUT, DELETE endpoints expose configured status and validation time only."),
        ("Search", "POST /api/career/searches requests the first 25-job page; /more accepts only the cached run's next page."),
        ("Results", "Stored jobs include exact publication time, modality, provider, source portal, link type, verification, and quick fit."),
        ("Interests", "One interest per profile and job. Repeated clicks are idempotent and preserve the existing guide."),
        ("Delete", "Removing either credential does not delete the confirmed resume, saved jobs, interests, or guides."),
        ("License", "Smol Ame in an Upcycled Terrarium by Seafoam remains CC BY 4.0 and separate from Apache-2.0 application code."),
    ]), Spacer(1, 6 * mm), callout("Final rule", "Never put real resumes, API keys, downloaded jobs, or undocumented third-party assets into a public repository.", NAVY)]
    return story


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame = Frame(22 * mm, 19 * mm, A4[0] - 44 * mm, A4[1] - 38 * mm, id="content", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc = BaseDocTemplate(str(OUT), pagesize=A4, title="AmeWork - Manual bilingue", author="AmeWork contributors", subject="Uso y arquitectura del orquestador multiagente", creator="ReportLab")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=on_cover, autoNextPageTemplate="body"),
        PageTemplate(id="body", frames=[frame], onPage=on_page),
    ])
    doc.build(build_story())
    print(OUT)


if __name__ == "__main__":
    main()
