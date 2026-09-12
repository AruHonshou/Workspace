import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, useLocation, useNavigate } from "react-router";
import { describe, expect, it } from "vitest";
import { WorkspaceRoutes, panelFromLocation, panelPath } from "./WorkspaceRoutes";
import type { ViewId } from "../types";
import { useWorkspaceActive } from "./WorkspaceActivity";

function Harness() {
  const location = useLocation();
  return <WorkspaceRoutes locale="es" activePanel={panelFromLocation(location)}
    home={<p>Inicio</p>} renderView={(view) => <p>Vista: {view}</p>} />;
}

describe("Full-page routes", () => {
  it.each([
    ["/mi-cv", "Mi CV", "profile"], ["/linkedin", "LinkedIn", "linkedin"],
    ["/sobre-mi", "Sobre mí", "about"], ["/candidaturas", "Candidaturas", "applications"],
    ["/configuracion", "Configuración", "settings"], ["/buscar", "Buscar empleos", "search"],
  ])("opens %s directly without a modal", (path, title, view) => {
    render(<MemoryRouter initialEntries={[path]}><Harness /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: title })).toHaveFocus();
    expect(screen.getByText(`Vista: ${view}`)).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("explains unknown routes instead of silently displaying the home scene", () => {
    render(<MemoryRouter initialEntries={["/does-not-exist"]}><Harness /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Página no encontrada" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir al buscador" })).toHaveAttribute("href", "/buscar");
  });

  it("does not mistake similarly named unknown routes for cached modules", () => {
    expect(panelFromLocation({ pathname: "/favoritos-archivados", search: "" })).toBeNull();
    expect(panelPath("favorites")).toBe("/favoritos");
  });
});

function Draft({ view }: { view: ViewId }) {
  const [draft, setDraft] = useState("");
  const active = useWorkspaceActive();
  const location = useLocation();
  return <><label>{view}<input value={draft} onChange={(event) => setDraft(event.target.value)} /></label>
    <output data-testid={`state-${view}`}>{active ? "active" : "inactive"} {location.pathname}</output></>;
}

function PersistentHarness({ visible = true }: { visible?: boolean }) {
  const location = useLocation();
  const navigate = useNavigate();
  return <><nav><Link to="/">Home</Link><Link to="/mi-cv">Profile</Link><Link to="/buscar">Search</Link>
    <button onClick={() => navigate(-1)}>Back</button><button onClick={() => navigate(1)}>Forward</button></nav>
    <WorkspaceRoutes locale="es" activePanel={panelFromLocation(location)} workspaceVisible={visible}
      home={<p>Desk</p>} renderView={(view) => <Draft view={view} />} /></>;
}

describe("Persistent workspace tabs", () => {
  it("retains drafts and reading position across tabs and Home, with working browser history", () => {
    render(<MemoryRouter initialEntries={["/mi-cv"]}><PersistentHarness /></MemoryRouter>);
    fireEvent.change(screen.getByRole("textbox", { name: "profile" }), { target: { value: "Unfinished profile" } });
    const profileMain = screen.getByRole("main");
    profileMain.scrollTop = 290;
    fireEvent.scroll(profileMain);

    fireEvent.click(screen.getByRole("link", { name: "Search" }));
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(document.querySelectorAll("#main-content")).toHaveLength(1);
    expect(screen.queryByRole("textbox", { name: "profile" })).not.toBeInTheDocument();
    expect(profileMain.closest("[inert]")).not.toBeNull();
    expect(screen.getByTestId("state-profile")).toHaveTextContent("inactive /mi-cv");
    fireEvent.change(screen.getByRole("textbox", { name: "search" }), { target: { value: "QA Automation" } });

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("textbox", { name: "profile" })).toHaveValue("Unfinished profile");
    expect(screen.getByRole("main").scrollTop).toBe(290);
    fireEvent.click(screen.getByRole("button", { name: "Forward" }));
    expect(screen.getByRole("textbox", { name: "search" })).toHaveValue("QA Automation");

    fireEvent.click(screen.getByRole("link", { name: "Home" }));
    expect(screen.getByText("Desk")).toBeInTheDocument();
    expect(screen.queryByRole("main")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "Profile" }));
    expect(screen.getByRole("textbox", { name: "profile" })).toHaveValue("Unfinished profile");
  });

  it("does not focus or expose a module until the camera transition completes", () => {
    const { rerender } = render(<MemoryRouter initialEntries={["/mi-cv"]}><PersistentHarness visible={false} /></MemoryRouter>);
    expect(screen.queryByRole("main")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByTestId("state-profile")).toHaveTextContent("inactive");
    rerender(<MemoryRouter initialEntries={["/mi-cv"]}><PersistentHarness visible /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Mi CV" })).toHaveFocus();
    expect(screen.getByTestId("state-profile")).toHaveTextContent("active");
  });
});
