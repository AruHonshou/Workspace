import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { api, type SimpleSearchResult } from "../api/client";
import { SimpleSearchPage } from "./SimpleSearchPage";

const result: SimpleSearchResult = { search_id: "search_test", status: "completed", started_at: "2026-09-07T12:00:00Z", jobs: [], loaded_pages: [0], next_page: 1, cached: false, excluded_count: 4, error: null, warnings: [], total_available: null };

describe("Independent job search", () => {
  it("restores an interrupted search error without resubmitting it", async () => {
    localStorage.setItem("workspace-last-search-id", result.search_id);
    vi.spyOn(api, "getSimpleSearch").mockResolvedValue({ ...result, status: "failed", error: "Página interrumpida; no se reintentó." });
    const search = vi.spyOn(api, "simpleSearch");
    render(<MemoryRouter><SimpleSearchPage locale="es" countries={[]} onSave={vi.fn()} /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Página interrumpida");
    expect(search).not.toHaveBeenCalled();
  });

  it("searches without profiles, preserves empty pages, and loads more explicitly", async () => {
    const search = vi.spyOn(api, "simpleSearch").mockResolvedValue(result);
    const more = vi.spyOn(api, "moreSimpleSearch").mockResolvedValue({ ...result, next_page: null, loaded_pages: [0, 1] });
    const user = userEvent.setup();
    render(<MemoryRouter><SimpleSearchPage locale="es" countries={[{ code: "CR", name: "Costa Rica" }]} onSave={vi.fn()} /></MemoryRouter>);
    await user.type(screen.getByRole("textbox", { name: "¿Qué puesto buscas?" }), "QA");
    await user.click(screen.getByRole("button", { name: "Buscar" }));
    expect(search).toHaveBeenCalledWith(expect.objectContaining({ role: "QA", country_code: "CR", window_days: 7, refresh: false }));
    expect(search.mock.calls[0][0]).not.toHaveProperty("profile_id");
    expect(screen.getByText(/No hay vacantes válidas/)).toBeInTheDocument();
    expect(more).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /Cargar hasta 20/ }));
    expect(more).toHaveBeenCalledWith("search_test", 1);
  });

  it("displays provider errors and never automatically retries", async () => {
    const search = vi.spyOn(api, "simpleSearch").mockResolvedValue({ ...result, status: "failed", error: "TheirStack sin cuota" });
    const user = userEvent.setup();
    render(<MemoryRouter><SimpleSearchPage locale="es" countries={[]} onSave={vi.fn()} /></MemoryRouter>);
    await user.type(screen.getByRole("textbox", { name: "¿Qué puesto buscas?" }), "QA");
    await user.click(screen.getByRole("button", { name: "Buscar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("TheirStack sin cuota");
    expect(search).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: /Cargar hasta 20/ })).not.toBeInTheDocument();
  });
});
