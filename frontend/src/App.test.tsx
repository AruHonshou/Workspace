import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { api } from "./api/client";
import App from "./App";

describe("Personal job assistant", () => {
  it("opens résumé onboarding on a fresh local backend", async () => {
    vi.spyOn(api, "listProfiles").mockResolvedValue([]);
    render(<App />);
    await vi.waitFor(() => expect(api.listProfiles).toHaveBeenCalledOnce());
    expect((await screen.findAllByRole("heading", { name: "Mi CV" })).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Necesitas las dos versiones/)).toBeInTheDocument();
    expect(screen.getByText("CV en español")).toBeInTheDocument();
    expect(screen.getByText("CV en inglés")).toBeInTheDocument();
  });

  it("shows only Ame as the visible orchestrator", () => {
    vi.spyOn(api, "listProfiles").mockResolvedValue([]);
    render(<App />);
    expect(screen.getAllByRole("img", { name: /Ame en su terrario retro/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByRole("button", { name: /Gura|Ina|Kiara|Calli/ })).not.toBeInTheDocument();
  });

  it("uses the simplified navigation and removes technical workflow labels", async () => {
    vi.spyOn(api, "listProfiles").mockResolvedValue([]);
    render(<App />);
    const nav = screen.getByRole("navigation", { name: "Navegación principal" });
    expect(nav).toHaveTextContent("Mi CV");
    expect(nav).toHaveTextContent("Buscar empleos");
    expect(nav).toHaveTextContent("Mis intereses");
    expect(nav).not.toHaveTextContent(/pipeline|paquetes|shortlist/i);

    await userEvent.click(screen.getByRole("button", { name: "EN" }));
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toHaveTextContent("My résumé");
  });
});
