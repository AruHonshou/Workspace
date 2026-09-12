import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Link, MemoryRouter, useLocation } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { api, type BackendProfile, type DeepFitAnalysisV2, type SavedJob } from "../api/client";
import { FilterSelect } from "../components/DashboardViews";
import { CountryPicker } from "../components/GlobalViews";
import { SavedJobsPage } from "../pages/SavedJobsPage";
import { WorkspaceActivity } from "./WorkspaceActivity";
import { panelFromLocation, WorkspaceRoutes } from "./WorkspaceRoutes";

const profile = { profile_id: "profile_qa", confirmed: true, display_name: "QA", name: "QA", facts: [], resumes: {} } as unknown as BackendProfile;
const saved = (id: string): SavedJob => ({
  saved_id: id, job_id: id, title: `QA ${id}`, company: "Example company", location: "Costa Rica",
  description: "QA with Playwright", apply_url: "https://example.com/jobs/qa", apply_url_type: "official", source_portals: ["LinkedIn"],
}) as unknown as SavedJob;

function Harness() {
  const location = useLocation();
  return <><nav><Link to="/mi-cv">Profile tab</Link><Link to="/buscar">Search tab</Link>
    <Link to="/favoritos">Favorites tab</Link><Link to="/favoritos/first">First job</Link><Link to="/favoritos/second">Second job</Link></nav>
    <WorkspaceRoutes locale="es" activePanel={panelFromLocation(location)} home={<p>Desk</p>}
      renderView={(view) => view === "favorites" ? <SavedJobsPage locale="es" /> : <p>{view} page</p>} /></>;
}

describe("Workspace operations survive navigation", () => {
  it("finishes a pending analysis in its original tab without duplicate AI calls or stolen focus", async () => {
    const getJob = vi.spyOn(api, "getSavedJob").mockImplementation(async (id) => saved(id));
    vi.spyOn(api, "listProfiles").mockResolvedValue([profile]);
    vi.spyOn(api, "getSavedJobGuide").mockRejectedValue(new Error("not generated"));
    vi.spyOn(api, "getSavedJobResumes").mockResolvedValue([]);
    let complete!: (value: DeepFitAnalysisV2) => void;
    const analyze = vi.spyOn(api, "analyzeSavedJob").mockImplementation(() => new Promise((resolve) => { complete = resolve; }));

    render(<MemoryRouter initialEntries={["/favoritos/first"]}><Harness /></MemoryRouter>);
    const button = await screen.findByRole("button", { name: "Analizar brechas" });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    expect(analyze).toHaveBeenCalledWith("first", "profile_qa", "es");
    fireEvent.click(screen.getByRole("link", { name: "Profile tab" }));
    const heading = screen.getByRole("heading", { name: "Mi CV" });
    expect(heading).toHaveFocus();
    await act(async () => complete({ score: 78, executive_summary: "Analysis for the first job", requirement_analysis: [] } as unknown as DeepFitAnalysisV2));
    expect(heading).toHaveFocus();
    expect(document.title).toContain("Mi CV");
    expect(screen.queryByRole("heading", { name: /Encaje estimado/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: "Second job" }));
    expect(await screen.findByRole("heading", { name: "QA second" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Encaje estimado/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "First job" }));
    expect(screen.getByRole("heading", { name: "Encaje estimado: 78%" })).toBeInTheDocument();
    expect(analyze).toHaveBeenCalledTimes(1);
    expect(getJob.mock.calls.every(([id]) => ["first", "second"].includes(id))).toBe(true);
    expect(document.querySelectorAll("#main-content")).toHaveLength(1);
  });

  it("refreshes favorites on reactivation, without a page reload", async () => {
    const list = vi.spyOn(api, "listSavedJobs").mockResolvedValueOnce([saved("first")]).mockResolvedValue([saved("first"), saved("second")]);
    render(<MemoryRouter initialEntries={["/favoritos"]}><Harness /></MemoryRouter>);
    expect(await screen.findByRole("link", { name: "QA first" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "Search tab" }));
    expect(list).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("link", { name: "Favorites tab" }));
    expect(await screen.findByRole("link", { name: "QA second" })).toBeInTheDocument();
    expect(list).toHaveBeenCalledTimes(2);
  });
});

describe("Inactive tab popovers", () => {
  it("immediately removes a portaled select without changing the selected value", async () => {
    const change = vi.fn();
    const content = <FilterSelect label="Profile" ariaLabel="Choose profile" icon="P" value="qa" onChange={change}
      options={[{ value: "qa", label: "QA" }, { value: "dev", label: "Development" }]} />;
    const { rerender } = render(<WorkspaceActivity.Provider value>{content}</WorkspaceActivity.Provider>);
    fireEvent.click(screen.getByRole("button", { name: "Choose profile: QA" }));
    expect(await screen.findByRole("listbox")).toBeInTheDocument();
    rerender(<WorkspaceActivity.Provider value={false}>{content}</WorkspaceActivity.Provider>);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    rerender(<WorkspaceActivity.Provider value>{content}</WorkspaceActivity.Provider>);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(change).not.toHaveBeenCalled();
  });

  it("closes the country portal when its tab becomes inactive", async () => {
    const content = <CountryPicker locale="es" value="CR" onChange={vi.fn()} countries={[{ code: "CR", name: "Costa Rica" }]} />;
    const { rerender } = render(<WorkspaceActivity.Provider value>{content}</WorkspaceActivity.Provider>);
    fireEvent.focus(screen.getByRole("combobox"));
    expect(await screen.findByRole("listbox", { name: "Países" })).toBeInTheDocument();
    rerender(<WorkspaceActivity.Provider value={false}>{content}</WorkspaceActivity.Provider>);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});
