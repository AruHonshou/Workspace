import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { api, type BackendProfile } from "./api/client";
import App from "./App";

describe("Personal job assistant", () => {
  it("opens directly on the original desk without an entry gate or audio", async () => {
    vi.spyOn(api, "listProfiles").mockResolvedValue([]);
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    const { container } = render(<App />);
    expect(screen.getByRole("heading", { name: "Un espacio para lo que sigue." })).toBeInTheDocument();
    expect(container.querySelector("audio")).toBeNull();
    expect(screen.queryByRole("button", { name: /Entrar a/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Activar modo oscuro" })).not.toBeInTheDocument();
    expect(play).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Animaciones de cámara" }));
    expect(localStorage.getItem("workspace-static-view")).toBe("true");
    expect(screen.getByRole("button", { name: "Animaciones de cámara" })).toHaveAttribute("aria-pressed", "false");
  });

  it("keeps a fresh backend on home and opens the résumé page on request", async () => {
    vi.spyOn(api, "listProfiles").mockResolvedValue([]);
    render(<App />);
    await vi.waitFor(() => expect(api.listProfiles).toHaveBeenCalledOnce());
    expect(window.location.pathname).toBe("/");
    await userEvent.click(screen.getByRole("link", { name: "Explorar oportunidades" }));
    await userEvent.click(screen.getByRole("link", { name: "Mi CV" }));
    expect(window.location.pathname).toBe("/mi-cv");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect((await screen.findAllByRole("heading", { name: "Mi CV" })).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Elige el CV que representa este perfil/)).toBeInTheDocument();
    expect(screen.getByText("CV en español")).toBeInTheDocument();
    expect(screen.getByText("CV en inglés")).toBeInTheDocument();
    expect(screen.queryByText(/Añadir otro idioma/)).not.toBeInTheDocument();
  });

  it("recovers the stored profiles when the first bootstrap request fails", async () => {
    const storedProfile = {
      profile_id: "profile_retry",
      display_name: "QA recuperado",
      name: "QA recuperado",
      summary: "QA engineer",
      revision: 1,
      confirmed: true,
      facts: [],
      resumes: { es: { filename: "cv.pdf", imported_at: "2026-08-20T18:00:00Z" } },
      preferences: {
        desired_titles: ["QA"],
        target_seniorities: [],
        allowed_work_modes: [],
        desired_locations: [],
        excluded_keywords: [],
        excluded_sectors: [],
      },
    } as unknown as BackendProfile;
    const listProfiles = vi.spyOn(api, "listProfiles")
      .mockRejectedValueOnce(new Error("backend starting"))
      .mockResolvedValueOnce([storedProfile]);

    render(<App />);
    await vi.waitFor(() => expect(listProfiles).toHaveBeenCalledTimes(2), { timeout: 2_000 });
    await userEvent.click(screen.getByRole("link", { name: "Explorar oportunidades" }));
    await userEvent.click(screen.getByRole("link", { name: "Mi CV" }));

    expect((await screen.findAllByText("QA recuperado")).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Sin perfil")).not.toBeInTheDocument();
  });

  it("keeps the desktop fallback available when WebGL is unavailable", async () => {
    vi.spyOn(api, "listProfiles").mockResolvedValue([]);
    render(<App />);
    expect(await screen.findByRole("img", { name: /Vista en primera persona/ })).toHaveAttribute("src", "/branding/desk-fallback.svg");
    expect(screen.getAllByText("Workspace").length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("link", { name: "Explorar oportunidades" }));
    expect(screen.getByRole("heading", { level: 1, name: "Buscar empleos" })).toBeInTheDocument();
  });

  it("keeps a direct LinkedIn URL when the profile list is empty", async () => {
    window.history.replaceState(null, "", "/linkedin");
    vi.spyOn(api, "listProfiles").mockResolvedValue([]);
    render(<App />);
    await vi.waitFor(() => expect(api.listProfiles).toHaveBeenCalledOnce());
    expect(window.location.pathname).toBe("/linkedin");
    expect(screen.getByRole("heading", { level: 1, name: "LinkedIn" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("supports browser back and forward without a modal", async () => {
    vi.spyOn(api, "listProfiles").mockResolvedValue([]);
    render(<App />);
    await userEvent.click(screen.getByRole("link", { name: "Explorar oportunidades" }));
    await userEvent.click(screen.getByRole("link", { name: "Mi CV" }));
    await userEvent.click(screen.getByRole("link", { name: "LinkedIn" }));
    window.history.back();
    await vi.waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Mi CV" })).toBeInTheDocument());
    window.history.forward();
    await vi.waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "LinkedIn" })).toBeInTheDocument());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("uses the simplified navigation and removes technical workflow labels", async () => {
    vi.spyOn(api, "listProfiles").mockResolvedValue([]);
    render(<App />);
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "Explorar oportunidades" }));
    const nav = screen.getByRole("navigation", { name: "Navegación principal" });
    expect(nav).toHaveTextContent("Mi CV");
    expect(nav).toHaveTextContent("Sobre mí");
    expect(nav).toHaveTextContent("Buscar empleos");
    expect(nav).toHaveTextContent("Favoritos");
    expect(nav).toHaveTextContent("Candidaturas");
    expect(nav).toHaveTextContent("LinkedIn");
    expect(nav).not.toHaveTextContent(/pipeline|paquetes|shortlist/i);

    expect(nav.querySelectorAll("a")).toHaveLength(7);
    await userEvent.click(screen.getByRole("link", { name: "Favoritos" }));
    expect(window.location.pathname).toBe("/favoritos");
    expect(window.location.search).toBe("");

    await userEvent.click(screen.getByRole("button", { name: "Cambiar a inglés" }));
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toHaveTextContent("My résumé");
  });
});
