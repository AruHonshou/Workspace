import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, type BackendProfile, type SavedJob } from "../api/client";
import type { InterviewGuide } from "../types";
import { SavedJobDetailPage } from "./SavedJobDetailPage";

const profile = {
  profile_id: "profile_qa",
  display_name: "QA",
  name: "QA",
  confirmed: true,
  facts: [],
  resumes: {},
} as unknown as BackendProfile;

const savedJob = {
  saved_id: "saved_qa",
  title: "QA Engineer",
  company: "Acme",
  location: "Costa Rica",
  description: "Pruebas con Playwright",
  apply_url: "https://example.com/jobs/qa",
  apply_url_type: "official",
  source_portals: ["LinkedIn"],
} as unknown as SavedJob;

const readyGuide = {
  guide_id: "guide_qa",
  status: "ready",
  document_id: "artifact_qa",
} as unknown as InterviewGuide;

afterEach(() => vi.restoreAllMocks());

describe("Saved job workspace", () => {
  it("loads the guide through the modern saved-job route and exposes both PDF actions", async () => {
    vi.spyOn(api, "getSavedJob").mockResolvedValue(savedJob);
    vi.spyOn(api, "listProfiles").mockResolvedValue([profile]);
    const getGuide = vi.spyOn(api, "getSavedJobGuide").mockResolvedValue(readyGuide);
    vi.spyOn(api, "getSavedJobResumes").mockResolvedValue([]);
    vi.spyOn(api, "savedJobGuideUrl").mockImplementation(
      (_savedId, _profileId, disposition) => `/guide/${disposition}.pdf`,
    );

    render(<MemoryRouter initialEntries={["/favoritos/saved_qa"]}><Routes><Route path="/favoritos/:id" element={<SavedJobDetailPage locale="es" />} /></Routes></MemoryRouter>);

    expect(await screen.findByRole("heading", { name: "QA Engineer" })).toBeInTheDocument();
    await waitFor(() => expect(getGuide).toHaveBeenCalledWith("saved_qa", "profile_qa"));
    expect(await screen.findByRole("link", { name: /Abrir guía PDF/ })).toHaveAttribute("href", "/guide/inline.pdf");
    expect(screen.getByRole("link", { name: /Descargar PDF/ })).toHaveAttribute("href", "/guide/attachment.pdf");
  });

  it("never exposes the former English DeepSeek fit error in Spanish mode", async () => {
    vi.spyOn(api, "getSavedJob").mockResolvedValue(savedJob);
    vi.spyOn(api, "listProfiles").mockResolvedValue([profile]);
    vi.spyOn(api, "getSavedJobGuide").mockRejectedValue(new Error("not found"));
    vi.spyOn(api, "getSavedJobResumes").mockResolvedValue([]);
    vi.spyOn(api, "analyzeSavedJob").mockRejectedValue(
      new Error("DeepSeek could not complete the fit analysis"),
    );

    render(<MemoryRouter initialEntries={["/favoritos/saved_qa"]}><Routes><Route path="/favoritos/:id" element={<SavedJobDetailPage locale="es" />} /></Routes></MemoryRouter>);

    const analyzeButton = await screen.findByRole("button", { name: "Analizar brechas" });
    await waitFor(() => expect(analyzeButton).toBeEnabled());
    fireEvent.click(analyzeButton);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "DeepSeek no pudo completar el análisis de brechas. Inténtalo nuevamente.",
    );
    expect(screen.queryByText(/could not complete the fit analysis/i)).not.toBeInTheDocument();
  });
});
