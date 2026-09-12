from __future__ import annotations

from job_orchestrator.linkedin import parse_linkedin_sections, redact_contact_text


def test_linkedin_sections_support_spanish_and_remove_contacts() -> None:
    parsed = parse_linkedin_sections(
        "Ada Lovelace\nQA Engineer\nContacto: ada@example.com\n"
        "Acerca de\nAutomatizo pruebas web con Playwright.\n"
        "Experiencia\nQA Engineer — Example\n"
        "Habilidades\nPlaywright\nPruebas manuales\n"
        "Certificaciones\nISTQB Foundation"
    )

    assert parsed["headline"] == "QA Engineer"
    assert "Playwright" in parsed["about"]
    assert "Pruebas manuales" in parsed["skills"]
    assert "example.com" not in "\n".join(parsed.values())


def test_contact_redaction_keeps_professional_metrics() -> None:
    safe = redact_contact_text(
        "Reduced regression time by 25%.\nPhone: +1 555 222 3333\nada@example.com"
    )
    assert "25%" in safe
    assert "555" not in safe
    assert "ada@example.com" not in safe


def test_linkedin_pdf_column_order_keeps_summary_out_of_certifications() -> None:
    parsed = parse_linkedin_sections(
        "Licencias y certificaciones\n"
        "Curso de JavaScript\n"
        "Ada Lovelace\n"
        "Software Engineer | QA Automation | Playwright\n"
        "San José, Costa Rica\n"
        "Español (Native or Bilingual)\n"
        "Extracto\n"
        "Ingeniera de software enfocada en calidad y automatización.\n"
        "Page 1 of 4\n"
        "Experiencia\n"
        "QA Engineer — Example Corp\n"
        "Educación\n"
        "Universidad de Costa Rica\n"
        "Aptitudes principales\n"
        "Playwright\nSelenium\n"
        "Certificaciones\n"
        "ISTQB Foundation"
    )

    assert parsed["headline"] == "Software Engineer | QA Automation | Playwright"
    assert parsed["about"] == (
        "Ingeniera de software enfocada en calidad y automatización."
    )
    assert parsed["experience"] == "QA Engineer — Example Corp"
    assert parsed["skills"] == "Playwright\nSelenium"
    assert parsed["certifications"].endswith("ISTQB Foundation")
    assert "Extracto" not in parsed["certifications"]
    assert "Page 1 of 4" not in "\n".join(parsed.values())
